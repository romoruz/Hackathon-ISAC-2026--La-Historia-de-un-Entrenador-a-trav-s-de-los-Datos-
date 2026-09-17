#!/usr/bin/env python3
"""
33_did_presion.py — ADR-54: el bloque defensivo D1 con la deriva fuera.

Preinscrito en `docs/preinscritos/ADR-54_BORRADOR.md` (commit 2af2ab2) antes
de escribir este archivo, con las adendas 1 (commit 9aa5524) y 2.

FUENTE DE LAS ACCIONES (adendas 1 y 2, D54-10 a D54-12)
------------------------------------------------------
La VISTA DEFENSORA: la union, sobre los 18 directorios `data/processed_api_*`,
de las filas con `team != club` de cada directorio. Cada accion aparece una
sola vez, en el directorio de quien defiende, con `min_actions_defense = 1`,
la misma regla para la unidad y para la base. `data/prior_liga` usa
`min_actions = 2` y ya NO se usa aqui (bug #20). Solo entran los partidos con
sus dos lados presentes (D54-12). Todo lo que sigue implementa ese documento; donde
hubo que concretar algo que el documento no fijaba, se marca con [IMPL].

EL PROBLEMA
-----------
La tasa de presion de la liga salta por torneo de forma sincronizada
(0.192 en A2022, 0.218 en C2025). Las nulas de 18/19/20 permutan la etiqueta
de era, asi que detectan estilo MAS deriva.

EL CONTRASTE
------------
Unidad u = (club, entrenador) defendiendo: acciones reales de los rivales en
sus partidos, en el marco del club (mirror_zone, ADR-40). Base: la liga en los
mismos torneos SIN NINGUN partido del club (D54-4), estandarizada a la mezcla
(torneo x zona) de la unidad:

    D_u(S) = pi_u(S) - sum_{t,z} w_u(t,z|S) * pi_base(t,z|S)

en puntos porcentuales (D54-3). Para un par, theta = D_a - D_b.

  E1  geografia: Delta_z por zona, omnibus T = sum_z (Delta_z / se_z)^2
  E2  nivel en k >= 3
  E3  pendiente de D(k), k = 2..12, OLS ponderada por n (la de 19)
  E4  L = 1, juego abierto (open, transition)
  E5  L = 1, balon parado (restart, set_piece); fuera si pi = 0 en las dos

[IMPL] Las acciones se agregan POR PARTIDO en tablas (subconjunto x zona).
Una replica del bootstrap es una suma ponderada de esas tablas: el torneo de
cada partido es unico, asi que la estandarizacion se reconstruye exacta.

[IMPL] Celdas de base con menos de --min-celda-base acciones usan la tasa del
torneo para ese subconjunto (todas las zonas). Se cuentan y se reportan.

[IMPL] Sensibilidad logit (D54-3) para E1 (por zona, etapa 2), E2, E4 y E5.
E3 es una pendiente y no tiene version logit.

INCERTIDUMBRE (D54-5)
---------------------
Bootstrap por partido. La base se remuestrea por partido estratificado por
torneo, UNA vez por replica y por club, y la comparten todas las unidades del
club. E2-E5: IC basic y p por inversion (funciones de 30, una sola ruta).
E1: bootstrap centrado, T* = sum_z ((Delta*_z - Delta_z)/se_z)^2.

Uso:
    nohup python -u scripts/33_did_presion.py \\
        --out reports/did_presion_v1.json \\
        > logs/did_presion_v1.log 2>&1 &

    # humo rapido, a otro archivo:
    python scripts/33_did_presion.py \\
        --clubes america --n-boot 200 --out /tmp/did_presion_humo.json
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
_EPS = 1e-12

CLUBES_ADR52 = ("america", "leon", "atlas", "atletico_san_luis",
                "monterrey", "cruz_azul")
ABIERTO = ("open", "transition")
PARADO = ("restart", "set_piece")
KS = tuple(range(2, 13))                 # E3: k = 2..12, como 19 (kmin=2, kmax=12)
S_TODAS, S_K3, S_L1A, S_L1P = 0, 1, 2, 3
S_K0 = 4                                 # subconjuntos 4.. son k = 2..12
N_SUB = S_K0 + len(KS)
ESCALARES = {"E2": S_K3, "E4": S_L1A, "E5": S_L1P}

REGLAS = {
    "D54-1": "familia nueva: E1-E5 de las parejas de ADR-52, BH 5%",
    "D54-2": "zonas solo en la etapa 2, condicionadas a E1",
    "D54-3": "magnitudes en pp con pi crudo; logit como sensibilidad",
    "D54-4": "base sin ningun partido del club, estandarizada por torneo x zona",
    "D54-5": "bootstrap por partido; base compartida dentro del club",
    "D54-6": "clave compuesta (club, entrenador)",
    "D54-7": "candado H4-8 vigente",
    "D54-8": "el crudo se reporta con las mismas replicas; no es hallazgo",
    "D54-9": "sin las columnas necesarias en la liga, se aborta",
    "D54-10": "unidad y base salen de la vista defensora (min_actions_defense = 1)",
    "D54-11": "el humo con la base vieja (min_actions = 2) se descarta",
    "D54-12": "solo partidos con sus dos lados en la vista; los incompletos salen de todo",
}


# ==========================================================================
# Nucleo puro (numpy): lo prueban los tests
# ==========================================================================
def mascaras(k: np.ndarray, L: np.ndarray, fase: np.ndarray) -> list[np.ndarray]:
    """Pertenencia de cada accion a cada subconjunto, en el orden de N_SUB."""
    abierto = np.isin(fase, ABIERTO)
    parado = np.isin(fase, PARADO)
    ms = [np.ones(len(k), dtype=bool), k >= 3, (L == 1) & abierto, (L == 1) & parado]
    ms += [k == j for j in KS]
    return ms


def tabla_por_partido(mloc: np.ndarray, zona: np.ndarray, y: np.ndarray,
                      masks: list[np.ndarray], n_m: int, nz: int
                      ) -> tuple[np.ndarray, np.ndarray]:
    """N[m, s, z] acciones e Y[m, s, z] presionadas, por partido."""
    S = len(masks)
    N = np.zeros(n_m * S * nz)
    Y = np.zeros(n_m * S * nz)
    for s, ms in enumerate(masks):
        key = mloc[ms] * S * nz + s * nz + zona[ms]
        N += np.bincount(key, minlength=n_m * S * nz)
        Y += np.bincount(key, weights=y[ms].astype(float), minlength=n_m * S * nz)
    return N.reshape(n_m, S, nz), Y.reshape(n_m, S, nz)


def agrega(N: np.ndarray, Y: np.ndarray, torneo_m: np.ndarray, w: np.ndarray,
           n_t: int) -> tuple[np.ndarray, np.ndarray]:
    """Suma ponderada por partido -> tablas [t, s, z]."""
    Nt = np.zeros((n_t,) + N.shape[1:])
    Yt = np.zeros_like(Nt)
    np.add.at(Nt, torneo_m, w[:, None, None] * N)
    np.add.at(Yt, torneo_m, w[:, None, None] * Y)
    return Nt, Yt


def tasa_base(Nt: np.ndarray, Yt: np.ndarray, min_celda: float
              ) -> tuple[np.ndarray, int]:
    """pi_base[t, s, z]; celdas ralas -> tasa del torneo para ese subconjunto."""
    with np.errstate(invalid="ignore", divide="ignore"):
        celda = Yt / Nt
        nts = Nt.sum(axis=2, keepdims=True)
        torneo = np.where(nts > 0, Yt.sum(axis=2, keepdims=True) / np.maximum(nts, _EPS),
                          np.nan)
    rala = Nt < min_celda
    rate = np.where(rala, np.broadcast_to(torneo, Nt.shape), celda)
    return rate, int(rala.sum())


def resumen_unidad(Nu: np.ndarray, Yu: np.ndarray, rate: np.ndarray, nz: int
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectores (pi_u, base_u, n_u) de largo nz + N_SUB - 1.

    Posiciones: 0..nz-1 zonas (subconjunto 'todas'); despues los subconjuntos
    1..N_SUB-1 agregados sobre zonas. La base se estandariza con la mezcla
    (torneo x zona) de la unidad, que ya viene en Nu.
    """
    with np.errstate(invalid="ignore", divide="ignore"):
        contrib = np.where(Nu > 0, Nu * rate, 0.0)           # nan solo si Nu > 0
        # zonas
        nz_u = Nu[:, S_TODAS, :].sum(axis=0)
        pz = Yu[:, S_TODAS, :].sum(axis=0) / nz_u
        bz = contrib[:, S_TODAS, :].sum(axis=0) / nz_u
        # subconjuntos agregados
        ns = Nu[:, 1:, :].sum(axis=(0, 2))
        ps = Yu[:, 1:, :].sum(axis=(0, 2)) / ns
        bs = contrib[:, 1:, :].sum(axis=(0, 2)) / ns
    return (np.concatenate([pz, ps]), np.concatenate([bz, bs]),
            np.concatenate([nz_u, ns]))


