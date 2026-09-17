#!/usr/bin/env python3
"""
40_panel_55.py — D59-P: panel 5.5, metricas del proveedor por era (descriptivo).

Preinscrito en `docs/preinscritos/PANEL_55_BORRADOR.md` antes de escribir este
archivo (el instalador de h2_27 lo commitea solo y primero). Lo que el
documento no fijaba se marca [IMPL].

  xG sin penales a favor y en contra (con penales como sensibilidad)
  OBV a favor y en contra (obv_total_net)
  pases progresivos: relativo 25% fuera del 40% propio; fijo 30/15/10 (sens.)
  field tilt del partido completo con la definicion de ADR-58 (D58-C)

Por era: media por partido, liga del mismo torneo SIN partidos del club
estandarizada a la mezcla de torneos de la era, diferencia con IC basic
(bootstrap por partido) y percentil por torneo. DESCRIPTIVO: sin p, sin BH.

Reutiliza, sin copiar: `torneo_cols` (24), `semilla` e `ic_basic` (30),
`partidos_completos` (33), `casos_desde` (36), `percentil` (38).

[IMPL] Un equipo-partido sin acciones en el ultimo tercio de ninguno de los
       dos lados tiene field tilt nulo y no entra a esa metrica.
[IMPL] OBV y xG de un equipo sin eventos con valor cuentan como 0.
[IMPL] La base del bootstrap se comparte dentro del club (semilla
       "__base__"), como en 38.

Uso:
    python scripts/40_panel_55.py --n-boot 200 --out /tmp/metricas_humo.json
    nohup python -u scripts/40_panel_55.py --out reports/metricas_v1.json \\
        > logs/metricas_v1.log 2>&1 &
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
CLUBES_ADR52 = ("america", "leon", "atlas", "atletico_san_luis", "monterrey", "cruz_azul")

ARCO = (120.0, 40.0)
X_PROPIO_40 = 48.0                      # 40% de 120
FRAC_PROG = 0.75                        # se acerca al menos un 25%
MEDIO_CAMPO = 60.0
UMBRAL_FIJO = (30.0, 15.0, 10.0)        # propio-propio, propio-rival, rival-rival
X_TERCIO = 80.0                         # D58-C
PASE_BALON_PARADO = ("Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off")
MIN_PARTIDOS_TORNEO = 12                # misma regla que 38

METRICAS = ("npxg_favor", "npxg_contra", "xg_favor_con_penales", "xg_contra_con_penales",
            "obv_favor", "obv_contra", "prog_pases", "prog_fraccion", "prog_pases_fijo",
            "field_tilt")
PRINCIPALES = ("npxg_favor", "npxg_contra", "obv_favor", "obv_contra", "prog_pases", "field_tilt")

REGLAS = {
    "D59P-0": "descriptivo: sin familia, sin p, sin BH; los IC no se redactan como hallazgos",
    "D59P-1": "xG = suma de shot_statsbomb_xg; principal sin penales; con penales como sensibilidad",
    "D59P-2": "OBV = suma de obv_total_net; en contra = la del rival en el mismo partido",
    "D59P-3": "pase progresivo: completado, de juego, x0 >= 48, d1 <= 0.75 d0 al centro del arco",
    "D59P-4": "sensibilidad: umbrales fijos 30/15/10 segun mitad de inicio y fin",
    "D59P-5": "field tilt = definicion de ADR-58 (D58-C) sobre el partido completo",
    "D59P-comparacion": "liga sin partidos del club, mismos torneos, estandarizada a la mezcla de la era",
    "D59P-incertidumbre": "bootstrap por partido, base estratificada por torneo y compartida en el club; IC basic",
}


# ==========================================================================
# Nucleo puro (cubierto por tests/test_panel_55.py)
# ==========================================================================
def dist_arco(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return np.hypot(ARCO[0] - x, ARCO[1] - y)


def progresivo_relativo(x0, y0, x1, y1) -> np.ndarray:
    x0 = np.asarray(x0, float)
    d0, d1 = dist_arco(x0, y0), dist_arco(x1, y1)
    return (x0 >= X_PROPIO_40) & (d1 <= FRAC_PROG * d0)


def progresivo_fijo(x0, y0, x1, y1) -> np.ndarray:
    x0, x1 = np.asarray(x0, float), np.asarray(x1, float)
    g = dist_arco(x0, y0) - dist_arco(x1, y1)
    p0, p1 = x0 < MEDIO_CAMPO, x1 < MEDIO_CAMPO
    umbral = np.where(p0 & p1, UMBRAL_FIJO[0],
                      np.where(p0 & ~p1, UMBRAL_FIJO[1],
                               np.where(~p0 & ~p1, UMBRAL_FIJO[2], np.inf)))
    return g >= umbral


def field_tilt(n_propio: float, n_rival: float) -> float:
    tot = n_propio + n_rival
    return float(n_propio / tot) if tot > 0 else float("nan")


def perfil_equipo_partido(por_eq: dict, a: str, b: str) -> dict[str, dict]:
    """Del acumulado por equipo {eq: {...}} a las metricas de a y b en el partido.

    por_eq[eq] trae: npxg, xg, obv, prog, prog_fijo, pases_juego, ft (acciones
    reales en el ultimo tercio). Los faltantes cuentan como 0.
    """
    def g(e, k):
        return float(por_eq.get(e, {}).get(k, 0.0) or 0.0)

    out = {}
    for e, o in ((a, b), (b, a)):
        pj = g(e, "pases_juego")
        out[e] = {
            "npxg_favor": g(e, "npxg"), "npxg_contra": g(o, "npxg"),
            "xg_favor_con_penales": g(e, "xg"), "xg_contra_con_penales": g(o, "xg"),
            "obv_favor": g(e, "obv"), "obv_contra": g(o, "obv"),
            "prog_pases": g(e, "prog"),
            "prog_fraccion": g(e, "prog") / pj if pj > 0 else float("nan"),
            "prog_pases_fijo": g(e, "prog_fijo"),
            "field_tilt": field_tilt(g(e, "ft"), g(o, "ft")),
        }
    return out


def medias_bootstrap(V: np.ndarray, t_idx: np.ndarray, W: np.ndarray, n_t: int
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Medias por torneo en cada replica, ignorando nulos.

    V: (n, K) valores; t_idx: (n,) torneo; W: (R, n) pesos.
    Devuelve suma (R, n_t, K) de pesos validos y media (R, n_t, K).
    """
    R, K = W.shape[0], V.shape[1]
    ok = np.isfinite(V)
    V0 = np.where(ok, V, 0.0)
    den = np.zeros((R, n_t, K))
    num = np.zeros((R, n_t, K))
    for t in range(n_t):
        ix = np.flatnonzero(t_idx == t)
        if ix.size == 0:
            continue
        Wt = W[:, ix]
        den[:, t, :] = Wt @ ok[ix].astype(float)
        num[:, t, :] = Wt @ V0[ix]
    with np.errstate(invalid="ignore", divide="ignore"):
        media = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
    return den, media


