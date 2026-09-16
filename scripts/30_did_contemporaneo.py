#!/usr/bin/env python3
"""
30_did_contemporaneo.py — ADR-53: el contraste entre eras, con la deriva fuera.

EL PROBLEMA (paquete h2_11)
---------------------------
En `25_pares_h4.py` la linea base contemporanea solo construye el prior `q`, y
magnitud y permutacion corren a lambda=0: el prior no entra. La v5 mide
diferencia entre eras CON la deriva del proveedor dentro. Sintoma: en 37 de los
45 pares significativos el entrenador POSTERIOR tiene posesiones mas largas.

EL CONTRASTE (ADR-53)
---------------------
Para cada unidad u = (club, entrenador):

    D_u = log E_T(P_u, alpha_u) - log E_T(P_base(u), alpha_u)

  * P_u, alpha_u : EMV a lambda=0 y distribucion inicial empirica de u. Es el
    MISMO estimando que `08_ic_derivados.py` (alpha' N 1), con la MISMA
    funcion `derivadas`: una sola ruta para E[T] (leccion del bug #2).
  * P_base(u)   : la liga SIN el club de u (B1), en los MISMOS torneos,
    ponderada a la mezcla de transiciones de u por torneo (B2). Cada torneo
    se normaliza por su total antes de mezclar, asi que un torneo con mas
    eventos anotados no pesa mas que otro.
  * alpha_u se usa en los DOS terminos: D_u compara que pasa despues de
    empezar donde empieza u, no donde empieza la liga.

Para un par (a, b) del mismo club:   theta = D_a - D_b,   rel = exp(theta) - 1.

Es una diferencia en diferencias en escala logaritmica. NO es el DiD clasico:
cada era se observa en su propio periodo y no hay pre-tratamiento. El supuesto
que lo sostiene es que, sin cambio de entrenador, el club se habria movido como
la liga. B3/B4 de `24_linea_base_contemporanea.py` lo contrastan, y el
contraste es debil por construccion.

INCERTIDUMBRE
-------------
Bootstrap no parametrico por posesion (ADR-07/31), intervalo `basic` (ADR-10),
en escala log. Se remuestrean las posesiones del foco Y las de la base, esta
ultima estratificada por torneo, salvo `--base-fija`. La mezcla por torneo se
recalcula en cada replica con las posesiones remuestreadas del foco.

p bilateral por inversion del intervalo basic:
    p = min(1, 2 (1 + #{theta* - theta >= |theta|, del lado de theta}) / (B+1))
de modo que p < a  <=>  el IC basic al nivel 1-a excluye el cero.

REGLAS PREINSCRITAS (2026-09-15, antes de correr esto)
======================================================
D53-1. Familia NUEVA de descubrimiento: theta de E[T] sobre TODOS los pares
       dentro del mismo club, con BH al 5%. No hereda nada de la v5.
D53-2. P_gol y P_remate son DESCRIPTIVOS: IC, sin p, fuera de la familia.
D53-3. El contraste CRUDO (mismo estimando, sin normalizar) se calcula con las
       mismas replicas para mostrar el efecto de la correccion. Su BH se
       reporta como comparacion, nunca como hallazgo.
D53-4. Control negativo: criterio de equivalencia SIN CAMBIOS respecto a la v5
       (IC95 de E[T] dentro de +-3% e IC95 de P_gol dentro de +-10%). Si
       ningun par lo cumple, se reporta el menor margen demostrable y NO se
       relajan los margenes.
D53-5. Clave compuesta (club, entrenador) en todo diccionario y archivo.
D53-6. Candado H4-8 vigente: ninguna era PRIMERA_DE_VENTANA sin verificar.
D53-7. La serie por torneo de D_u es DESCRIPTIVA (sin IC) y solo para torneos
       con al menos --min-poss-torneo posesiones del foco.
D53-8. Si 2/(B+1) > alpha/m, el piso del p impide rechazar un par aislado; el
       JSON lo declara. Por eso el defecto es B = 4000.

Uso:
    python scripts/30_did_contemporaneo.py \\
        --indirs data/processed_api_* --prior-from data/prior_liga \\
        --v5 reports/pares_h4_v5.json --out reports/did_h4_v1.json

    # humo, rapido, a otro archivo:
    python scripts/30_did_contemporaneo.py --indirs data/processed_api_america \\
        --prior-from data/prior_liga --n-boot 200 --out /tmp/did_humo.json
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
_EPS = 1e-12

REGLAS = {
    "D53-1": "familia nueva: theta(E_T) de todos los pares intra-club, BH 5%",
    "D53-2": "P_gol y P_remate descriptivos, fuera de la familia",
    "D53-3": "el crudo (mismo estimando, sin normalizar) es comparacion, no hallazgo",
    "D53-4": "control negativo con margenes SIN CAMBIOS (3% E_T, 10% P_gol)",
    "D53-5": "clave compuesta (club, entrenador)",
    "D53-6": "candado H4-8 vigente",
    "D53-7": "serie por torneo descriptiva",
    "D53-8": "se declara si el piso del p impide rechazar un par aislado",
}
CANT = ("E_T", "P_gol", "P_remate")


# ==========================================================================
# Matematica nueva: pura, sin dtdecoder (la prueban los tests)
# ==========================================================================
def base_ponderada(C_por_torneo: dict, peso_por_torneo: dict) -> np.ndarray:
    """B2: mezcla de la base con la composicion por torneo del foco.

    Cada torneo se normaliza por su total ANTES de mezclar. Si no, un torneo
    con mas anotacion (la deriva que se quiere cancelar) pesaria mas.
    """
    tot = float(sum(peso_por_torneo.values()))
    if tot <= 0:
        raise ValueError("pesos por torneo vacios")
    out = None
    for t, w in peso_por_torneo.items():
        if w <= 0:
            continue
        if t not in C_por_torneo:
            raise ValueError(f"la base no tiene el torneo {t}")
        C = C_por_torneo[t]
        s = float(C.sum())
        if s <= 0:
            raise ValueError(f"la base del torneo {t} esta vacia")
        term = (w / tot) * (C / s)
        out = term if out is None else out + term
    return out


def normaliza_filas(C: np.ndarray) -> np.ndarray:
    n = C.sum(axis=1, keepdims=True)
    return np.where(n > 0, C / np.maximum(n, _EPS), 1.0 / C.shape[1])


def p_basic(reps: np.ndarray, punto: float) -> float:
    """p bilateral por inversion del intervalo basic.

    El IC basic al nivel 1-a es [2t - q(1-a/2), 2t - q(a/2)]. Excluye el cero
    con t > 0 cuando q(1-a/2) < 2t, es decir cuando la cola de replicas con
    t* - t >= t tiene masa menor que a/2.
    """
    r = np.asarray(reps, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0 or not np.isfinite(punto):
        return float("nan")
    dev = r - punto
    if punto >= 0:
        k = int((dev >= punto).sum())
    else:
        k = int((dev <= punto).sum())
    return float(min(1.0, 2.0 * (1 + k) / (r.size + 1)))


def ic_basic(reps: np.ndarray, punto: float, nivel: float = 0.95) -> tuple[float, float]:
    r = np.asarray(reps, dtype=float)
    r = r[np.isfinite(r)]
    a = (1.0 - nivel) / 2.0
    lo, hi = np.quantile(r, a), np.quantile(r, 1.0 - a)
    return float(2.0 * punto - hi), float(2.0 * punto - lo)


def a_rel(x: float) -> float:
    return float(np.expm1(x))


def equivalente(ic_rel: tuple[float, float], margen: float) -> bool:
    return bool(ic_rel[0] >= -margen and ic_rel[1] <= margen)


def semilla(base: int, club: str, coach: str) -> np.random.Generator:
    """Semilla estable por unidad. NO usa hash(): esta aleatorizado por proceso."""
    return np.random.default_rng([base,
                                  zlib.crc32(club.encode("utf-8")),
                                  zlib.crc32(coach.encode("utf-8"))])


def pesos_por_torneo(lens: np.ndarray, torneo_idx: np.ndarray,
                     elegidas: np.ndarray, n_torneos: int) -> np.ndarray:
    """Transiciones del foco por torneo en una seleccion de posesiones."""
    return np.bincount(torneo_idx[elegidas], weights=lens[elegidas],
                       minlength=n_torneos)


def logratio(x: float, y: float) -> float:
    if not (x > 0 and y > 0):
        return float("nan")
    return float(np.log(x) - np.log(y))


# ==========================================================================
# Carga de la maquinaria del proyecto (una sola ruta para cada cosa)
# ==========================================================================
def _carga(nombre: str):
    ruta = RAIZ / "scripts" / nombre
    spec = importlib.util.spec_from_file_location(nombre.replace(".py", "").lstrip("0123456789_"), ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Foco:
    """Indice de 08 + torneo de cada posesion, en el MISMO orden."""

    def __init__(self, df, space, m08, torneos: list[str]):
        import polars as pl
        self.idx = m08.Indice(df, space)
        orden = ["poss_uid"] + (["event_index"] if "event_index" in df.columns else [])
        ds = df.sort(orden)
        uid_ini = ds["poss_uid"].to_numpy()[self.idx.starts]
        tor = ds["torneo"].to_numpy()[self.idx.starts]
        prim = (ds.group_by("poss_uid", maintain_order=True)
                .agg(pl.col("torneo").first()))
        # comprobacion de alineacion: el torneo de cada posesion tiene que
        # venir de la misma fila que su inicio en el Indice
        if prim.height != self.idx.n_poss:
            raise RuntimeError("desalineacion Indice / posesiones")
        self.pos = {t: k for k, t in enumerate(torneos)}
        self.torneo_idx = np.array([self.pos[t] for t in tor], dtype=np.int64)
        self.uids = uid_ini
        self.n_torneos = len(torneos)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indirs", nargs="+", required=True, type=Path)
    ap.add_argument("--prior-from", required=True, type=Path, dest="prior_from")
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--n-boot", type=int, default=4000, dest="n_boot")
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--nivel", type=float, default=0.95)
    ap.add_argument("--margen-et", type=float, default=0.03)
    ap.add_argument("--margen-gol", type=float, default=0.10)
    ap.add_argument("--min-poss-torneo", type=int, default=400)
    ap.add_argument("--base-fija", action="store_true",
                    help="no remuestrear la base (mas rapido; subestima el IC)")
    ap.add_argument("--sin-candado", action="store_true",
                    help="NO usar para resultados reportables")
    ap.add_argument("--v5", type=Path, default=None,
                    help="pares_h4_v5.json para la tabla de comparacion")
    ap.add_argument("--out", type=Path, default=Path("reports/did_h4_v1.json"))
    args = ap.parse_args()

    if args.out.exists():
        sys.exit(f"{args.out} ya existe. Regla de sesion: escribir a un archivo "
                 "NUEVO cuando el resultado puede reemplazar a uno publicado.")

    import polars as pl
    from dtdecoder.cli import _read_trans
    from dtdecoder.config import Config
    from dtdecoder.eras import check_verificada
    from dtdecoder.estimate import count_matrix
    from dtdecoder.inference import benjamini_hochberg

    m08 = _carga("08_ic_derivados.py")
    # torneo_cols de 24 (etiqueta Y orden cronologico). La de 25 solo emite la
    # etiqueta: ordenar por ella es alfabetico, el bug de 22_deriva_proveedor.
    m24 = _carga("24_linea_base_contemporanea.py")
    cfg = Config.load(args.config)
    space = m08._space(cfg)
    t0 = time.time()

    liga = _read_trans(str(args.prior_from), permitir_prior=True)
    liga = liga.with_columns(m24.torneo_cols())
    if not args.base_fija:
        if "poss_uid" not in liga.columns:
            sys.exit("El artefacto del prior no trae `poss_uid`: no se puede "
                     "remuestrear la base. Usa --base-fija (y declaralo).")
        if "match_id" in liga.columns:
            rep_uid = (liga.group_by("poss_uid")
                       .agg(pl.col("match_id").n_unique().alias("k"))["k"].max())
            if rep_uid and rep_uid > 1:
                sys.exit("`poss_uid` se repite entre partidos en el prior: el "
                         "remuestreo por posesion mezclaria posesiones distintas.")
    orden_t = dict(liga.select("torneo", "torneo_orden").unique().iter_rows())
    torneos = sorted(orden_t, key=orden_t.get)          # cronologico, no alfabetico
    print(f"liga: {liga.height:,} transiciones · torneos: {' '.join(torneos)}")

    # Conteos de la liga por (team, torneo), una sola vez.
    C_eq_t: dict[tuple[str, str], np.ndarray] = {}
    for (eq, t), g in liga.group_by(["team", "torneo"]):
        C_eq_t[(eq, t)] = count_matrix(g, space)
    equipos = sorted({e for e, _ in C_eq_t})
    print(f"conteos por equipo y torneo: {len(C_eq_t)} matrices, "
          f"{len(equipos)} equipos\n")

    def estima(C, alpha, prior):
        return m08.derivadas(C, alpha, prior, 0.0, space)

    unidades: dict[tuple[str, str], dict] = {}
    reps: dict[tuple[str, str], dict] = {}
    saltadas = []

    for indir in sorted(args.indirs):
        rp = indir / "phase0_report.json"
        if not rp.exists():
            continue
        co = json.loads(rp.read_text()).get("coaches") or {}
        club = co.get("club")
        dts = [c["coach"] for c in co.get("coverage", []) if c.get("suficiente")]
        if not club or not dts:
            continue
        if not args.sin_candado:
            vivos = []
            for dt in dts:
                try:
                    check_verificada(club, dt)
                    vivos.append(dt)
                except SystemExit:
                    saltadas.append({"club": club, "coach": dt,
                                     "motivo": "PRIMERA_DE_VENTANA sin verificar"})
            dts = vivos
        if not dts:
            continue

        trans = _read_trans(str(indir)).with_columns(m24.torneo_cols())
        # base de ESTE club: liga sin el club, por torneo
        C_base_t = {t: sum(C_eq_t[(e, t)] for e in equipos
                           if e != club and (e, t) in C_eq_t)
                    for t in torneos}
        idx_base_t = {}
        if not args.base_fija:
            for t in torneos:
                g = liga.filter((pl.col("team") != club) & (pl.col("torneo") == t))
                if g.height:
                    idx_base_t[t] = m08.Indice(g, space)

        for dt in dts:
            sel_c = pl.col("coach") == dt
            df = trans.filter(sel_c & (pl.col("team") == club))
            n_solo_coach = trans.filter(sel_c).height
            if df.height == 0:
                continue
            f = Foco(df, space, m08, torneos)
            B_ = args.n_boot
            todas = np.arange(f.idx.n_poss)
            w0 = pesos_por_torneo(f.idx.lens, f.torneo_idx, todas, f.n_torneos)
            peso0 = {t: w0[k] for t, k in f.pos.items() if w0[k] > 0}
            n_base = float(sum(C_base_t[t].sum() for t in peso0))
            Cb0 = n_base * base_ponderada(C_base_t, peso0)
            Pb0 = normaliza_filas(Cb0)
            Cu0, au0 = f.idx.todo()
            eu, eb = estima(Cu0, au0, Pb0), estima(Cb0, au0, Pb0)
            if eu is None or eb is None:
                saltadas.append({"club": club, "coach": dt, "motivo": "rho(Q) >= 1"})
                continue
            punto = {k: {"D": logratio(eu[k], eb[k]), "L": float(np.log(eu[k]))
                         if eu[k] > 0 else float("nan")} for k in CANT}

            rng = semilla(args.seed, club, dt)
            R_D = np.full((B_, len(CANT)), np.nan)
            R_L = np.full((B_, len(CANT)), np.nan)
            for b in range(B_):
                el = rng.integers(0, f.idx.n_poss, size=f.idx.n_poss)
                Cu, au = f.idx.conteos_y_alpha(el)
                w = pesos_por_torneo(f.idx.lens, f.torneo_idx, el, f.n_torneos)
                peso = {t: w[k] for t, k in f.pos.items() if w[k] > 0}
                if args.base_fija:
                    Cb = n_base * base_ponderada(C_base_t, peso)
                else:
                    Cb_t = {}
                    for t in peso:
                        ib = idx_base_t[t]
                        Cb_t[t], _ = ib.conteos_y_alpha(
                            rng.integers(0, ib.n_poss, size=ib.n_poss))
                    Cb = n_base * base_ponderada(Cb_t, peso)
                Pb = normaliza_filas(Cb)
                xu, xb = estima(Cu, au, Pb), estima(Cb, au, Pb)
                if xu is None or xb is None:
                    continue
                for j, k in enumerate(CANT):
                    R_D[b, j] = logratio(xu[k], xb[k])
                    R_L[b, j] = np.log(xu[k]) if xu[k] > 0 else np.nan
            validas = int(np.isfinite(R_D[:, 0]).sum())

            # serie por torneo (D53-7), descriptiva
            serie = {}
            tor_df = df.group_by("torneo").agg(pl.col("poss_uid").n_unique().alias("n"))
            for t, n in tor_df.iter_rows():
                if n < args.min_poss_torneo:
                    continue
                sub = df.filter(pl.col("torneo") == t)
                it = m08.Indice(sub, space)
                Ct, at = it.todo()
                Pbt = normaliza_filas(C_base_t[t])
                xu_t, xb_t = estima(Ct, at, Pbt), estima(C_base_t[t], at, Pbt)
                if xu_t and xb_t:
                    serie[t] = {"n_poss": int(n),
                                "rel_E_T": a_rel(logratio(xu_t["E_T"], xb_t["E_T"]))}
            serie = dict(sorted(serie.items(), key=lambda kv: orden_t[kv[0]]))

            lo, hi = ic_basic(R_D[:, 0], punto["E_T"]["D"], args.nivel)
            unidades[(club, dt)] = {
                "club": club, "coach": dt, "indir": str(indir),
                "n_poss": int(f.idx.n_poss), "n_transiciones": int(df.height),
                "aviso_filtro": (None if n_solo_coach == df.height else
                                 f"coach solo: {n_solo_coach}; (club, coach): {df.height}"),
                "torneos": [t for t in torneos if t in peso0],
                "n_transiciones_base": int(sum(C_base_t[t].sum() for t in peso0)),
                "E_T": eu["E_T"], "E_T_base": eb["E_T"],
                "rel_E_T_vs_liga": a_rel(punto["E_T"]["D"]),
                "rel_E_T_vs_liga_ic95": [a_rel(lo), a_rel(hi)],
                "replicas_validas": validas,
                "serie_por_torneo": serie,
            }
            reps[(club, dt)] = {"D": R_D, "L": R_L, "punto": punto}
            print(f"  {club:<20}{dt:<26} n={f.idx.n_poss:>6}  "
                  f"vs liga {100*a_rel(punto['E_T']['D']):+6.2f}% "
                  f"[{100*a_rel(lo):+6.2f}, {100*a_rel(hi):+6.2f}]  "
                  f"({validas}/{B_} replicas, {time.time()-t0:,.0f} s)")
        del idx_base_t

    # ---------------------------------------------------------------- pares
    pares = []
    por_club: dict[str, list[str]] = {}
    for club, dt in unidades:
        por_club.setdefault(club, []).append(dt)
    for club in sorted(por_club):
        for x, y in itertools.combinations(sorted(por_club[club]), 2):
            ra, rb = reps[(club, x)], reps[(club, y)]
            fila = {"club": club, "a": x, "b": y,
                    "n_poss_a": unidades[(club, x)]["n_poss"],
                    "n_poss_b": unidades[(club, y)]["n_poss"],
                    "did": {}, "crudo": {}}
            for j, k in enumerate(CANT):
                for tipo, clave in (("did", "D"), ("crudo", "L")):
                    th = ra["punto"][k][clave] - rb["punto"][k][clave]
                    r = ra[clave][:, j] - rb[clave][:, j]
                    lo, hi = ic_basic(r, th, args.nivel)
                    ent = {"rel": a_rel(th), "ic95": [a_rel(lo), a_rel(hi)],
                           "replicas_validas": int(np.isfinite(r).sum())}
                    if k == "E_T":
                        ent["p"] = p_basic(r, th)
                    fila[tipo][k] = ent
            fila["cambia_signo_por_correccion"] = bool(
                np.sign(fila["did"]["E_T"]["rel"]) != np.sign(fila["crudo"]["E_T"]["rel"]))
            pares.append(fila)

    if not pares:
        print("\nNingun par evaluable.")
        return 1

    m = len(pares)
    for tipo in ("did", "crudo"):
        p = np.array([x[tipo]["E_T"]["p"] for x in pares])
        q, rech = benjamini_hochberg(p, alpha=args.alpha)
        for x, qi, ri in zip(pares, q, rech):
            x[tipo]["E_T"]["q"] = float(qi)
            x[tipo]["E_T"]["rechaza_fdr"] = bool(ri)
    piso = 2.0 / (args.n_boot + 1)
    aviso_piso = (None if piso <= args.alpha / m else
                  f"piso del p {piso:.5f} > alpha/m {args.alpha/m:.5f}: un par "
                  "aislado no puede rechazar (D53-8)")

    # ---------------------------------------------------- control negativo
    no_rech = [x for x in pares if not x["did"]["E_T"]["rechaza_fdr"]]
    cands = []
    for x in no_rech:
        e, g = x["did"]["E_T"], x["did"]["P_gol"]
        cands.append({
            "club": x["club"], "a": x["a"], "b": x["b"],
            "rel_E_T": e["rel"], "ic95_E_T": e["ic95"],
            "rel_P_gol": g["rel"], "ic95_P_gol": g["ic95"],
            "min_n_poss": min(x["n_poss_a"], x["n_poss_b"]),
            "equivalente": equivalente(e["ic95"], args.margen_et)
                           and equivalente(g["ic95"], args.margen_gol),
            "margen_demostrable_E_T": max(abs(e["ic95"][0]), abs(e["ic95"][1])),
        })
    elegidos = sorted([c for c in cands if c["equivalente"]],
                      key=lambda c: -c["min_n_poss"])
    control = {
        "criterio": "IC95 E_T en +-{:.0%} e IC95 P_gol en +-{:.0%} (D53-4, sin cambios)"
                    .format(args.margen_et, args.margen_gol),
        "n_no_rechazados": len(no_rech),
        "elegido": elegidos[0] if elegidos else None,
        "n_equivalentes": len(elegidos),
        "menor_margen_demostrable_E_T": (min(c["margen_demostrable_E_T"] for c in cands)
                                         if cands else None),
        "candidatos": sorted(cands, key=lambda c: c["margen_demostrable_E_T"]),
    }

    # ------------------------------------------------ comparacion con la v5
    comp = None
    if args.v5 and args.v5.exists():
        v5 = {(z["club"], z["a"], z["b"]): z
              for z in json.loads(args.v5.read_text())["pares"]}
        filas = []
        for x in pares:
            z = v5.get((x["club"], x["a"], x["b"]))
            if z is None:
                continue
            filas.append({"club": x["club"], "a": x["a"], "b": x["b"],
                          "v5_rel_E_T": z["magnitud_lambda0"]["rel_E_T"],
                          "v5_rechaza": z["rechaza_fdr"],
                          "did_rel_E_T": x["did"]["E_T"]["rel"],
                          "did_rechaza": x["did"]["E_T"]["rechaza_fdr"]})
        comp = {
            "nota": "la v5 pondera por visitas (w) y este script por alpha: "
                    "estimandos distintos. El contraste limpio con la correccion "
                    "es el bloque `crudo` de cada par, no esta tabla.",
            "emparejados": len(filas),
            "v5_rechaza_y_did_no": sum(f["v5_rechaza"] and not f["did_rechaza"] for f in filas),
            "did_rechaza_y_v5_no": sum(f["did_rechaza"] and not f["v5_rechaza"] for f in filas),
            "cambian_signo": int(sum(np.sign(f["v5_rel_E_T"]) != np.sign(f["did_rel_E_T"])
                                     for f in filas)),
            "filas": filas,
        }

    # ----------------------------------------------- firma temporal (diag.)
    def posterior_mas_largo(tipo):
        n = tot = 0
        for x in pares:
            if not x[tipo]["E_T"]["rechaza_fdr"]:
                continue
            ta = unidades[(x["club"], x["a"])]["torneos"]
            tb = unidades[(x["club"], x["b"])]["torneos"]
            ma = np.mean([orden_t[t] for t in ta])
            mb = np.mean([orden_t[t] for t in tb])
            rel = x[tipo]["E_T"]["rel"]
            tot += 1
            n += int((rel > 0) == (ma > mb))
        return {"posterior_mas_largo": n, "de": tot}

    salida = {
        "adr": "ADR-53", "reglas_preinscritas": REGLAS,
        "parametros": {"n_boot": args.n_boot, "seed": args.seed, "alpha": args.alpha,
                       "nivel": args.nivel, "base_remuestreada": not args.base_fija,
                       "min_poss_torneo": args.min_poss_torneo,
                       "torneos_orden": torneos},
        "aviso_piso_p": aviso_piso,
        "eras_bloqueadas_por_candado": saltadas,
        "n_unidades": len(unidades), "n_pares": m,
        "n_rechazados_did": sum(x["did"]["E_T"]["rechaza_fdr"] for x in pares),
        "n_rechazados_crudo": sum(x["crudo"]["E_T"]["rechaza_fdr"] for x in pares),
        "n_cambian_signo_por_correccion": sum(x["cambia_signo_por_correccion"] for x in pares),
        "firma_temporal": {"did": posterior_mas_largo("did"),
                           "crudo": posterior_mas_largo("crudo")},
        "unidades": list(unidades.values()),
        "pares": pares,
        "control_negativo": control,
        "comparacion_v5": comp,
        "segundos": round(time.time() - t0, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False))

    print(f"\n{m} pares · rechazan DiD {salida['n_rechazados_did']} · "
          f"rechazan crudo {salida['n_rechazados_crudo']} · "
          f"cambian de signo al corregir {salida['n_cambian_signo_por_correccion']}")
    print(f"firma temporal (rechazados con el posterior mas largo): "
          f"crudo {salida['firma_temporal']['crudo']} · "
          f"DiD {salida['firma_temporal']['did']}")
    if aviso_piso:
        print(f"AVISO: {aviso_piso}")
    el = control["elegido"]
    mm = control["menor_margen_demostrable_E_T"]
    if el:
        print(f"control negativo: {el['club']} {el['a']} vs {el['b']}")
    elif mm is None:
        print("control negativo: no hay pares sin rechazar; no hay candidatos")
    else:
        print(f"control negativo: NINGUNO cumple; menor margen demostrable "
              f"en E_T {100*mm:.2f}% (los margenes NO se relajan, D53-4)")
    for x in pares:
        if x["club"] in ("América", "Atlas", "León"):
            d, c = x["did"]["E_T"], x["crudo"]["E_T"]
            print(f"  {x['club']:<8}{x['a'][:16]:<17}vs {x['b'][:16]:<17}"
                  f"crudo {100*c['rel']:+6.2f}%  DiD {100*d['rel']:+6.2f}% "
                  f"[{100*d['ic95'][0]:+6.2f}, {100*d['ic95'][1]:+6.2f}] "
                  f"q={d['q']:.4f}")
    print(f"\nescrito {args.out}  ({salida['segundos']:,.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
