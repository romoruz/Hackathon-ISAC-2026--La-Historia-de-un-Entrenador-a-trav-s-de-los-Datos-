#!/usr/bin/env python3
"""
25_goal_open_eras.py — ¿los remates de un técnico son MEJORES, no solo más?

LA PREGUNTA QUE ESTO CONTESTA
-----------------------------
El reporte ya dice cuántos remates genera cada era y dónde. No dice si son
buenos. `10_RESULTADOS.md` tiene "Jardine genera menos remates que Ortiz
(-12.5%)" y la pregunta obvia de cualquier jurado es: ¿y son mejores?

`goal_open` da ese eje. Es la fracción de portería que el rematador ve de verdad,
descontando a los defensores que la tapan. Es una medida de CALIDAD del remate,
independiente del volumen.

QUÉ HACE
--------
  A. Features de ataque y de geometría defensiva sobre cada remate.
  B. Dos modelos de gol: xG_base (solo ataque) y xG_full (+ geometría).
     Predicciones FUERA DE PLIEGUE en los dos.
  C. Delta-AUC con bootstrap POR BLOQUES: ¿la geometría aporta?
  D. Descomposición de Murphy del Brier. Cierra `10_RESULTADOS.md` §24.3.
  E. Calibración contra `shot_statsbomb_xg`: validación externa gratuita.
  F. **El hallazgo**: goal_open medio por era, con IC por bloques.

DECISIONES QUE VIENEN DEL DIAGNÓSTICO (scripts/24), NO DE MIRAR RESULTADOS
--------------------------------------------------------------------------
  · Solo `shot_type == "Open Play"`. Los 36 penales se excluyen POR DEFINICIÓN
    (no hay geometría defensiva que fotografiar), no por disponibilidad de foto.
    Filtrar por `shot_freeze_frame.is_not_null()` dejaría entrar 4 penales que
    SÍ traen foto: 4 observaciones con goal_open ~ 1 y cero goles, que atenúan
    justo el efecto que se quiere medir. Es el bug #10 con otra cara.
  · Los tiros libres directos van aparte (--con-tiros-libres), como sensibilidad
    declarada: hay geometría (la barrera) pero el proceso generador es otro.
  · Portero ausente -> se descarta ese remate para las features de portero.
    NUNCA `fillna(median)`.

EL BLOQUE DE REMUESTREO ES EL PARTIDO
-------------------------------------
ADR-07 fija la posesión como unidad para las cantidades de la cadena. Aquí NO
sirve: casi toda posesión tiene un solo remate, así que remuestrear por posesión
es prácticamente i.i.d. y estrecha los IC de mentira.

La era se asigna A NIVEL DE PARTIDO, y los remates de un partido comparten rival,
marcador y contexto. El bloque correcto para este estimando es el PARTIDO — el
mismo que usa la nula por permutación del bloque defensivo (ADR-48).
`--bloque possession` está disponible para comprobar cuánto estrecha.

SIN DEPENDENCIAS NUEVAS
-----------------------
La logística regularizada va implementada con numpy (Newton-Raphson / IRLS). No
entra sklearn: ADR-19 restringe las dependencias, y ver la verosimilitud escrita
conecta con el curso de inferencia mejor que una llamada a `.fit()`.

Uso:
    python scripts/25_goal_open_eras.py \\
      --eventos eventos_completos_america.csv --club "América" \\
      --parquet data/processed/transitions.parquet \\
      --era-a "Andre Jardine" --era-b "Fernando Ortiz"
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dtdecoder.geometria_remate import Contadores, RADIO_DEFENSOR  # noqa: E402
from dtdecoder.xg_remate import (  # noqa: E402
    ATA, DEF, ajusta_logistica, features, fuera_de_pliegue, predice,
)

SEED = 20260826


# ======================================================================
# Inferencia por bloques
# ======================================================================
def boot_bloques(bloques, stat, B=4000, rng=None):
    """Bootstrap remuestreando BLOQUES enteros con reemplazo."""
    rng = rng or np.random.default_rng(SEED)
    ub = np.unique(bloques)
    idx_de = {b: np.where(bloques == b)[0] for b in ub}
    out = []
    for _ in range(B):
        elegidos = rng.choice(ub, size=len(ub), replace=True)
        idx = np.concatenate([idx_de[b] for b in elegidos])
        v = stat(idx)
        if v is not None and np.isfinite(v):
            out.append(v)
    return np.array(out)


def ic_percentil(v, alpha=0.05):
    return float(np.percentile(v, 100 * alpha / 2)), float(np.percentile(v, 100 * (1 - alpha / 2)))


def auc(y, p):
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return np.nan
    r = np.argsort(np.argsort(p)) + 1.0
    n1, n0 = y.sum(), (1 - y).sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def murphy(p, y, bins=10):
    """BS = UNC - RES + REL. Portado de `06_diagnosticos.py` del proyecto previo."""
    p, y = np.asarray(p), np.asarray(y)
    ybar = y.mean()
    unc = ybar * (1 - ybar)
    bordes = np.quantile(p, np.linspace(0, 1, bins + 1))
    bordes[0], bordes[-1] = -np.inf, np.inf
    rel = res = 0.0
    for i in range(bins):
        m = (p >= bordes[i]) & (p < bordes[i + 1])
        if m.sum() == 0:
            continue
        pk, ok, nk = p[m].mean(), y[m].mean(), m.sum()
        rel += nk * (pk - ok) ** 2
        res += nk * (ok - ybar) ** 2
    n = len(y)
    return {"BS": float(np.mean((p - y) ** 2)), "UNC": float(unc),
            "RES": float(res / n), "REL": float(rel / n)}


# ======================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eventos", required=True)
    ap.add_argument("--club", required=True)
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--era-a", required=True)
    ap.add_argument("--era-b", required=True)
    ap.add_argument("--radio", type=float, default=RADIO_DEFENSOR)
    ap.add_argument("--lam", type=float, default=3.0)
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("--bloque", choices=["match", "possession"], default="match")
    ap.add_argument("--con-tiros-libres", action="store_true",
                    help="sensibilidad: añade los tiros libres directos")
    ap.add_argument("--out", default="reports")
    a = ap.parse_args()

    rng = np.random.default_rng(SEED)
    lf = pl.scan_csv(a.eventos, infer_schema_length=None)
    cols = lf.collect_schema().names()
    for c in ("shot_type", "shot_freeze_frame", "location", "shot_outcome",
              "possession", "match_id"):
        if c not in cols:
            sys.exit(f"falta la columna '{c}'")

    tipos = ["Open Play"] + (["Free Kick"] if a.con_tiros_libres else [])
    extra = [c for c in ("shot_statsbomb_xg", "shot_body_part", "shot_first_time")
             if c in cols]

    d = (lf.filter((pl.col("type") == "Shot") & (pl.col("team") == a.club)
                   & pl.col("shot_type").is_in(tipos))
           .select(["match_id", "possession", "location", "shot_freeze_frame",
                    "shot_outcome", "shot_type"] + extra)
           .collect())

    eras = (pl.read_parquet(a.parquet).select(["match_id", "coach"])
              .drop_nulls().unique())
    d = d.join(eras, on="match_id", how="left")
    print(f"remates {tipos}: {d.height:,}   (penales excluidos por definición)")

    # ---------- features ----------
    cont = Contadores()
    filas, y, blo, era, xg_sb = [], [], [], [], []
    for row in d.iter_rows(named=True):
        f = features(row["location"], row["shot_freeze_frame"], a.radio, cont)
        if f is None or not np.isfinite(f["goal_open"]):
            continue
        filas.append(f)
        y.append(1 if row["shot_outcome"] == "Goal" else 0)
        blo.append(row["match_id"] if a.bloque == "match"
                   else f'{row["match_id"]}_{row["possession"]}')
        era.append(row["coach"])
        xg_sb.append(row.get("shot_statsbomb_xg", np.nan))

    y = np.array(y, float)
    blo = np.array(blo)
    era = np.array([e if e is not None else "" for e in era])
    xg_sb = np.array([v if v is not None else np.nan for v in xg_sb], float)
    print(f"con geometría válida: {len(y):,}   goles: {int(y.sum())}   "
          f"tasa {y.mean():.2%}")
    print(f"contadores de geometría: {cont.resumen()}")

    M = np.array([[f[c] for c in ATA + DEF] for f in filas])
    # Un remate sin portero pierde 2 features. Se descarta ENTERO en vez de
    # imputar: es la regla que fijó scripts/24 §3.
    ok = np.isfinite(M).all(1)
    print(f"descartados por portero ausente u otra feature nula: {(~ok).sum()}")
    M, y, blo, era, xg_sb = M[ok], y[ok], blo[ok], era[ok], xg_sb[ok]
    # Una feature sin varianza no aporta y su coeficiente estandarizado sale 0
    # sin que nada falle: parece "sin efecto" cuando en realidad es "sin datos".
    sd0 = M.std(0)
    for nom, s_ in zip(ATA + DEF, sd0):
        if s_ < 1e-8:
            print(f"  AVISO: la feature '{nom}' es CONSTANTE (sd={s_:.2e}). "
                  f"Su coeficiente sera 0 por construccion, no por ausencia de efecto.")

    Xa, Xf = M[:, :len(ATA)], M

    # ---------- B. dos modelos, fuera de pliegue ----------
    p_base = fuera_de_pliegue(Xa, y, blo, lam=a.lam, rng=rng)
    p_full = fuera_de_pliegue(Xf, y, blo, lam=a.lam, rng=rng)
    print("\n" + "=" * 66)
    print("B. ¿APORTA LA GEOMETRÍA DEFENSIVA?")
    print("=" * 66)
    print(f"  AUC xG_base {auc(y, p_base):.4f}   AUC xG_full {auc(y, p_full):.4f}")

    dv = boot_bloques(blo, lambda i: (auc(y[i], p_full[i]) - auc(y[i], p_base[i])),
                      B=a.n_boot, rng=rng)
    lo, hi = ic_percentil(dv)
    print(f"  Delta-AUC {auc(y,p_full)-auc(y,p_base):+.4f}  IC95 [{lo:+.4f}, {hi:+.4f}]"
          f"  -> {'significativo' if lo > 0 else 'NO significativo (cruza 0)'}")
    print(f"  (bootstrap por {a.bloque}; {len(np.unique(blo)):,} bloques)")

    # coeficientes sobre el ajuste completo, solo direccionales
    mu, sd = Xf.mean(0), Xf.std(0) + 1e-9
    b = ajusta_logistica((Xf - mu) / sd, y, lam=a.lam)
    print("\n  coeficientes estandarizados (DIRECCIÓN, no magnitud):")
    for nom, c in zip(ATA + DEF, b[1:]):
        print(f"      {nom:14} {c:+.3f}")

    # ---------- D. Murphy ----------
    print("\n" + "=" * 66)
    print("D. DESCOMPOSICIÓN DE MURPHY DEL BRIER  (10_RESULTADOS §24.3)")
    print("=" * 66)
    res = {}
    for nom, p in (("xG_base", p_base), ("xG_full", p_full)):
        m = murphy(p, y)
        res[nom] = m
        print(f"  {nom}: BS={m['BS']:.5f}  UNC={m['UNC']:.5f}  "
              f"RES={m['RES']:.5f}  REL={m['REL']:.5f}")
    if np.isfinite(xg_sb).sum() > 50:
        v = np.isfinite(xg_sb)
        m = murphy(xg_sb[v], y[v])
        res["statsbomb"] = m
        print(f"  StatsBomb xG (referencia externa): BS={m['BS']:.5f}  "
              f"REL={m['REL']:.5f}  AUC={auc(y[v], xg_sb[v]):.4f}")
        print(f"    correlación xG_full vs StatsBomb: "
              f"{np.corrcoef(p_full[v], xg_sb[v])[0,1]:.3f}")
    mf = res["xG_full"]
    resuelta = mf["RES"] / mf["UNC"]          # destreza: cuanto explica el modelo
    print(f"\n  RES/UNC = {resuelta:.1%}  ->  el modelo resuelve el "
          f"{resuelta:.1%} de la incertidumbre;")
    print(f"  el {1-resuelta:.1%} restante es IRREDUCIBLE con estas features.")
    print(f"  fiabilidad REL={mf['REL']:.5f} (mas cerca de 0 = mejor calibrado).")
    print("  Un RES bajo NO es un fallo del modelo: es que el gol desde juego")
    print("  abierto es mayormente azar. Es el mismo diagnostico que el 97% del")
    print("  proyecto de corners, calculado igual (RES/UNC), no como UNC/BS.")
    if mf["BS"] > mf["UNC"]:
        print("  AVISO: BS > UNC, el modelo es PEOR que predecir la tasa base.")

    # ---------- F. el hallazgo ----------
    print("\n" + "=" * 66)
    print(f"F. CALIDAD DE REMATE POR ERA: {a.era_a} vs {a.era_b}")
    print("=" * 66)
    ia, ib = era == a.era_a, era == a.era_b
    if ia.sum() < 30 or ib.sum() < 30:
        sys.exit(f"muestra insuficiente: {ia.sum()} y {ib.sum()} remates")
    go = M[:, ATA.__len__() + DEF.index("goal_open")]

    salida = {"club": a.club, "era_a": a.era_a, "era_b": a.era_b,
              "n_a": int(ia.sum()), "n_b": int(ib.sum()),
              "bloque": a.bloque, "radio": a.radio, "tipos": tipos,
              "delta_auc": {"est": auc(y, p_full) - auc(y, p_base),
                            "lo": lo, "hi": hi},
              "murphy": res, "contadores": vars(cont)}

    # DESCOMPOSICION: xG_full mezcla features de ataque y de defensa, asi que
    # una diferencia significativa en xG_full puede venir ENTERA de que una era
    # remata desde mejores posiciones. Sin xG_base al lado, el hallazgo no se
    # puede atribuir a la geometria defensiva.
    #
    #   D(xG_full) = D(xG_base)  +  resto
    #                 posicion      geometria defensiva
    #
    for nom, vec in (("goal_open medio", go),
                     ("xG_base medio", p_base), ("xG_full medio", p_full),
                     ("tasa de gol", y)):
        est = vec[ia].mean() - vec[ib].mean()
        bs = boot_bloques(blo, lambda i: (vec[i][ia[i]].mean() - vec[i][ib[i]].mean()
                                          if ia[i].sum() and ib[i].sum() else None),
                          B=a.n_boot, rng=rng)
        l, h = ic_percentil(bs)
        marca = "SIGNIFICATIVO" if l * h > 0 else "cruza 0"
        print(f"  {nom:16} {vec[ia].mean():.4f} vs {vec[ib].mean():.4f}   "
              f"dif {est:+.4f}  IC95 [{l:+.4f}, {h:+.4f}]  {marca}")
        salida[nom.replace(" ", "_")] = {"a": float(vec[ia].mean()),
                                         "b": float(vec[ib].mean()),
                                         "dif": float(est), "lo": l, "hi": h,
                                         "significativo": bool(l * h > 0)}

    # La atribucion, con su IC propio: no basta con restar dos diferencias
    # puntuales, porque la resta tambien tiene incertidumbre.
    print("\n  ATRIBUCIÓN — ¿de dónde viene la diferencia de calidad?")
    d_base = p_base[ia].mean() - p_base[ib].mean()
    d_full = p_full[ia].mean() - p_full[ib].mean()
    bs = boot_bloques(blo, lambda i: (
        (p_full[i][ia[i]].mean() - p_full[i][ib[i]].mean())
        - (p_base[i][ia[i]].mean() - p_base[i][ib[i]].mean())
        if ia[i].sum() and ib[i].sum() else None), B=a.n_boot, rng=rng)
    l2, h2 = ic_percentil(bs)
    print(f"      por posición del remate (xG_base)  {d_base:+.4f}")
    print(f"      por geometría defensiva (resto)    {d_full-d_base:+.4f}"
          f"  IC95 [{l2:+.4f}, {h2:+.4f}]"
          f"  {'SIGNIFICATIVO' if l2*h2 > 0 else 'cruza 0'}")
    salida["atribucion"] = {"posicion": float(d_base),
                            "geometria": float(d_full - d_base),
                            "lo": l2, "hi": h2,
                            "significativo": bool(l2 * h2 > 0)}
    if abs(d_full - d_base) < abs(d_base) / 3:
        print("      -> la diferencia es sobre todo de POSICIÓN, no de que la")
        print("         defensa rival dejara más portería visible.")

    # goal_open tiene masa puntual en 1.0 (defensores fuera de la linea de
    # vision): la media resume mal esa distribucion.
    print(f"\n  DISTRIBUCIÓN de goal_open (la media resume mal si hay masa en 1):")
    for nom, m_ in ((a.era_a, ia), (a.era_b, ib)):
        v = go[m_]
        print(f"      {nom:18} =1.00 el {(v >= 0.9999).mean():5.1%}   "
              f"<0.90 el {(v < 0.90).mean():5.1%}   mediana {np.median(v):.3f}")
    salida["masa_en_uno"] = {a.era_a: float((go[ia] >= 0.9999).mean()),
                             a.era_b: float((go[ib] >= 0.9999).mean())}

    print("\n  LECTURA: goal_open mide CALIDAD del remate (cuánta portería ve")
    print("  el rematador). Es un eje independiente del VOLUMEN de remates que")
    print("  ya reporta la cadena. Un técnico puede rematar menos y mejor.")
    print("\n  NO afirmar la nula: si un IC cruza 0, la frase es 'no detectamos")
    print("  una diferencia mayor que X', nunca 'no hay diferencia'.")

    Path(a.out).mkdir(exist_ok=True)
    f = Path(a.out) / f"goal_open_{a.era_a}_{a.era_b}.json".replace(" ", "")
    f.write_text(json.dumps(salida, indent=2, ensure_ascii=False, default=float))
    print(f"\nguardado en {f}")


if __name__ == "__main__":
    main()
