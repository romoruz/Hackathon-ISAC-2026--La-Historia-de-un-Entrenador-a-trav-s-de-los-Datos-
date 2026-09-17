#!/usr/bin/env python3
"""
36_contexto.py — ADR-56 y ADR-57: cuanto ajusta un entrenador al contexto,
por encima de lo que ajusta la liga.

    theta = [M_u(A) - M_u(B)] - [M_L(A) - M_L(B)]

  contextos (A vs B):  localia (local vs visitante) · marcador (perdiendo vs
                       ganando) · momento (min >= 60 vs < 60) · rival (tercio
                       fuerte vs debil, por diferencia de xG sin el partido)
  metricas:            M1 acciones/posesion y M2 P(remate)/posesion del club
                       atacando; M3 pi de presion y M4 P(remate) del rival
                       (club defendiendo)

Todo se mide desde la PERSPECTIVA DEL CLUB focal: `score_state` es relativo al
equipo que ataca (sonda de contexto), asi que en las filas del rival se
invierte. Bootstrap por partido (conserva la dependencia intra-partido), base
compartida dentro del club, IC basic y p por inversion (funciones de 30).

Familias: ADR-52 (21 eras, 336 contrastes) y casos (ADR-57), con BH por
separado. `marcador_60` (marcador dentro de minuto >= 60) es sensibilidad,
fuera de las familias.

Uso:
    nohup python -u scripts/36_contexto.py --out reports/contexto_v1.json \\
        > logs/contexto_v1.log 2>&1 &
    python scripts/36_contexto.py --n-boot 200 --out /tmp/contexto_humo.json
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
_EPS = 1e-12
CLUBES_ADR52 = ("america", "leon", "atlas", "atletico_san_luis", "monterrey", "cruz_azul")
CONTEXTOS = ("localia", "marcador", "momento", "rival", "marcador_60")
FAMILIA_CONTEXTOS = CONTEXTOS[:4]
NIVELES = {"localia": ("local", "visitante"), "marcador": ("perdiendo", "ganando"),
           "momento": ("min>=60", "min<60"), "rival": ("fuerte", "debil"),
           "marcador_60": ("perdiendo", "ganando")}
METRICAS = ("M1", "M2", "M3", "M4")
# columnas de valores por registro: 0 n_pos_att 1 L_att 2 S_att 3 n_act_def 4 press_def 5 n_pos_def 6 S_def
NUM_DEN = {"M1": (1, 0), "M2": (2, 0), "M3": (4, 3), "M4": (6, 5)}
CASOS_ESPERADOS = {
    "Andre Jardine": {"América", "Atlético San Luis"}, "Fernando Ortiz": {"América", "Monterrey"},
    "Santiago Solari": {"América"}, "Nicolas Larcamon": {"Cruz Azul", "León", "Puebla"},
    "Miguel Herrera": {"Tigres UANL", "Tijuana"}, "Domenec Torrent": {"Atlético San Luis", "Monterrey"},
    "Victor Manuel Vucetich": {"Mazatlán", "Monterrey"}, "Ignacio Ambriz": {"Santos Laguna", "Toluca"},
    "Eduardo Fentanes": {"Necaxa", "Santos Laguna"}, "Veljko Paunovic": {"Guadalajara", "Tigres UANL"},
    "Benjamin Mora": {"Atlas", "Querétaro"}, "Benat San Jose": {"Atlas", "Mazatlán"},
}
REGLAS = {
    "D56": "theta = ajuste de la unidad menos ajuste de la liga en el mismo contexto",
    "D56-bootstrap": "por partido, base estratificada por torneo y compartida en el club; B=16000 (adenda 1)",
    "D56-familia": "M1-M4 x 4 contextos x 21 eras de ADR-52, BH 5%",
    "D57-1": "casos: America + entrenadores con >= 2 eras analizables en clubes distintos",
    "D57-2": "familia casos separada, BH 5%",
    "sensibilidad": "marcador_60 fuera de las familias",
}


# ==========================================================================
# Nucleo puro
# ==========================================================================
def invierte_marcador(s: str | None) -> str | None:
    return {"winning": "losing", "losing": "winning"}.get(s, s)


def nivel_marcador(s: str | None) -> int:
    """0 = perdiendo (A), 1 = ganando (B), 2 = otro (empate / nulo)."""
    return {"losing": 0, "winning": 1}.get(s, 2)


def nivel_momento(minuto) -> int:
    if minuto is None or (isinstance(minuto, float) and np.isnan(minuto)):
        return 2
    return 0 if minuto >= 60 else 1


def tercios(medias: dict) -> tuple[float, float]:
    v = np.array(sorted(medias.values()), float)
    return float(np.quantile(v, 1 / 3)), float(np.quantile(v, 2 / 3))


def nivel_rival(xgd_loo: float, corte: tuple[float, float]) -> int:
    """0 = fuerte (tercio superior), 1 = debil (inferior), 2 = medio / sin dato."""
    if xgd_loo is None or not np.isfinite(xgd_loo):
        return 2
    if xgd_loo >= corte[1]:
        return 0
    if xgd_loo <= corte[0]:
        return 1
    return 2


def media_sin(valores: dict, excluir) -> float:
    """Media de {partido: valor} sin el partido `excluir` (leave-one-out)."""
    v = [x for m, x in valores.items() if m != excluir]
    return float(np.mean(v)) if v else float("nan")


def totales(vals: np.ndarray, key: np.ndarray, w: np.ndarray, n_key: int) -> np.ndarray:
    """Sumas ponderadas por clave: (7, n_key)."""
    return np.stack([np.bincount(key, weights=w * vals[:, j], minlength=n_key)
                     for j in range(vals.shape[1])])


def ajuste(T_u: np.ndarray, T_b: np.ndarray, k: int, metrica: str, n_t: int
           ) -> tuple[float, float, float]:
    """(ajuste unidad, ajuste base estandarizada, theta) para el contexto k.

    T_*: (7, n_ctx*3*n_t) con clave (k*3 + nivel)*n_t + t.
    La base de cada nivel se pondera con la mezcla por torneo de la UNIDAD en
    ese nivel (denominador de la metrica).
    """
    num, den = NUM_DEN[metrica]
    res = []
    for j in (0, 1):
        sl = slice((k * 3 + j) * n_t, (k * 3 + j + 1) * n_t)
        nu, du = T_u[num, sl], T_u[den, sl]
        nb, db = T_b[num, sl], T_b[den, sl]
        if du.sum() <= 0:
            res.append((float("nan"), float("nan")))
            continue
        ru = nu.sum() / du.sum()
        with np.errstate(invalid="ignore", divide="ignore"):
            rb_t = np.where(db > 0, nb / db, np.nan)
        w = du / du.sum()
        if np.any((w > 0) & ~np.isfinite(rb_t)):
            res.append((float(ru), float("nan")))
            continue
        res.append((float(ru), float(np.nansum(np.where(w > 0, w * rb_t, 0.0)))))
    au = res[0][0] - res[1][0]
    ab = res[0][1] - res[1][1]
    return float(au), float(ab), float(au - ab)


def ajuste_vec(TU: np.ndarray, TB: np.ndarray, k: int, metrica: str, n_t: int):
    """`ajuste` vectorizado sobre replicas: TU, TB de forma (R, 7, n_key)."""
    num, den = NUM_DEN[metrica]
    partes = []
    for j in (0, 1):
        sl = slice((k * 3 + j) * n_t, (k * 3 + j + 1) * n_t)
        nu, du = TU[:, num, sl], TU[:, den, sl]
        nb, db = TB[:, num, sl], TB[:, den, sl]
        dus = du.sum(axis=1)
        pos_ = dus > 0
        with np.errstate(invalid="ignore", divide="ignore"):
            ru = np.where(pos_, nu.sum(axis=1) / np.where(pos_, dus, 1.0), np.nan)
            rb = np.where(db > 0, nb / np.where(db > 0, db, 1.0), np.nan)
            w = du / np.where(pos_, dus, 1.0)[:, None]
        malo = ((w > 0) & ~np.isfinite(rb)).any(axis=1) | ~pos_
        base = np.where(w > 0, w * np.nan_to_num(rb), 0.0).sum(axis=1)
        partes.append((ru, np.where(malo, np.nan, base)))
    au = partes[0][0] - partes[1][0]
    ab = partes[0][1] - partes[1][1]
    return au, ab, au - ab


def casos_desde(unidades: list[tuple[str, str]]) -> dict:
    """D57-1: {coach: {clubes}} para America + entrenadores en >= 2 clubes."""
    por: dict = {}
    for club, coach in unidades:
        por.setdefault(coach, set()).add(club)
    return {c: s for c, s in por.items() if len(s) >= 2 or "América" in s}


# ==========================================================================
def _carga(nombre: str):
    spec = importlib.util.spec_from_file_location("m_" + nombre[:2] + "_ctx", RAIZ / "scripts" / nombre)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=Path("data"))
    ap.add_argument("--eventos", type=Path, default=Path("data/api/eventos_api_ligamx"))
    ap.add_argument("--indice", type=Path, default=Path("data/raw_api/indice_partidos.csv"))
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--n-boot", type=int, default=16000, dest="n_boot")  # ADR-56 adenda 1
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=Path("reports/contexto_v1.json"))
    args = ap.parse_args()
    if args.out.exists():
        sys.exit(f"{args.out} ya existe: escribe a un archivo NUEVO.")

    import polars as pl
    from dtdecoder.config import Config
    from dtdecoder.eras import check_verificada
    from dtdecoder.inference import benjamini_hochberg

    m08 = _carga("08_ic_derivados.py")
    m24 = _carga("24_linea_base_contemporanea.py")
    m30 = _carga("30_did_contemporaneo.py")
    m33 = _carga("33_did_presion.py")
    sp = m08._space(Config.load(args.config))
    gol = sp.n_transient + list(sp.absorbing).index("GOAL")
    tiro = sp.n_transient + list(sp.absorbing).index("SHOT_NOGOAL")
    t0 = time.time()

    # ------------------------------------------------ vista defensora
    cols = ["poss_uid", "match_id", "team", "event_index", "action_type", "under_pressure",
            "score_state", "to_state", "match_date", "coach_faced"]
    dirs = sorted(p for p in args.datos.glob("processed_api_*") if (p / "phase0_report.json").exists())
    if len(dirs) != 18:
        sys.exit(f"hacen falta los 18 directorios; hay {len(dirs)}")
    partes, unidades_rep = [], []
    for d in dirs:
        rep = json.loads((d / "phase0_report.json").read_text()).get("coaches") or {}
        club = rep["club"]
        partes.append(pl.read_parquet(d / "transitions.parquet", columns=cols)
                      .filter(pl.col("team") != club).with_columns(pl.lit(club).alias("defensor")))
        for c in rep.get("coverage", []):
            if c.get("suficiente"):
                unidades_rep.append((d.name.replace("processed_api_", ""), club, c["coach"]))
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
    print(f"vista: {v.height:,} filas · {len(completos)} partidos · excluidos D54-12: "
          f"{sorted(int(m) for m in incompletos)}")

    # ------------------------------------------------ posesiones
    pos = (v.sort(["poss_uid", "event_index"]).group_by("poss_uid", maintain_order=True)
           .agg(pl.col("match_id").first(), pl.col("team").first().alias("atacante"),
                pl.col("defensor").first(),
                pl.col("score_state").first(),
                (pl.col("action_type") != "TERMINAL").sum().alias("L"),
                pl.col("to_state").is_in([gol, tiro]).any().cast(pl.Int8).alias("S"),
                ((pl.col("action_type") != "TERMINAL")
                 & pl.col("under_pressure").fill_null(False)).sum().alias("press"))
           .with_columns(pl.col("poss_uid").str.split("_").list.last()
                         .cast(pl.Int64, strict=False).alias("possession")))
    minutos = (pl.scan_parquet(sorted(glob.glob(str(args.eventos / "*.parquet"))))
               .filter(pl.col("match_id").is_in(sorted(completos)))
               .group_by(["match_id", "possession"]).agg(pl.col("minute").min().alias("minuto"))
               .collect())
    pos = pos.join(minutos, on=["match_id", "possession"], how="left")
    print(f"posesiones: {pos.height:,} · con minuto: {pos['minuto'].is_not_null().mean():.4f}")

    # ------------------------------------------------ localia y rival
    idx = pl.read_csv(args.indice, infer_schema_length=None)
    local_de = dict(idx.select("match_id", "home_team").iter_rows())
    xg = (pl.scan_parquet(sorted(glob.glob(str(args.eventos / "*.parquet"))))
          .filter((pl.col("type") == "Shot") & pl.col("match_id").is_in(sorted(completos)))
          .group_by(["match_id", "team"]).agg(pl.col("shot_statsbomb_xg").sum().alias("xg"))
          .collect())
    xg_de = {(m, t): float(x or 0.0) for m, t, x in xg.iter_rows()}
    xgd: dict = {}                       # (equipo, torneo) -> {partido: xg propio - xg rival}
    for m, eqs in equipos_de.items():
        a, b = sorted(eqs)
        for e, o in ((a, b), (b, a)):
            xgd.setdefault((e, torneo_de[m]), {})[m] = xg_de.get((m, e), 0.0) - xg_de.get((m, o), 0.0)
    cortes = {}
    for t in torneos:
        medias = {e: float(np.mean(list(d_.values()))) for (e, tt), d_ in xgd.items() if tt == t}
        cortes[t] = tercios(medias)

    cache_riv: dict = {}

    def nivel_rival_de(m, rival):
        if (m, rival) not in cache_riv:
            t = torneo_de[m]
            cache_riv[(m, rival)] = nivel_rival(media_sin(xgd.get((rival, t), {}), m), cortes[t])
        return cache_riv[(m, rival)]

    # ------------------------------------------------ registros por perspectiva
    # para cada (partido, equipo focal F): filas por (contexto, nivel) con 7 valores
    P = pos.select("match_id", "atacante", "defensor", "score_state", "L", "S", "press", "minuto").to_numpy()
    reg: dict = {}

    def suma(m, F, k, j, vals):
        a = reg.setdefault((m, F, k, j), np.zeros(7))
        a += vals

    for m, atac, dfn, ss, L, S, press, minuto in P:
        if m not in equipos_de:
            continue
        L, S, press = float(L), float(S), float(press)
        mom = nivel_momento(minuto)
        for F, rival, lado in ((atac, dfn, "att"), (dfn, atac, "def")):
            ss_F = ss if lado == "att" else invierte_marcador(ss)
            vals = (np.array([1, L, S, 0, 0, 0, 0], float) if lado == "att"
                    else np.array([0, 0, 0, L, press, 1, S], float))
            niveles = {
                0: 0 if local_de.get(m) == F else 1,
                1: nivel_marcador(ss_F),
                2: mom,
                3: nivel_rival_de(m, rival),
                4: nivel_marcador(ss_F) if mom == 0 else 2,
            }
            for k, j in niveles.items():
                suma(m, F, k, j, vals)
    claves = list(reg.keys())
    R_val = np.array([reg[c] for c in claves])
    R_m = np.array([c[0] for c in claves])
    R_F = np.array([c[1] for c in claves], dtype=object)
    R_key = np.array([(c[2] * 3 + c[3]) * n_t + tpos[torneo_de[c[0]]] for c in claves], dtype=np.int64)
    N_KEY = len(CONTEXTOS) * 3 * n_t
    print(f"registros: {len(claves):,} ({time.time()-t0:,.0f} s)")

    # ------------------------------------------------ liga (predicciones 1-4)
    T_all = totales(R_val, R_key, np.ones(len(claves)), N_KEY)
    def tasa_liga(k, j, metrica):
        num, den = NUM_DEN[metrica]
        sl = slice((k * 3 + j) * n_t, (k * 3 + j + 1) * n_t)
        return float(T_all[num, sl].sum() / max(T_all[den, sl].sum(), _EPS))
    liga = {c: {mt: {NIVELES[c][0]: tasa_liga(k, 0, mt), NIVELES[c][1]: tasa_liga(k, 1, mt),
                     "otro": tasa_liga(k, 2, mt)} for mt in METRICAS}
            for k, c in enumerate(CONTEXTOS)}

    # ------------------------------------------------ unidades y casos
    unidades, bloqueadas = [], []
    for slug, club, dt in unidades_rep:
        try:
            check_verificada(club, dt)
            unidades.append((slug, club, dt))
        except SystemExit:
            bloqueadas.append({"club": club, "coach": dt})
    casos = casos_desde([(c, e) for _, c, e in unidades])
    dif_casos = {c: (sorted(casos.get(c, [])), sorted(CASOS_ESPERADOS.get(c, [])))
                 for c in set(casos) | set(CASOS_ESPERADOS) if casos.get(c) != CASOS_ESPERADOS.get(c)}
    if dif_casos:
        print(f"AVISO D57-1: los casos calculados difieren de la tabla del ADR (manda el calculo): {dif_casos}")
    en_casos = lambda club, dt: dt in casos and club in casos[dt]

    partidos = sorted(completos)
    reps: dict = {}
    filas = []
    por_club: dict = {}
    for slug, club, dt in unidades:
        por_club.setdefault((slug, club), []).append(dt)
    for (slug, club), dts in sorted(por_club.items()):
        base_m = np.array([m for m in partidos if club not in equipos_de[m]])
        base_set = set(base_m.tolist())
        sel_b = np.array([m in base_set for m in R_m])
        bv, bk, bm = R_val[sel_b], R_key[sel_b], R_m[sel_b]
        bidx = {m: i for i, m in enumerate(base_m)}
        brow = np.array([bidx[m] for m in bm], dtype=np.int64)
        bt = np.array([tpos[torneo_de[m]] for m in base_m])
        rng_b = m30.semilla(args.seed, club, "__base__")
        Wb = [np.ones(len(base_m))]
        for _ in range(args.n_boot):
            w = np.zeros(len(base_m))
            for t in range(n_t):
                ix = np.flatnonzero(bt == t)
                if ix.size:
                    w[ix] = np.bincount(rng_b.integers(0, ix.size, ix.size), minlength=ix.size)
            Wb.append(w)
        TB = np.stack([totales(bv, bk, w[brow], N_KEY) for w in Wb])
        for dt in dts:
            mids = [m for m in partidos if coach_de.get((m, club)) == dt]
            if not mids:
                continue
            ms = set(mids)
            sel_u = np.array([(m in ms) and (F == club) for m, F in zip(R_m, R_F)])
            uv, uk, um = R_val[sel_u], R_key[sel_u], R_m[sel_u]
            uidx = {m: i for i, m in enumerate(mids)}
            urow = np.array([uidx[m] for m in um], dtype=np.int64)
            rng_u = m30.semilla(args.seed, club, dt)
            Wu = [np.ones(len(mids))] + [
                np.bincount(rng_u.integers(0, len(mids), len(mids)), minlength=len(mids)).astype(float)
                for _ in range(args.n_boot)]
            TU = np.stack([totales(uv, uk, w[urow], N_KEY) for w in Wu])
            fila = {"club": club, "coach": dt, "slug": slug, "n_partidos": len(mids),
                    "en_adr52": slug in CLUBES_ADR52, "en_casos": en_casos(club, dt),
                    "contrastes": {}, "tasas": {}}
            for k, c in enumerate(CONTEXTOS):
                for mt in METRICAS:
                    au, ab, TH = ajuste_vec(TU, TB, k, mt, n_t)
                    th = float(TH[0])
                    ok = np.isfinite(th) and np.isfinite(TH[1:]).sum() > 10
                    fila["contrastes"][f"{c}|{mt}"] = {
                        "ajuste_unidad": float(au[0]), "ajuste_liga": float(ab[0]), "theta": th,
                        "ic95": list(m30.ic_basic(TH[1:], th)) if ok else [None, None],
                        "p": m30.p_basic(TH[1:], th) if ok else float("nan"),
                        "familia": c in FAMILIA_CONTEXTOS}
                    num, den = NUM_DEN[mt]
                    for j, nom in enumerate(NIVELES[c] + ("otro",)):
                        sl = slice((k * 3 + j) * n_t, (k * 3 + j + 1) * n_t)
                        d_ = TU[0, den, sl].sum()
                        fila["tasas"][f"{c}|{mt}|{nom}"] = (float(TU[0, num, sl].sum() / d_) if d_ > 0 else None)
            filas.append(fila)
            th1 = fila["contrastes"]["marcador|M1"]["theta"]
            print(f"  {club:<20}{dt:<26} n={len(mids):>3}  marcador·M1 {th1:+.3f}  "
                  f"localia·M2 {100*fila['contrastes']['localia|M2']['theta']:+.2f} pp  "
                  f"({time.time()-t0:,.0f} s)")

    # ------------------------------------------------ familias
    resumen_fam = {}
    for nom_f, clave in (("adr52", "en_adr52"), ("casos", "en_casos")):
        items = [(f, k) for f in filas if f[clave] for k, c in f["contrastes"].items()
                 if c["familia"] and np.isfinite(c["p"])]
        m = len(items)
        if not m:
            resumen_fam[nom_f] = {"m": 0}
            continue
        q, rech = benjamini_hochberg(np.array([f["contrastes"][k]["p"] for f, k in items]), alpha=args.alpha)
        for (f, k), qi, ri in zip(items, q, rech):
            f["contrastes"][k][f"q_{nom_f}"] = float(qi)
            f["contrastes"][k][f"rechaza_{nom_f}"] = bool(ri)
        piso = 2.0 / (args.n_boot + 1)
        resumen_fam[nom_f] = {
            "m": m, "rechazan": int(rech.sum()),
            "aviso_piso_p": (None if piso <= args.alpha / m else
                             f"piso del p {piso:.5f} > alpha/m {args.alpha/m:.5f}: un contraste aislado no puede rechazar"),
            "por_contexto": {c: int(sum(ri and k.startswith(c + "|") for (f, k), ri in zip(items, rech)))
                             for c in FAMILIA_CONTEXTOS}}

    # ------------------------------------------------ predicciones
    L_ = liga
    rf = resumen_fam.get("adr52", {})
    pc = rf.get("por_contexto", {})
    mas_frec = max(pc, key=pc.get) if pc and sum(pc.values()) else None
    viaja = []
    for c, clubes in casos.items():
        if len(clubes) < 2:
            continue
        signos = {np.sign(f["contrastes"]["marcador|M1"]["theta"]) for f in filas
                  if f["coach"] == c and f["club"] in clubes and np.isfinite(f["contrastes"]["marcador|M1"]["theta"])}
        viaja.append((c, len(signos) == 1))
    pred = [
        {"adr": 56, "n": 1, "texto": "liga: M1 perdiendo > ganando",
         "valor": [L_["marcador"]["M1"]["perdiendo"], L_["marcador"]["M1"]["ganando"]],
         "cumple": L_["marcador"]["M1"]["perdiendo"] > L_["marcador"]["M1"]["ganando"]},
        {"adr": 56, "n": 2, "texto": "liga: presion (M3) del que defiende perdiendo > ganando",
         "valor": [L_["marcador"]["M3"]["perdiendo"], L_["marcador"]["M3"]["ganando"]],
         "cumple": L_["marcador"]["M3"]["perdiendo"] > L_["marcador"]["M3"]["ganando"]},
        {"adr": 56, "n": 3, "texto": "liga: M2 local > visitante",
         "valor": [L_["localia"]["M2"]["local"], L_["localia"]["M2"]["visitante"]],
         "cumple": L_["localia"]["M2"]["local"] > L_["localia"]["M2"]["visitante"]},
        {"adr": 56, "n": 4, "texto": "liga: M2 min>=60 > min<60",
         "valor": [L_["momento"]["M2"]["min>=60"], L_["momento"]["M2"]["min<60"]],
         "cumple": L_["momento"]["M2"]["min>=60"] > L_["momento"]["M2"]["min<60"]},
        {"adr": 56, "n": 5, "texto": "a lo sumo 20 de 336 rechazan (ADR-52)",
         "valor": [rf.get("rechazan"), rf.get("m")], "cumple": (rf.get("rechazan") or 0) <= 20},
        {"adr": 56, "n": 6, "texto": "entre los rechazos, el contexto mas frecuente es el marcador",
         "valor": pc, "cumple": (None if mas_frec is None else mas_frec == "marcador")},
        {"adr": 57, "n": 1, "texto": "al menos 6 de 9 entrenadores de varios clubes: mismo signo en marcador|M1",
         "valor": [sum(x for _, x in viaja), len(viaja)],
         "cumple": (None if not viaja else sum(x for _, x in viaja) >= 6)},
    ]

    salida = {"adr": ["ADR-56", "ADR-57"], "reglas": REGLAS,
              "parametros": {"n_boot": args.n_boot, "seed": args.seed, "torneos": torneos,
                             "cortes_rival": cortes},
              "universo": {"partidos": len(completos), "excluidos_d54_12": sorted(int(m) for m in incompletos)},
              "eras_bloqueadas_por_candado": bloqueadas,
              "casos": {c: sorted(s) for c, s in casos.items()}, "casos_difieren_del_adr": dif_casos,
              "liga": liga, "familias": resumen_fam, "predicciones": pred,
              "viaja_marcador_M1": dict(viaja),
              "unidades": filas, "segundos": round(time.time() - t0, 1)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False,
                                   default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("\n== familias ==")
    for k, r in resumen_fam.items():
        print(f"  {k}: {r}")
    print("\n== predicciones preinscritas ==")
    for p_ in pred:
        v_ = p_["cumple"]
        print(f"  ADR-{p_['adr']} P{p_['n']}. {'CUMPLE' if v_ else ('n/e   ' if v_ is None else 'FALLA ')}  "
              f"{p_['texto']}  {json.dumps(p_['valor'], default=float)}")
    print(f"\nescrito {args.out}  ({salida['segundos']:,.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