def comparacion(Vu, tu, Wu, Vb, tb, Wb, n_t):
    """(media era, base estandarizada) por replica y metrica: dos (R, K).

    base = sum_t w_t * media_liga_t, con w_t la fraccion de partidos VALIDOS
    de la era en t. Un torneo con peso y sin liga deja la base en nulo.
    """
    du, mu = medias_bootstrap(Vu, tu, Wu, n_t)
    _, mb = medias_bootstrap(Vb, tb, Wb, n_t)
    tot = du.sum(axis=1)                                        # (R, K)
    with np.errstate(invalid="ignore", divide="ignore"):
        era = np.where(tot > 0, np.nansum(np.where(du > 0, du * mu, 0.0), axis=1) / tot, np.nan)
        w = du / np.where(tot > 0, tot, 1.0)[:, None, :]
    malo = ((w > 0) & ~np.isfinite(mb)).any(axis=1) | (tot <= 0)
    base = np.where(w > 0, w * np.nan_to_num(mb), 0.0).sum(axis=1)
    return era, np.where(malo, np.nan, base)


# ==========================================================================
def _carga(nombre: str):
    spec = importlib.util.spec_from_file_location("m_" + nombre[:2] + "_p55", RAIZ / "scripts" / nombre)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _xy(pl, col: str, pref: str):
    partes = pl.col(col).str.strip_chars("[] ").str.split(",")
    return [partes.list.get(0).str.strip_chars(" ").cast(pl.Float64, strict=False).alias(pref + "x"),
            partes.list.get(1).str.strip_chars(" ").cast(pl.Float64, strict=False).alias(pref + "y")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=Path("data"))
    ap.add_argument("--eventos", type=Path, default=Path("data/api/eventos_api_ligamx"))
    ap.add_argument("--n-boot", type=int, default=2000, dest="n_boot")
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--nivel", type=float, default=0.95)
    ap.add_argument("--out", type=Path, default=Path("reports/metricas_v1.json"))
    args = ap.parse_args()
    if args.out.exists():
        sys.exit(f"{args.out} ya existe: escribe a un archivo NUEVO.")
    pre = RAIZ / "docs" / "preinscritos" / "PANEL_55_BORRADOR.md"
    if not pre.exists():
        sys.exit(f"ABORTA: falta la preinscripcion {pre}")

    import polars as pl
    from dtdecoder.eras import check_verificada

    m24 = _carga("24_linea_base_contemporanea.py")
    m30 = _carga("30_did_contemporaneo.py")
    m33 = _carga("33_did_presion.py")
    m36 = _carga("36_contexto.py")
    m38 = _carga("38_jugadores.py")
    t0 = time.time()

    # ------------------------------------------------ vista y universo (igual que 38)
    cols = ["match_id", "team", "event_index", "action_type", "match_date", "coach_faced"]
    dirs = sorted(p for p in args.datos.glob("processed_api_*") if (p / "phase0_report.json").exists())
    if len(dirs) != 18:
        sys.exit(f"hacen falta los 18 directorios; hay {len(dirs)}")
    partes, unidades = [], []
    for d in dirs:
        rep = json.loads((d / "phase0_report.json").read_text()).get("coaches") or {}
        club = rep["club"]
        partes.append(pl.read_parquet(d / "transitions.parquet", columns=cols)
                      .filter(pl.col("team") != club).with_columns(pl.lit(club).alias("defensor")))
        for c in rep.get("coverage", []):
            if c.get("suficiente"):
                unidades.append((d.name.replace("processed_api_", ""), club, c["coach"]))
    v = pl.concat(partes, how="vertical_relaxed")
    ternas = v.select("match_id", "team", "defensor").unique()
    completos, incompletos = m33.partidos_completos(
        ternas["match_id"].to_numpy(), ternas["team"].to_numpy(), ternas["defensor"].to_numpy())
    v = v.filter(pl.col("match_id").is_in(sorted(completos))).with_columns(m24.torneo_cols())
    orden_t = dict(v.select("torneo", "torneo_orden").unique().iter_rows())
    torneos = sorted(orden_t, key=orden_t.get)
    tpos = {t: i for i, t in enumerate(torneos)}
    n_t = len(torneos)
    torneo_de = dict(v.select("match_id", "torneo").unique().iter_rows())
    coach_de = {(m, c): e for m, c, e in v.filter(pl.col("coach_faced").is_not_null())
                .select("match_id", "defensor", "coach_faced").unique().iter_rows()}
    equipos_de: dict = {}
    for m, a, d_ in ternas.iter_rows():
        if m in completos:
            equipos_de.setdefault(m, set()).update((a, d_))
    bloqueadas, vivas = [], []
    for slug, club, dt in unidades:
        try:
            check_verificada(club, dt)
            vivas.append((slug, club, dt))
        except SystemExit:
            bloqueadas.append({"club": club, "coach": dt})
    casos = m36.casos_desde([(c, e) for _, c, e in vivas])
    print(f"vista: {v.height:,} filas · {len(completos)} partidos · eras: {len(vivas)} "
          f"({time.time()-t0:,.0f} s)")

    # ------------------------------------------------ eventos
    archivos = sorted(glob.glob(str(args.eventos / "*.parquet")))
    lf = pl.scan_parquet(archivos).filter(pl.col("match_id").is_in(sorted(completos)))
    esquema = lf.collect_schema()
    faltan = [c for c in ("shot_statsbomb_xg", "shot_type", "obv_total_net", "pass_outcome",
                          "pass_type", "pass_end_location", "location") if c not in esquema]
    if faltan:
        sys.exit(f"ABORTA (D54-9): faltan columnas {faltan}")

    tiros = (lf.filter(pl.col("type") == "Shot")
             .select("match_id", "team", "shot_statsbomb_xg", "shot_type").collect())
    tipos_tiro = dict(tiros.group_by("shot_type").len().iter_rows())
    if "Penalty" not in tipos_tiro:
        sys.exit(f"ABORTA (D59P-1): shot_type no trae 'Penalty': {tipos_tiro}")
    xg = (tiros.group_by("match_id", "team")
          .agg(pl.col("shot_statsbomb_xg").fill_null(0.0).sum().alias("xg"),
               pl.col("shot_statsbomb_xg").fill_null(0.0)
               # un shot_type nulo NO es penal: `!=` con nulo daria nulo y lo tiraria
               .filter(pl.col("shot_type").fill_null("") != "Penalty").sum().alias("npxg")))
    obv = (lf.filter(pl.col("obv_total_net").is_not_null())
           .group_by("match_id", "team").agg(pl.col("obv_total_net").sum().alias("obv"),
                                             pl.len().alias("n_obv")).collect())

    pases = lf.filter(pl.col("type") == "Pass").select(
        "match_id", "team", "pass_outcome", "pass_type", "location", "pass_end_location").collect()
    tipos_pase = dict(pases.group_by("pass_type").len().iter_rows())
    presentes = [t for t in PASE_BALON_PARADO if t in tipos_pase]
    if len(presentes) < 3:
        sys.exit(f"ABORTA (D59P-3): pass_type no trae las etiquetas esperadas: {tipos_pase}")
    frac_completo = float(pases["pass_outcome"].is_null().mean())
    juego = (pases.filter(pl.col("pass_outcome").is_null()
                          & (pl.col("pass_type").is_null() | ~pl.col("pass_type").is_in(PASE_BALON_PARADO)))
             .with_columns(*_xy(pl, "location", "i"), *_xy(pl, "pass_end_location", "f")))
    n_sin_coord = int(juego.select(pl.any_horizontal(pl.col("ix", "iy", "fx", "fy").is_null()).sum()).item())
    juego = juego.drop_nulls(["ix", "iy", "fx", "fy"])
    X = juego.select("ix", "iy", "fx", "fy").to_numpy()
    juego = juego.with_columns(
        pl.Series("prog", progresivo_relativo(X[:, 0], X[:, 1], X[:, 2], X[:, 3]).astype(np.int64)),
        pl.Series("prog_fijo", progresivo_fijo(X[:, 0], X[:, 1], X[:, 2], X[:, 3]).astype(np.int64)))
    prog = juego.group_by("match_id", "team").agg(pl.len().alias("pases_juego"),
                                                  pl.col("prog").sum(), pl.col("prog_fijo").sum())

    # field tilt: acciones reales de la vista unidas a su evento (como 38)
    acciones = (v.filter(pl.col("action_type") != "TERMINAL")
                .select("match_id", "team", "event_index")
                .join(lf.select("match_id", pl.col("index").alias("event_index"), "location").collect(),
                      on=["match_id", "event_index"], how="left"))
    tasa_union = float(acciones["location"].is_not_null().mean())
    ft = (acciones.drop_nulls("location")
          .with_columns(pl.col("location").str.strip_chars("[]").str.split(",").list.get(0)
                        .cast(pl.Float64).alias("x"))
          .group_by("match_id", "team").agg((pl.col("x") >= X_TERCIO).sum().alias("ft")))
    print(f"eventos: {tiros.height:,} remates · {pases.height:,} pases ({juego.height:,} de juego "
          f"completados) · union acciones-eventos {tasa_union:.4f} ({time.time()-t0:,.0f} s)")

    por_m: dict = defaultdict(lambda: defaultdict(dict))
    for tabla, campos in ((xg, ("xg", "npxg")), (obv, ("obv",)),
                          (prog, ("pases_juego", "prog", "prog_fijo")), (ft, ("ft",))):
        for fila in tabla.select("match_id", "team", *campos).iter_rows():
            for k, val in zip(campos, fila[2:]):
                por_m[fila[0]][fila[1]][k] = val

    # ------------------------------------------------ equipo-partido
    filas_tm = []
    for m in sorted(completos):
        a, b = sorted(equipos_de[m])
        perf = perfil_equipo_partido(por_m.get(m, {}), a, b)
        for e in (a, b):
            filas_tm.append((m, e, tpos[torneo_de[m]], [perf[e][k] for k in METRICAS]))
    TM_m = np.array([f[0] for f in filas_tm])
    TM_e = np.array([f[1] for f in filas_tm], dtype=object)
    TM_t = np.array([f[2] for f in filas_tm], dtype=np.int64)
    TM_V = np.array([f[3] for f in filas_tm], float)
    K = len(METRICAS)
    kk = {k: i for i, k in enumerate(METRICAS)}

    # comprobaciones preinscritas
    media_liga = {k: float(np.nanmean(TM_V[:, kk[k]])) for k in METRICAS}
    chequeos = {
        "field_tilt_media_liga": media_liga["field_tilt"],
        "npxg_favor_menos_contra": media_liga["npxg_favor"] - media_liga["npxg_contra"],
        "obv_favor_menos_contra": media_liga["obv_favor"] - media_liga["obv_contra"],
    }
    print("\n== comprobaciones ==")
    for k, x in chequeos.items():
        print(f"  {k:<28} {x:+.10f}")
    if (abs(chequeos["field_tilt_media_liga"] - 0.5) > 1e-9
            or abs(chequeos["npxg_favor_menos_contra"]) > 1e-9
            or abs(chequeos["obv_favor_menos_contra"]) > 1e-9):
        sys.exit("ABORTA: una comprobacion de simetria fallo; no se escribe nada.")
    liga_por_torneo = {}
    for t in torneos:
        s = TM_t == tpos[t]
        liga_por_torneo[t] = {k: float(np.nanmean(TM_V[s, kk[k]])) for k in METRICAS}
        liga_por_torneo[t]["equipo_partidos"] = int(s.sum())

    # medias por equipo y torneo para los percentiles
    por_eq_t = defaultdict(list)
    for i, (m, e) in enumerate(zip(TM_m, TM_e)):
        por_eq_t[(e, TM_t[i])].append(i)

    # ------------------------------------------------ por era
    filas = []
    por_club = defaultdict(list)
    for slug, club, dt in vivas:
        por_club[(slug, club)].append(dt)
    for (slug, club), dts in sorted(por_club.items()):
        base_sel = np.array([(e != club) and (club not in equipos_de[m]) for m, e in zip(TM_m, TM_e)], bool)
        bix = np.flatnonzero(base_sel)
        bt = TM_t[bix]
        rng_b = m30.semilla(args.seed, club, "__base__")
        Wb = np.empty((args.n_boot + 1, bix.size))
        Wb[0] = 1.0
        for r in range(1, args.n_boot + 1):
            w = np.zeros(bix.size)
            for ti in range(n_t):
                ix = np.flatnonzero(bt == ti)
                if ix.size:
                    w[ix] = np.bincount(rng_b.integers(0, ix.size, ix.size), minlength=ix.size)
            Wb[r] = w
        for dt in dts:
            mids = {m for m in completos if coach_de.get((m, club)) == dt}
            uix = np.flatnonzero(np.array([(e == club) and (m in mids) for m, e in zip(TM_m, TM_e)], bool))
            if uix.size == 0:
                continue
            fila = {"club": club, "coach": dt, "slug": slug, "n_partidos": int(uix.size),
                    "en_adr52": slug in CLUBES_ADR52, "en_casos": dt in casos and club in casos[dt]}
            # por torneo
            porT = {}
            for ti in sorted(set(TM_t[uix].tolist())):
                sel = uix[TM_t[uix] == ti]
                t = torneos[ti]
                parcial = sel.size < MIN_PARTIDOS_TORNEO
                d_t = {"partidos": int(sel.size), "parcial": parcial}
                for k in METRICAS:
                    val = float(np.nanmean(TM_V[sel, kk[k]])) if np.isfinite(TM_V[sel, kk[k]]).any() else float("nan")
                    d_t[k] = {"era": val, "liga": liga_por_torneo[t][k]}
                    if not parcial:
                        pobl = [float(np.nanmean(TM_V[ix_, kk[k]])) for (e, tt), ix_ in por_eq_t.items()
                                if tt == ti and e != club and len(ix_) >= MIN_PARTIDOS_TORNEO]
                        d_t[k]["percentil"] = m38.percentil(val, pobl)
                porT[t] = d_t
            fila["por_torneo"] = porT
            # global con bootstrap
            rng_u = m30.semilla(args.seed, club, dt)
            Wu = np.empty((args.n_boot + 1, uix.size))
            Wu[0] = 1.0
            for r in range(1, args.n_boot + 1):
                Wu[r] = np.bincount(rng_u.integers(0, uix.size, uix.size), minlength=uix.size)
            era, base = comparacion(TM_V[uix], TM_t[uix], Wu, TM_V[bix], bt, Wb, n_t)
            glob_ = {}
            for k in METRICAS:
                j = kk[k]
                dif = era[:, j] - base[:, j]
                ok = np.isfinite(dif[1:]).sum() > 10 and np.isfinite(dif[0])
                glob_[k] = {"era": float(era[0, j]), "liga": float(base[0, j]),
                            "dif": float(dif[0]),
                            "rel": float(dif[0] / base[0, j]) if np.isfinite(base[0, j]) and base[0, j] != 0 else None,
                            "ic95": list(m30.ic_basic(dif[1:], dif[0], args.nivel)) if ok else [None, None],
                            "replicas_validas": int(np.isfinite(dif[1:]).sum())}
            fila["global"] = glob_
            filas.append(fila)
            g = fila["global"]
            print(f"  {club:<20}{dt:<26} n={uix.size:>3}  npxG {g['npxg_favor']['dif']:+.3f}  "
                  f"OBV {g['obv_favor']['dif']:+.3f}  prog {g['prog_pases']['dif']:+.2f}  "
                  f"FT {100*g['field_tilt']['dif']:+.2f} pp  ({time.time()-t0:,.0f} s)")

    salida = {
        "adr": "D59-P (panel 5.5, descriptivo)",
        "preinscripcion": "docs/preinscritos/PANEL_55_BORRADOR.md",
        "reglas": REGLAS,
        "parametros": {"n_boot": args.n_boot, "seed": args.seed, "nivel": args.nivel,
                       "x_propio_40": X_PROPIO_40, "frac_prog": FRAC_PROG, "umbral_fijo": UMBRAL_FIJO,
                       "x_tercio": X_TERCIO, "pase_balon_parado": PASE_BALON_PARADO,
                       "min_partidos_torneo": MIN_PARTIDOS_TORNEO, "torneos": torneos,
                       "metricas": METRICAS, "principales": PRINCIPALES},
        "diagnostico": {"remates": tiros.height, "shot_type": tipos_tiro,
                        "pases": pases.height, "pass_type": {str(k): v_ for k, v_ in tipos_pase.items()},
                        "frac_pases_completados": frac_completo,
                        "pases_juego_completados": juego.height, "pases_sin_coordenadas": n_sin_coord,
                        "frac_progresivos_liga": float(juego["prog"].mean()),
                        "frac_progresivos_fijo_liga": float(juego["prog_fijo"].mean()),
                        "union_acciones_eventos": tasa_union, "chequeos": chequeos},
        "universo": {"partidos": len(completos), "excluidos_d54_12": sorted(int(m) for m in incompletos)},
        "eras_bloqueadas_por_candado": bloqueadas,
        "casos": {c: sorted(s) for c, s in casos.items()},
        "liga": {"media": media_liga, "por_torneo": liga_por_torneo},
        "unidades": filas,
        "segundos": round(time.time() - t0, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False,
                                   default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    d = salida["diagnostico"]
    print(f"\n== diagnostico ==\n  pases completados {d['frac_pases_completados']:.4f} · "
          f"progresivos (principal) {d['frac_progresivos_liga']:.4f} · (fijo) "
          f"{d['frac_progresivos_fijo_liga']:.4f} · sin coordenadas {n_sin_coord}")
    print(f"  shot_type: {tipos_tiro}")
    print(f"\nescrito {args.out}  ({salida['segundos']:,.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