def idx_sub(s: int, nz: int) -> int:
    return nz + s - 1


def pendiente_pond(y: np.ndarray, n: np.ndarray, validos: np.ndarray) -> float:
    """OLS de y contra k ponderada por n, sobre los k validos (la de 19)."""
    k = np.asarray(KS, dtype=float)[validos]
    if k.size < 3:
        return float("nan")
    w = n[validos].astype(float)
    yy = y[validos]
    if not np.all(np.isfinite(yy)):
        return float("nan")
    kb = np.average(k, weights=w)
    yb = np.average(yy, weights=w)
    return float((w * (k - kb) * (yy - yb)).sum() / max((w * (k - kb) ** 2).sum(), _EPS))


def logit(p):
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(q) - np.log1p(-q)


def omnibus(delta: np.ndarray, reps: np.ndarray, testables: np.ndarray
            ) -> tuple[float, float, int]:
    """E1: T = sum (Delta/se)^2 y su p por bootstrap centrado."""
    idx = np.flatnonzero(testables)
    if idx.size == 0:
        return float("nan"), float("nan"), 0
    R = reps[:, idx]
    ok = np.all(np.isfinite(R), axis=1)
    R = R[ok]
    se = R.std(axis=0, ddof=1)
    se = np.where(se > 0, se, np.nan)
    d = delta[idx]
    T = float(np.nansum((d / se) ** 2))
    Tb = np.nansum(((R - d) / se) ** 2, axis=1)
    p = float((1 + (Tb >= T).sum()) / (R.shape[0] + 1))
    return T, p, int(idx.size)


def partidos_completos(mid: np.ndarray, atacante: np.ndarray,
                       defensor: np.ndarray) -> tuple[set, set]:
    """D54-12: partidos con sus dos lados (dos atacantes y dos defensores)."""
    lados: dict = {}
    for m, a, d in zip(mid, atacante, defensor):
        lados.setdefault(m, set()).add((a, d))
    completos = {m for m, s in lados.items()
                 if len(s) == 2 and len({a for a, _ in s}) == 2}
    return completos, set(lados) - completos


# ==========================================================================
# Maquinaria del proyecto
# ==========================================================================
def _carga(nombre: str):
    ruta = RAIZ / "scripts" / nombre
    spec = importlib.util.spec_from_file_location(
        "m_" + nombre.replace(".py", "").replace("-", "_"), ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prior-from", default=None, dest="prior_from",
                    help="OBSOLETO desde la adenda 1: se ignora (bug #20)")
    ap.add_argument("--clubes", default=",".join(CLUBES_ADR52),
                    help="slugs de data/processed_api_<slug>")
    ap.add_argument("--datos", type=Path, default=Path("data"))
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--n-boot", type=int, default=6000, dest="n_boot")
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--nivel", type=float, default=0.95)
    ap.add_argument("--min-zona", type=int, default=100)
    ap.add_argument("--min-k", type=int, default=200)
    ap.add_argument("--min-celda-base", type=float, default=30.0)
    ap.add_argument("--sin-candado", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("reports/did_presion_v1.json"))
    args = ap.parse_args()

    if args.out.exists():
        sys.exit(f"{args.out} ya existe: escribe a un archivo NUEVO.")
    slugs = [s.strip() for s in args.clubes.split(",") if s.strip()]
    familia_adr52 = sorted(slugs) == sorted(CLUBES_ADR52)

    import polars as pl
    from dtdecoder.cli import _read_trans
    from dtdecoder.config import Config
    from dtdecoder.eras import check_verificada
    from dtdecoder.inference import benjamini_hochberg

    m08 = _carga("08_ic_derivados.py")
    m24 = _carga("24_linea_base_contemporanea.py")
    m30 = _carga("30_did_contemporaneo.py")
    sp = m08._space(Config.load(args.config))
    nph, nz = len(sp.phases), sp.nx * sp.ny
    t0 = time.time()

    # ------------------------------------------- la vista defensora (D54-10)
    if args.prior_from:
        print("AVISO: --prior-from se ignora desde la adenda 1 (bug #20).")
    necesarias = ["under_pressure", "event_index", "match_id", "action_type",
                  "team", "match_date", "poss_uid", "from_state", "phase",
                  "coach_faced"]
    partes = []
    dirs = sorted(p for p in args.datos.glob("processed_api_*")
                  if (p / "phase0_report.json").exists())
    for d in dirs:
        club_d = (json.loads((d / "phase0_report.json").read_text())
                  .get("coaches") or {}).get("club")
        t = pl.read_parquet(d / "transitions.parquet")
        faltan = [c for c in necesarias if c not in t.columns]
        if faltan or not club_d:
            sys.exit(f"D54-9: {d.name} no trae {faltan or 'club'}. No se construye la base.")
        partes.append(t.filter(pl.col("team") != club_d).select(necesarias)
                      .with_columns(pl.lit(club_d).alias("defensor")))
    if len(dirs) != 18:
        sys.exit(f"D54-10: la vista necesita los 18 directorios; hay {len(dirs)}.")
    liga = pl.concat(partes, how="vertical_relaxed")
    dup = liga.group_by(["poss_uid", "event_index"]).len().filter(pl.col("len") > 1).height
    if dup:
        sys.exit(f"D54-10: {dup} acciones aparecen en mas de un directorio.")
    ternas = liga.select("match_id", "team", "defensor").unique()
    completos, incompletos = partidos_completos(
        ternas["match_id"].to_numpy(), ternas["team"].to_numpy(), ternas["defensor"].to_numpy())
    liga = liga.filter(pl.col("match_id").is_in(sorted(completos)))
    print(f"vista defensora: {len(dirs)} directorios · {len(completos)} partidos completos · "
          f"excluidos por D54-12: {sorted(int(m) for m in incompletos)}")
    liga = liga.with_columns(m24.torneo_cols())
    n_term = int((liga["action_type"] == "TERMINAL").sum())
    real = liga.filter(pl.col("action_type") != "TERMINAL")
    nulos_real = int(real["under_pressure"].null_count())
    rep_uid = int(real.group_by("poss_uid").agg(pl.col("match_id").n_unique().alias("k"))["k"].max())
    if rep_uid > 1:
        sys.exit("poss_uid se repite entre partidos: k y L quedarian mal.")
    real = (real.sort(["poss_uid", "event_index"])
            .with_columns(
                (pl.int_range(pl.len()).over("poss_uid") + 1).alias("k"),
                pl.len().over("poss_uid").alias("L"),
                pl.col("under_pressure").fill_null(False).cast(pl.Int8).alias("presion"))
            )
    zona = sp.mirror_zone(real["from_state"].to_numpy().astype(int) // nph).astype(np.int64)
    orden_t = dict(liga.select("torneo", "torneo_orden").unique().iter_rows())
    torneos = sorted(orden_t, key=orden_t.get)
    tpos = {t: i for i, t in enumerate(torneos)}
    n_t = len(torneos)

    A_mid = real["match_id"].to_numpy()
    A_team = real["team"].to_numpy()
    A_def = real["defensor"].to_numpy()
    A_y = real["presion"].to_numpy()
    A_t = np.array([tpos[t] for t in real["torneo"].to_numpy()], dtype=np.int64)
    A_mask = mascaras(real["k"].to_numpy(), real["L"].to_numpy(), real["phase"].to_numpy())
    equipos_de = {m: set(eqs) for m, eqs in
                  liga.group_by("match_id").agg(pl.col("team").unique()).iter_rows()}
    print(f"vista: {liga.height:,} filas · {len(equipos_de)} partidos · "
          f"TERMINAL {n_term:,} · under_pressure nulo en acciones reales: {nulos_real}")
    print(f"torneos: {' '.join(torneos)}\n")

    def tablas(sel: np.ndarray):
        mids, inv = np.unique(A_mid[sel], return_inverse=True)
        N, Y = tabla_por_partido(inv, zona[sel], A_y[sel],
                                 [m[sel] for m in A_mask], len(mids), nz)
        tor = np.zeros(len(mids), dtype=np.int64)
        tor[inv] = A_t[sel]
        return mids, N, Y, tor

    unidades: dict[tuple[str, str], dict] = {}
    reps: dict[tuple[str, str], dict] = {}
    bloqueadas = []

    for slug in slugs:
        indir = args.datos / f"processed_api_{slug}"
        rp = indir / "phase0_report.json"
        if not rp.exists():
            sys.exit(f"falta {rp}")
        co = json.loads(rp.read_text()).get("coaches") or {}
        club = co["club"]
        dts = [c["coach"] for c in co.get("coverage", []) if c.get("suficiente")]
        if not args.sin_candado:
            vivos = []
            for dt in dts:
                try:
                    check_verificada(club, dt)
                    vivos.append(dt)
                except SystemExit:
                    bloqueadas.append({"club": club, "coach": dt})
            dts = vivos

        tc = _read_trans(str(indir))
        if "coach_faced" not in tc.columns:
            sys.exit(f"{indir}: sin coach_faced (phase0 con --club)")
        mapa = (liga.filter((pl.col("defensor") == club) & pl.col("coach_faced").is_not_null())
                .group_by("match_id")
                .agg(pl.col("coach_faced").n_unique().alias("n"),
                     pl.col("coach_faced").first().alias("coach")))
        if mapa["n"].max() and mapa["n"].max() > 1:
            sys.exit(f"{club}: un partido con dos entrenadores enfrentados")
        del_club = {m for m, eqs in equipos_de.items() if club in eqs}
        del_club |= set(mapa["match_id"].to_list())

        # --- base del club (D54-4)
        sel_b = ~np.isin(A_mid, np.array(sorted(del_club)))
        b_mids, bN, bY, b_tor = tablas(sel_b)
        b_por_t = [np.flatnonzero(b_tor == i) for i in range(n_t)]
        Nt0, Yt0 = agrega(bN, bY, b_tor, np.ones(len(b_mids)), n_t)
        rate0, ralas0 = tasa_base(Nt0, Yt0, args.min_celda_base)

        # --- unidades del club
        U = []
        for dt in dts:
            mids_dt = mapa.filter(pl.col("coach") == dt)["match_id"].to_numpy()
            sel_u = np.isin(A_mid, mids_dt) & (A_def == club)
            if not sel_u.any():
                continue
            u_mids, uN, uY, u_tor = tablas(sel_u)
            control = tc.filter((pl.col("team") != club)
                                & (pl.col("action_type") != "TERMINAL")
                                & (pl.col("coach_faced") == dt)
                                & pl.col("match_id").is_in(sorted(completos))).height
            Nu0, Yu0 = agrega(uN, uY, u_tor, np.ones(len(u_mids)), n_t)
            pi0, ba0, n0 = resumen_unidad(Nu0, Yu0, rate0, nz)
            w_t = Nu0[:, S_TODAS, :].sum(axis=1)
            t_medio = float((w_t * np.array([orden_t[t] for t in torneos])).sum()
                            / max(w_t.sum(), _EPS))
            U.append({"coach": dt, "N": uN, "Y": uY, "tor": u_tor,
                      "rng": m30.semilla(args.seed, club, dt),
                      "R_pi": np.full((args.n_boot, len(pi0)), np.nan),
                      "R_ba": np.full((args.n_boot, len(pi0)), np.nan),
                      "R_n": np.zeros((args.n_boot, len(pi0)), dtype=np.float32)})
            unidades[(club, dt)] = {
                "club": club, "coach": dt, "n_partidos": int(len(u_mids)),
                "n_acciones": int(sel_u.sum()),
                "n_acciones_dir_club": int(control),
                "coinciden_fuentes": bool(control == int(sel_u.sum())),
                "torneos": [t for i, t in enumerate(torneos) if w_t[i] > 0],
                "t_medio": t_medio,
                "celdas_base_ralas": ralas0,
                "_pi0": pi0, "_ba0": ba0, "_n0": n0,
            }

        # --- bootstrap (D54-5): base una vez por replica, compartida
        rng_b = m30.semilla(args.seed, club, "__base__")
        for b in range(args.n_boot):
            wb = np.zeros(len(b_mids))
            for ix in b_por_t:
                if ix.size:
                    wb[ix] = np.bincount(rng_b.integers(0, ix.size, ix.size),
                                         minlength=ix.size)
            Ntb, Ytb = agrega(bN, bY, b_tor, wb, n_t)
            rate_b, _ = tasa_base(Ntb, Ytb, args.min_celda_base)
            for u in U:
                n_m = len(u["tor"])
                wu = np.bincount(u["rng"].integers(0, n_m, n_m), minlength=n_m).astype(float)
                Nub, Yub = agrega(u["N"], u["Y"], u["tor"], wu, n_t)
                u["R_pi"][b], u["R_ba"][b], u["R_n"][b] = resumen_unidad(Nub, Yub, rate_b, nz)
        for u in U:
            reps[(club, u["coach"])] = u
            d = unidades[(club, u["coach"])]
            print(f"  {club:<20}{u['coach']:<26} partidos={d['n_partidos']:>4} "
                  f"acciones={d['n_acciones']:>6} (dir club {d['n_acciones_dir_club']:>6}) "
                  f"celdas ralas={ralas0}  ({time.time()-t0:,.0f} s)")

    # ---------------------------------------------------------------- pares
    pares = []
    por_club: dict[str, list[str]] = {}
    for c, d in unidades:
        por_club.setdefault(c, []).append(d)
    for club in sorted(por_club):
        for a, b in itertools.combinations(sorted(por_club[club]), 2):
            ua, ub = unidades[(club, a)], unidades[(club, b)]
            ra, rb = reps[(club, a)], reps[(club, b)]
            fila = {"club": club, "a": a, "b": b, "contrastes": {}}

            # E1 (omnibus) --------------------------------------------------
            Da = ua["_pi0"][:nz] - ua["_ba0"][:nz]
            Db = ub["_pi0"][:nz] - ub["_ba0"][:nz]
            testables = (ua["_n0"][:nz] >= args.min_zona) & (ub["_n0"][:nz] >= args.min_zona)
            dz = Da - Db
            Rz = (ra["R_pi"][:, :nz] - ra["R_ba"][:, :nz]) - (rb["R_pi"][:, :nz] - rb["R_ba"][:, :nz])
            T, p, nt_ = omnibus(dz, Rz, testables)
            dzc = ua["_pi0"][:nz] - ub["_pi0"][:nz]
            Rzc = ra["R_pi"][:, :nz] - rb["R_pi"][:, :nz]
            Tc, pc, _ = omnibus(dzc, Rzc, testables)
            fila["contrastes"]["E1"] = {
                "did": {"T": T, "p": p}, "crudo": {"T": Tc, "p": pc},
                "zonas_testables": nt_}
            fila["_zonas"] = (dz, Rz, dzc, Rzc, testables,
                              logit(ua["_pi0"][:nz]) - logit(ua["_ba0"][:nz])
                              - logit(ub["_pi0"][:nz]) + logit(ub["_ba0"][:nz]))

            # E2, E4, E5 ----------------------------------------------------
            for e, s in ESCALARES.items():
                i = idx_sub(s, nz)
                if e == "E5" and ua["_pi0"][i] == 0 and ub["_pi0"][i] == 0:
                    fila["contrastes"][e] = {"excluido": "pi = 0 en las dos eras"}
                    continue
                th = (ua["_pi0"][i] - ua["_ba0"][i]) - (ub["_pi0"][i] - ub["_ba0"][i])
                R = (ra["R_pi"][:, i] - ra["R_ba"][:, i]) - (rb["R_pi"][:, i] - rb["R_ba"][:, i])
                thc = ua["_pi0"][i] - ub["_pi0"][i]
                Rc = ra["R_pi"][:, i] - rb["R_pi"][:, i]
                thl = ((logit(ua["_pi0"][i]) - logit(ua["_ba0"][i]))
                       - (logit(ub["_pi0"][i]) - logit(ub["_ba0"][i])))
                Rl = ((logit(ra["R_pi"][:, i]) - logit(ra["R_ba"][:, i]))
                      - (logit(rb["R_pi"][:, i]) - logit(rb["R_ba"][:, i])))
                fila["contrastes"][e] = {
                    "did": {"theta": float(th), "ic95": list(m30.ic_basic(R, th, args.nivel)),
                            "p": m30.p_basic(R, th)},
                    "crudo": {"theta": float(thc), "ic95": list(m30.ic_basic(Rc, thc, args.nivel)),
                              "p": m30.p_basic(Rc, thc)},
                    "logit": {"theta": float(thl), "ic95": list(m30.ic_basic(Rl, thl, args.nivel)),
                              "signo_coincide": bool(np.sign(thl) == np.sign(th))},
                    "pi_a": float(ua["_pi0"][i]), "pi_b": float(ub["_pi0"][i]),
                    "base_a": float(ua["_ba0"][i]), "base_b": float(ub["_ba0"][i]),
                    "n_a": int(ua["_n0"][i]), "n_b": int(ub["_n0"][i]),
                }

            # E3 ------------------------------------------------------------
            ik = [idx_sub(S_K0 + j, nz) for j in range(len(KS))]
            va = ua["_n0"][ik] >= args.min_k
            vb = ub["_n0"][ik] >= args.min_k

            def pend(pi, ba, n, v, restar):
                return pendiente_pond(pi[ik] - (ba[ik] if restar else 0), n[ik], v)

            th = pend(ua["_pi0"], ua["_ba0"], ua["_n0"], va, True) - \
                pend(ub["_pi0"], ub["_ba0"], ub["_n0"], vb, True)
            thc = pend(ua["_pi0"], ua["_ba0"], ua["_n0"], va, False) - \
                pend(ub["_pi0"], ub["_ba0"], ub["_n0"], vb, False)
            R = np.array([pend(ra["R_pi"][j], ra["R_ba"][j], ra["R_n"][j], va, True)
                          - pend(rb["R_pi"][j], rb["R_ba"][j], rb["R_n"][j], vb, True)
                          for j in range(args.n_boot)])
            Rc = np.array([pend(ra["R_pi"][j], ra["R_ba"][j], ra["R_n"][j], va, False)
                           - pend(rb["R_pi"][j], rb["R_ba"][j], rb["R_n"][j], vb, False)
                           for j in range(args.n_boot)])
            fila["contrastes"]["E3"] = {
                "did": {"theta": th, "ic95": list(m30.ic_basic(R, th, args.nivel)),
                        "p": m30.p_basic(R, th)},
                "crudo": {"theta": thc, "ic95": list(m30.ic_basic(Rc, thc, args.nivel)),
                          "p": m30.p_basic(Rc, thc)},
                "k_validos_a": int(va.sum()), "k_validos_b": int(vb.sum()),
            }
            pares.append(fila)

    # ------------------------------------------------------ etapa 1 (D54-1)
    items = [(x, e) for x in pares for e in ("E1", "E2", "E3", "E4", "E5")
             if "did" in x["contrastes"][e] and np.isfinite(x["contrastes"][e]["did"]["p"])]
    m = len(items)
    for tipo in ("did", "crudo"):
        p = np.array([x["contrastes"][e][tipo]["p"] for x, e in items])
        q, rech = benjamini_hochberg(p, alpha=args.alpha)
        for (x, e), qi, ri in zip(items, q, rech):
            x["contrastes"][e][tipo]["q"] = float(qi)
            x["contrastes"][e][tipo]["rechaza"] = bool(ri)
    piso = 2.0 / (args.n_boot + 1)
    aviso_piso = None if piso <= args.alpha / max(m, 1) else \
        f"piso del p {piso:.5f} > alpha/m {args.alpha/m:.5f}"

    # ------------------------------------------------------ etapa 2 (D54-2)
    for x in pares:
        dz, Rz, dzc, Rzc, test, dlog = x.pop("_zonas")
        x["zonas"] = None
        if not x["contrastes"]["E1"]["did"].get("rechaza"):
            continue
        idx = np.flatnonzero(test)
        ps = np.array([m30.p_basic(Rz[:, z], dz[z]) for z in idx])
        q, rech = benjamini_hochberg(ps, alpha=args.alpha)
        x["zonas"] = [{
            "zona": int(z), "ix": int(z // sp.ny), "iy": int(z % sp.ny),
            "delta": float(dz[z]), "ic95": list(m30.ic_basic(Rz[:, z], dz[z], args.nivel)),
            "p": float(pz), "q": float(qz), "rechaza": bool(rz),
            "delta_crudo": float(dzc[z]), "delta_logit": float(dlog[z]),
            "signo_logit_coincide": bool(np.sign(dlog[z]) == np.sign(dz[z])),
        } for z, pz, qz, rz in zip(idx, ps, q, rech)]

    # ------------------------------------------------- predicciones (ADR-54)
    def par(club, x, y):
        for f in pares:
            if f["club"] == club and {f["a"], f["b"]} == {x, y}:
                return f, f["a"] != x
        return None, None

    def firma(tipo):
        n = tot = 0
        for f in pares:
            c = f["contrastes"]["E2"]
            if not c.get(tipo, {}).get("rechaza"):
                continue
            ta = unidades[(f["club"], f["a"])]["t_medio"]
            tb = unidades[(f["club"], f["b"])]["t_medio"]
            tot += 1
            n += int((c[tipo]["theta"] > 0) == (ta > tb))
        return n, tot

    pred = []
    nc, tc_ = firma("crudo"); nd, td = firma("did")
    fr = lambda n, t: (n / t) if t else None
    pred.append({"n": 1, "texto": "firma temporal de E2 entre 35% y 65% (crudo y DiD)",
                 "crudo": [nc, tc_], "did": [nd, td],
                 "cumple": (None if not tc_ or not td else
                            all(0.35 <= fr(n, t) <= 0.65 for n, t in ((nc, tc_), (nd, td))))})
    f, inv = par("América", "Andre Jardine", "Fernando Ortiz")
    if f:
        s = -1 if inv else 1
        e2 = f["contrastes"]["E2"]
        pred.append({"n": 2, "texto": "Jardine-Ortiz E2: DiD mas negativo que el crudo",
                     "did": s * e2["did"]["theta"], "crudo": s * e2["crudo"]["theta"],
                     "cumple": s * e2["did"]["theta"] < s * e2["crudo"]["theta"]})
    f, _ = par("Atlas", "Diego Cocca I", "Diego Cocca II")
    if f:
        e2 = f["contrastes"]["E2"]
        dif = abs(e2["did"]["theta"] - e2["crudo"]["theta"])
        pred.append({"n": 3, "texto": "Cocca I-II E2: |DiD - crudo| < 0.5 pp",
                     "diferencia": dif, "cumple": dif < 0.005})
    cambian = sum(x["contrastes"][e]["did"]["rechaza"] != x["contrastes"][e]["crudo"]["rechaza"]
                  for x, e in items)
    pred.append({"n": 4, "texto": "menos del 25% de la etapa 1 cambia de veredicto",
                 "cambian": cambian, "de": m,
                 "cumple": (cambian / m < 0.25) if m else None})

    for d in unidades.values():
        for k in ("_pi0", "_ba0", "_n0"):
            d.pop(k, None)
    salida = {
        "adr": "ADR-54", "preinscripcion": "docs/preinscritos/ADR-54_BORRADOR.md (commit 2af2ab2)",
        "reglas_preinscritas": REGLAS,
        "parametros": {"n_boot": args.n_boot, "seed": args.seed, "alpha": args.alpha,
                       "min_zona": args.min_zona, "min_k": args.min_k,
                       "min_celda_base": args.min_celda_base, "clubes": slugs,
                       "familia_adr52": familia_adr52, "torneos": torneos},
        "fuente": "vista defensora (D54-10)",
        "diagnostico_vista": {"filas": liga.height, "terminal": n_term,
                              "under_pressure_nulo_en_reales": nulos_real,
                              "partidos_completos": len(completos),
                              "partidos_excluidos_d54_12": sorted(int(m) for m in incompletos)},
        "aviso_piso_p": aviso_piso,
        "eras_bloqueadas_por_candado": bloqueadas,
        "n_unidades": len(unidades), "n_pares": len(pares), "m_etapa1": m,
        "n_rechaza_did": sum(x["contrastes"][e]["did"]["rechaza"] for x, e in items),
        "n_rechaza_crudo": sum(x["contrastes"][e]["crudo"]["rechaza"] for x, e in items),
        "n_cambian_veredicto": cambian,
        "predicciones": pred,
        "unidades": list(unidades.values()),
        "pares": pares,
        "segundos": round(time.time() - t0, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False,
                                   default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    print(f"\n{len(pares)} pares · etapa 1: {m} contrastes · rechazan DiD "
          f"{salida['n_rechaza_did']} · crudo {salida['n_rechaza_crudo']} · "
          f"cambian de veredicto {cambian}")
    if aviso_piso:
        print(f"AVISO: {aviso_piso}")
    if not familia_adr52:
        print("AVISO: los clubes no son la familia de ADR-52; no es el resultado preinscrito.")
    if any(not d["coinciden_fuentes"] for d in unidades.values()):
        print("AVISO: en alguna unidad la vista defensora y el directorio del club "
              "NO coinciden (ver `coinciden_fuentes`): con D54-10 deberian ser identicos.")
    print("\n== predicciones preinscritas ==")
    for p_ in pred:
        v = p_["cumple"]
        print(f"  {p_['n']}. {'CUMPLE' if v else ('n/e   ' if v is None else 'FALLA ')}  "
              f"{p_['texto']}  {json.dumps({k: p_[k] for k in p_ if k not in ('n','texto','cumple')}, default=float)}")
    print("\n== etapa 1 ==")
    for x in pares:
        cs = x["contrastes"]
        linea = []
        for e in ("E1", "E2", "E3", "E4", "E5"):
            c = cs[e]
            if "did" not in c:
                linea.append(f"{e} --"); continue
            mark = "*" if c["did"].get("rechaza") else " "
            if e == "E1":
                linea.append(f"E1 p={c['did']['p']:.4f}{mark}")
            else:
                linea.append(f"{e} {100*c['did']['theta']:+.2f}{mark}"
                             if e != "E3" else f"E3 {1000*c['did']['theta']:+.2f}‰{mark}")
        print(f"  {x['club']:<18}{x['a'][:15]:<16}vs {x['b'][:15]:<16}" + "  ".join(linea))
    print(f"\n(* = rechaza tras BH; E2/E4/E5 en pp; E3 en milésimas por toque)")
    print(f"escrito {args.out}  ({salida['segundos']:,.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
