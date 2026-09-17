#!/usr/bin/env python3
"""
38_jugadores.py — ADR-58: uso de jugadores.

Preinscrito en `docs/preinscritos/ADR-58_BORRADOR.md` (commit db715ef) antes de
escribir este archivo. Lo que el documento no fijaba se marca [IMPL].

  A  nucleo y rotacion (descriptivo): N80, continuidad del once, jugadores
     distintos, cambios tacticos por partido; percentil en la liga del torneo
  B  roles (descriptivo): posicion modal y zonas de accion, >= 450 minutos
  C  tras el primer cambio tactico (min 55-80): Delta = despues - antes en
     ventanas de 10 min con exclusion de +-60 s; theta = Delta de la era -
     Delta de la liga en el mismo estrato (bloque x marcador x torneo)

[IMPL] Reloj de `positions`: se detecta si `from`/`to` son acumulados o
       relativos al periodo, y se imprime la decision.
[IMPL] A: los torneos con menos de 12 partidos de la era se reportan marcados
       como parciales y NO entran al percentil (N80 depende del numero de
       partidos).
[IMPL] C: los estratos de la era sin eventos de liga se descartan y se
       renormaliza; se reporta la fraccion descartada.
[IMPL] C: el marcador del equipo al cambio es el de la ultima posesion que
       empezo antes del cambio, desde la perspectiva del equipo.
[IMPL] FT usa la x del evento (marco del equipo que ejecuta, D-contrato).
[IMPL] Sensibilidad por lesion: el primer cambio por lesion del partido, si cae
       en la misma franja.

Uso:
    nohup python -u scripts/38_jugadores.py --out reports/jugadores_v1.json \\
        > logs/jugadores_v1.log 2>&1 &
    python scripts/38_jugadores.py --n-boot 200 --out /tmp/jugadores_humo.json
"""
from __future__ import annotations

import argparse
import glob
import gzip
import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
_EPS = 1e-12
CLUBES_ADR52 = ("america", "leon", "atlas", "atletico_san_luis", "monterrey", "cruz_azul")
METRICAS = ("M1", "M2", "M4", "FT")
VENT, EXCL = 600.0, 60.0                 # 10 min de ventana, 60 s de exclusion
T_MIN, T_MAX = 600.0, 2100.0             # 10:00 a 35:00 del segundo tiempo
BLOQUES = (600.0, 1080.0, 1560.0)        # 10:00, 18:00, 26:00
MIN_PARTIDOS_TORNEO = 12
MIN_MINUTOS_ROL = 450.0
REGLAS = {
    "D58-A": "nucleo y rotacion descriptivos, percentil en la liga del mismo torneo",
    "D58-B": "roles descriptivos, jugadores con >= 450 minutos",
    "D58-C": "primer cambio tactico 10:00-35:00 del 2T; ventanas 10 min con exclusion 60 s; "
             "theta = Delta era - Delta liga en el estrato (bloque x marcador x torneo)",
    "D58-familias": "{M1,M2,M4,FT} x eras: ADR-52 y casos, BH 5% por separado",
    "D58-redaccion": "tras sus primeros cambios, el equipo...; nunca causal",
}


# ==========================================================================
# Nucleo puro
# ==========================================================================
def seg(ts) -> float:
    if ts is None:
        return float("nan")
    partes = str(ts).split(":")
    v = 0.0
    for p in partes:
        v = v * 60 + float(p)
    return v


def detecta_reloj(muestras: list[tuple[int, float]]) -> str:
    """muestras: (from_period, from_segundos) de entradas en el 2T."""
    s2 = [s for p, s in muestras if p == 2]
    if not s2:
        return "desconocido"
    return "acumulado" if np.mean(np.array(s2) >= 45 * 60) > 0.5 else "periodo"


def minutos_jugados(pos: list[dict], fin_periodo: dict, reloj: str) -> float:
    """Minutos de un jugador en un partido a partir de sus `positions`."""
    total = 0.0
    ultimo = max(fin_periodo)
    for x in pos:
        fp = int(x.get("from_period") or 1)
        tp = int(x.get("to_period") or ultimo)
        f = seg(x.get("from"))
        if reloj == "acumulado":
            # el reloj acumulado reinicia cada periodo en 45:00 x (periodo - 1)
            fin = 45 * 60 * (ultimo - 1) + fin_periodo[ultimo]
            t = seg(x["to"]) if x.get("to") is not None else fin
            total += max(t - f, 0.0)
        else:
            t = seg(x["to"]) if x.get("to") is not None else fin_periodo[tp]
            if fp == tp:
                total += max(t - f, 0.0)
            else:
                total += max(fin_periodo[fp] - f, 0.0)
                total += sum(fin_periodo[p] for p in range(fp + 1, tp) if p in fin_periodo)
                total += max(t, 0.0)
    return total / 60.0


def n80(minutos) -> int:
    v = np.sort(np.asarray(list(minutos), float))[::-1]
    if v.sum() <= 0:
        return 0
    return int(np.searchsorted(np.cumsum(v) / v.sum(), 0.8 - 1e-12) + 1)


def continuidad(onces: list[set]) -> float:
    """Fraccion media del once que se repite respecto al partido anterior."""
    v = [len(a & b) / max(len(b), 1) for a, b in zip(onces[:-1], onces[1:])]
    return float(np.mean(v)) if v else float("nan")


def percentil(valor: float, poblacion) -> float:
    p = np.asarray([x for x in poblacion if np.isfinite(x)], float)
    if p.size == 0 or not np.isfinite(valor):
        return float("nan")
    return float((np.sum(p < valor) + 0.5 * np.sum(p == valor)) / p.size)


def bloque(t: float) -> int:
    return int(np.searchsorted(BLOQUES, t, side="right") - 1)


def marcador_idx(s) -> int | None:
    return {"losing": 0, "drawing": 1, "winning": 2}.get(s)


def tasa_ventana(t_ini: np.ndarray, num: np.ndarray, den: np.ndarray, lo: float, hi: float,
                 cerrado_izq: bool) -> float:
    """sum(num)/sum(den) para eventos con tiempo en [lo, hi) o (lo, hi]."""
    m = ((t_ini >= lo) & (t_ini < hi)) if cerrado_izq else ((t_ini > lo) & (t_ini <= hi))
    d = den[m].sum()
    return float(num[m].sum() / d) if d > 0 else float("nan")


def ventanas(t: float, excl: float = EXCL) -> tuple[tuple[float, float], tuple[float, float]]:
    antes = (max(t - excl - VENT, 0.0), t - excl)
    despues = (t + excl, t + excl + VENT)
    return antes, despues


def theta_estratificado(D_era: np.ndarray, w_era: np.ndarray, s_era: np.ndarray,
                        D_base: np.ndarray, w_base: np.ndarray, s_base: np.ndarray,
                        n_s: int) -> tuple[float, float, float, float]:
    """(media era, liga estandarizada, theta, fraccion de peso descartada).

    D_*: Delta por evento (nan = no valido). Pesos por evento (bootstrap).
    """
    ve, vb = np.isfinite(D_era) & (w_era > 0), np.isfinite(D_base) & (w_base > 0)
    if not ve.any():
        return (float("nan"),) * 4
    me = float(np.sum(w_era[ve] * D_era[ve]) / np.sum(w_era[ve]))
    nb = np.bincount(s_base[vb], weights=w_base[vb], minlength=n_s)
    sb = np.bincount(s_base[vb], weights=w_base[vb] * D_base[vb], minlength=n_s)
    pe = np.bincount(s_era[ve], weights=w_era[ve], minlength=n_s)
    ok = (pe > 0) & (nb > 0)
    if not ok.any():
        return me, float("nan"), float("nan"), 1.0
    desc = float(pe[~ok].sum() / pe.sum())
    pi = pe[ok] / pe[ok].sum()
    mb = float(np.sum(pi * sb[ok] / nb[ok]))
    return me, mb, me - mb, desc


# ==========================================================================
def _carga(nombre: str):
    spec = importlib.util.spec_from_file_location("m_" + nombre[:2] + "_jug", RAIZ / "scripts" / nombre)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lee_json(p: Path):
    txt = gzip.open(p, "rt").read() if p.suffix == ".gz" else p.read_text()
    return json.loads(txt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=Path("data"))
    ap.add_argument("--eventos", type=Path, default=Path("data/api/eventos_api_ligamx"))
    ap.add_argument("--lineups", type=Path, default=Path("data/raw_api/lineups"))
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--n-boot", type=int, default=6000, dest="n_boot")
    ap.add_argument("--seed", type=int, default=20260918)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=Path("reports/jugadores_v1.json"))
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
    m36 = _carga("36_contexto.py")
    sp = m08._space(Config.load(args.config))
    nph, n_tr = len(sp.phases), sp.n_transient
    gol = n_tr + list(sp.absorbing).index("GOAL")
    tiro = n_tr + list(sp.absorbing).index("SHOT_NOGOAL")
    t0 = time.time()

    # ------------------------------------------------ vista y universo
    cols = ["poss_uid", "match_id", "team", "event_index", "action_type", "score_state",
            "from_state", "to_state", "match_date", "coach_faced", "player_id"]
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
    torneo_de = dict(v.select("match_id", "torneo").unique().iter_rows())
    fecha_de = dict(v.select("match_id", "match_date").unique().iter_rows())
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
    lf = pl.scan_parquet(sorted(glob.glob(str(args.eventos / "*.parquet")))) \
        .filter(pl.col("match_id").is_in(sorted(completos)))
    nombre_eq = dict(lf.select("team_id", "team").unique().collect().iter_rows())
    fin_per = {(m, p): seg(ts) for m, p, ts in
               lf.group_by(["match_id", "period"]).agg(pl.col("timestamp").max()).collect().iter_rows()}
    subs = (lf.filter(pl.col("type") == "Substitution")
            .select("match_id", "team", "period", "timestamp", "substitution_outcome", "index")
            .sort(["match_id", "period", "timestamp", "index"]).collect())
    shifts = (lf.filter(pl.col("type") == "Tactical Shift").group_by(["match_id", "team"]).len().collect())
    shifts_de = {(m, t): n for m, t, n in shifts.iter_rows()}
    ini_pos = (lf.group_by(["match_id", "possession"])
               .agg(pl.col("period").sort_by("index").first(), pl.col("timestamp").sort_by("index").first())
               .collect())
    acciones = (v.filter(pl.col("action_type") != "TERMINAL")
                .select("match_id", "team", "event_index")
                .join(lf.select("match_id", pl.col("index").alias("event_index"), "period", "timestamp", "location")
                      .collect(), on=["match_id", "event_index"], how="left"))
    tasa_union = float(acciones["timestamp"].is_not_null().mean())
    acciones = acciones.filter(pl.col("timestamp").is_not_null()).with_columns(
        pl.col("location").str.strip_chars("[]").str.split(",").list.get(0).cast(pl.Float64).alias("x"))
    print(f"eventos: {subs.height:,} sustituciones · union acciones-eventos {tasa_union:.4f} "
          f"({time.time()-t0:,.0f} s)")

    # ------------------------------------------------ A · alineaciones y minutos
    muestras, xi = [], {}
    minutos = defaultdict(lambda: defaultdict(float))    # minutos[equipo][(m, jugador)]
    posicion_min = defaultdict(Counter)                    # (equipo, jugador) -> {posicion: min}
    archivos = {int(Path(p).name.split(".")[0]): Path(p) for p in glob.glob(str(args.lineups / "*"))}
    lineups = {}
    for m in completos:
        if m not in archivos:
            continue
        lineups[m] = lee_json(archivos[m])
        for eq in (lineups[m].values() if isinstance(lineups[m], dict) else lineups[m]):
            for j in eq["lineup"]:
                for x in j.get("positions") or []:
                    if str(x.get("start_reason", "")).startswith("Substitution") and x.get("from_period") == 2:
                        muestras.append((2, seg(x.get("from"))))
    reloj = detecta_reloj(muestras)
    print(f"alineaciones: {len(lineups)} partidos · reloj de positions: {reloj} "
          f"(muestras de entradas en el 2T: {len(muestras)})")
    if reloj == "desconocido":
        sys.exit("[IMPL] no se pudo detectar el reloj de positions")
    for m, lu in lineups.items():
        fp = {p: s for (mm, p), s in fin_per.items() if mm == m}
        for eq in (lu.values() if isinstance(lu, dict) else lu):
            nom = nombre_eq.get(eq["team_id"])
            if nom is None:
                continue
            once = set()
            for j in eq["lineup"]:
                ps = j.get("positions") or []
                if not ps:
                    continue
                mins = minutos_jugados(ps, fp, reloj)
                minutos[nom][(m, j["player_id"])] += mins
                if any(x.get("start_reason") == "Starting XI" for x in ps):
                    once.add(j["player_id"])
                for x in ps:
                    posicion_min[(nom, j["player_id"])][x.get("position")] += minutos_jugados([x], fp, reloj)
            xi[(m, nom)] = once

    def indicadores(equipo, mids):
        mins = defaultdict(float)
        for (m, pid), x in minutos[equipo].items():
            if m in mids:
                mins[pid] += x
        orden = sorted(mids, key=lambda m: fecha_de[m])
        return {"n80": n80(mins.values()) if mins else None,
                "continuidad": continuidad([xi.get((m, equipo), set()) for m in orden]),
                "jugadores_distintos": sum(1 for x in mins.values() if x > 0),
                "cambios_tacticos_por_partido": float(np.mean([shifts_de.get((m, equipo), 0) for m in mids])),
                "partidos": len(mids)}

    # distribucion de la liga por equipo-torneo
    liga_tt = defaultdict(dict)
    por_eq_t = defaultdict(list)
    for m, eqs in equipos_de.items():
        for e in eqs:
            por_eq_t[(e, torneo_de[m])].append(m)
    for (e, t), mids in por_eq_t.items():
        liga_tt[t][e] = indicadores(e, set(mids))

    # ------------------------------------------------ C · eventos de cambio
    ini_de = {(m, p): (per, seg(ts)) for m, p, per, ts in ini_pos.iter_rows()}
    pos = (v.sort(["poss_uid", "event_index"]).group_by("poss_uid", maintain_order=True)
           .agg(pl.col("match_id").first(), pl.col("team").first(), pl.col("score_state").first(),
                (pl.col("action_type") != "TERMINAL").sum().alias("L"),
                pl.col("to_state").is_in([gol, tiro]).any().cast(pl.Int8).alias("S"))
           .with_columns(pl.col("poss_uid").str.split("_").list.last().cast(pl.Int64, strict=False)
                         .alias("possession")))
    pos_m = defaultdict(list)
    for m, e, ss, L, S, pn in pos.select("match_id", "team", "score_state", "L", "S", "possession").iter_rows():
        per, t = ini_de.get((m, pn), (None, None))
        if per is not None:
            pos_m[m].append((per, t, e, ss, L, S))
    acc_m = defaultdict(list)
    for m, e, per, ts, x in acciones.select("match_id", "team", "period", "timestamp", "x").iter_rows():
        acc_m[m].append((per, seg(ts), e, (x or 0.0) >= 80.0))
    P_m = {m: (np.array([r[0] for r in L_]), np.array([r[1] for r in L_]), np.array([r[2] for r in L_]),
               [r[3] for r in L_], np.array([r[4] for r in L_], float), np.array([r[5] for r in L_], float))
           for m, L_ in pos_m.items()}
    A_m = {m: (np.array([r[0] for r in L_]), np.array([r[1] for r in L_]), np.array([r[2] for r in L_]),
               np.array([r[3] for r in L_], float)) for m, L_ in acc_m.items()}

    def delta_evento(m, equipo, t, excl):
        per, tt, eq, ss, L, S = P_m[m]
        (a0, a1), (d0, d1) = ventanas(t, excl)
        mio, rival = (per == 2) & (eq == equipo), (per == 2) & (eq != equipo)
        out = []
        for num, sel in ((L, mio), (S, mio), (S, rival)):
            b = tasa_ventana(tt[sel], num[sel], np.ones(sel.sum()), a0, a1, True)
            dd = tasa_ventana(tt[sel], num[sel], np.ones(sel.sum()), d0, d1, False)
            out.append(dd - b)
        ap_, at_, ae_, af_ = A_m.get(m, (np.array([]),) * 4)
        s2 = ap_ == 2
        ft = []
        for lo, hi, izq in ((a0, a1, True), (d0, d1, False)):
            ok = s2 & (((at_ >= lo) & (at_ < hi)) if izq else ((at_ > lo) & (at_ <= hi)))
            tot = af_[ok].sum()
            ft.append(float(af_[ok & (ae_ == equipo)].sum() / tot) if tot > 0 else float("nan"))
        out.append(ft[1] - ft[0])
        antes = (per == 2) & (tt < t)
        ss_eq = None
        if antes.any():
            k = np.flatnonzero(antes)[np.argmax(tt[antes])]
            ss_eq = ss[k] if eq[k] == equipo else m36.invierte_marcador(ss[k])
        return np.array(out), marcador_idx(ss_eq)

    eventos = []
    for tipo in ("Tactical", "Injury"):
        primeros = (subs.filter(pl.col("substitution_outcome") == tipo)
                    .group_by(["match_id", "team"], maintain_order=True).first())
        for m, e, per, ts in primeros.select("match_id", "team", "period", "timestamp").iter_rows():
            t = seg(ts)
            if per != 2 or not (T_MIN <= t <= T_MAX) or m not in P_m:
                continue
            D, mk = delta_evento(m, e, t, EXCL)
            D0, _ = delta_evento(m, e, t, 0.0)
            if mk is None:
                continue
            eventos.append({"tipo": tipo, "m": m, "equipo": e, "t": t, "D": D, "D0": D0,
                            "estrato": (bloque(t) * 3 + mk) * len(torneos) + tpos[torneo_de[m]],
                            "marcador": mk})
    n_s = 3 * 3 * len(torneos)
    tac = [x for x in eventos if x["tipo"] == "Tactical"]
    print(f"eventos de cambio: tacticos {len(tac)} · por lesion {len(eventos) - len(tac)} "
          f"({time.time()-t0:,.0f} s)")

    def media_liga(evs, mk, j, clave="D"):
        vals = [x[clave][j] for x in evs if x["marcador"] == mk and np.isfinite(x[clave][j])]
        return (float(np.mean(vals)) if vals else float("nan")), len(vals)

    liga = {tipo: {mt: {nm: media_liga([x for x in eventos if x["tipo"] == tipo], k, j)
                        for k, nm in enumerate(("perdiendo", "empatando", "ganando"))}
                   for j, mt in enumerate(METRICAS)} for tipo in ("Tactical", "Injury")}

    # ------------------------------------------------ por era
    E_m = np.array([x["m"] for x in tac])
    E_eq = np.array([x["equipo"] for x in tac], dtype=object)
    E_D = np.array([x["D"] for x in tac]).reshape(-1, 4)
    E_D0 = np.array([x["D0"] for x in tac]).reshape(-1, 4)
    E_s = np.array([x["estrato"] for x in tac], dtype=np.int64)
    filas = []
    por_club = defaultdict(list)
    for slug, club, dt in vivas:
        por_club[(slug, club)].append(dt)
    for (slug, club), dts in sorted(por_club.items()):
        base_sel = np.array([club not in equipos_de[m] for m in E_m], bool)
        bm = E_m[base_sel]
        umat = sorted(set(bm.tolist()))
        idx_b = {m: i for i, m in enumerate(umat)}
        brow = np.array([idx_b[m] for m in bm], dtype=np.int64)
        bt = np.array([tpos[torneo_de[m]] for m in umat])
        rng_b = m30.semilla(args.seed, club, "__base__")
        Wb = [np.ones(len(umat))]
        for _ in range(args.n_boot):
            w = np.zeros(len(umat))
            for ti in range(len(torneos)):
                ix = np.flatnonzero(bt == ti)
                if ix.size:
                    w[ix] = np.bincount(rng_b.integers(0, ix.size, ix.size), minlength=ix.size)
            Wb.append(w)
        for dt in dts:
            mids = {m for m in completos if coach_de.get((m, club)) == dt}
            if not mids:
                continue
            fila = {"club": club, "coach": dt, "slug": slug, "n_partidos": len(mids),
                    "en_adr52": slug in CLUBES_ADR52, "en_casos": dt in casos and club in casos[dt]}
            # A
            porT = defaultdict(set)
            for m in mids:
                porT[torneo_de[m]].add(m)
            filaA = {}
            for t, ms in sorted(porT.items(), key=lambda kv: orden_t[kv[0]]):
                ind = indicadores(club, ms)
                parcial = len(ms) < MIN_PARTIDOS_TORNEO
                if not parcial:
                    for k in ("n80", "continuidad", "jugadores_distintos", "cambios_tacticos_por_partido"):
                        ind[f"percentil_{k}"] = percentil(
                            ind[k] if ind[k] is not None else float("nan"),
                            [x[k] for e, x in liga_tt[t].items() if e != club and x["partidos"] >= MIN_PARTIDOS_TORNEO
                             and x[k] is not None])
                ind["parcial"] = parcial
                filaA[t] = ind
            fila["A"] = filaA
            # B
            mins_era = defaultdict(float)
            for (m, pid), x in minutos[club].items():
                if m in mids:
                    mins_era[pid] += x
            roles = []
            vj = (v.filter((pl.col("team") == club) & pl.col("match_id").is_in(sorted(mids))
                           & (pl.col("action_type") != "TERMINAL"))
                  .select("player_id", "from_state"))
            zonas_de = defaultdict(lambda: np.zeros(sp.nx * sp.ny))
            for pid, fs in vj.iter_rows():
                if pid is not None and fs is not None and fs < n_tr:
                    zonas_de[int(pid)][int(fs) // nph] += 1
            for pid, mm in sorted(mins_era.items(), key=lambda kv: -kv[1]):
                if mm < MIN_MINUTOS_ROL:
                    continue
                z = zonas_de.get(int(pid), np.zeros(sp.nx * sp.ny))
                pm = posicion_min.get((club, pid), Counter())
                roles.append({"player_id": int(pid), "minutos": round(mm, 1),
                              "posicion_modal": pm.most_common(1)[0][0] if pm else None,
                              "acciones": int(z.sum()),
                              "zonas": (z / z.sum()).round(4).tolist() if z.sum() else None,
                              "centro_ix": float((np.arange(sp.nx * sp.ny) // sp.ny * z).sum() / z.sum()) if z.sum() else None,
                              "centro_iy": float((np.arange(sp.nx * sp.ny) % sp.ny * z).sum() / z.sum()) if z.sum() else None})
            fila["B"] = roles
            # C
            sel_u = np.array([(m in mids) and (e == club) for m, e in zip(E_m, E_eq)], bool)
            um = E_m[sel_u]
            idx_u = {m: i for i, m in enumerate(sorted(set(um.tolist())))}
            urow = np.array([idx_u[m] for m in um], dtype=np.int64)
            rng_u = m30.semilla(args.seed, club, dt)
            nu = len(idx_u)
            Wu = [np.ones(nu)] + [np.bincount(rng_u.integers(0, nu, nu), minlength=nu).astype(float)
                                  for _ in range(args.n_boot)] if nu else []
            fila["C"] = {"eventos": int(sel_u.sum())}
            for j, mt in enumerate(METRICAS):
                if not nu:
                    fila["C"][mt] = {"theta": float("nan"), "p": float("nan"), "ic95": [None, None]}
                    continue
                R = np.array([theta_estratificado(E_D[sel_u, j], wu[urow], E_s[sel_u],
                                                  E_D[base_sel, j], wb[brow], E_s[base_sel], n_s)
                              for wu, wb in zip(Wu, Wb)])
                th = R[0, 2]
                ok = np.isfinite(th) and np.isfinite(R[1:, 2]).sum() > 10
                R0 = theta_estratificado(E_D0[sel_u, j], np.ones(nu)[urow], E_s[sel_u],
                                         E_D0[base_sel, j], np.ones(len(umat))[brow], E_s[base_sel], n_s)
                fila["C"][mt] = {"media_era": R[0, 0], "media_liga": R[0, 1], "theta": th,
                                 "descartado": R[0, 3],
                                 "ic95": list(m30.ic_basic(R[1:, 2], th)) if ok else [None, None],
                                 "p": m30.p_basic(R[1:, 2], th) if ok else float("nan"),
                                 "sin_exclusion_theta": R0[2]}
            filas.append(fila)
            c = fila["C"]
            print(f"  {club:<20}{dt:<26} eventos={c['eventos']:>3}  "
                  f"M2 {100*c['M2']['theta']:+6.2f} pp  FT {100*c['FT']['theta']:+6.2f} pp  "
                  f"({time.time()-t0:,.0f} s)")

    # ------------------------------------------------ familias
    resumen = {}
    piso = 2.0 / (args.n_boot + 1)
    for nom, clave in (("adr52", "en_adr52"), ("casos", "en_casos")):
        items = [(f, mt) for f in filas if f[clave] for mt in METRICAS if np.isfinite(f["C"][mt]["p"])]
        m_ = len(items)
        if not m_:
            resumen[nom] = {"m": 0}
            continue
        q, rech = benjamini_hochberg(np.array([f["C"][mt]["p"] for f, mt in items]), alpha=args.alpha)
        for (f, mt), qi, ri in zip(items, q, rech):
            f["C"][mt][f"q_{nom}"], f["C"][mt][f"rechaza_{nom}"] = float(qi), bool(ri)
        resumen[nom] = {"m": m_, "rechazan": int(rech.sum()),
                        "aviso_piso_p": None if piso <= args.alpha / m_ else
                        f"piso del p {piso:.5f} > alpha/m {args.alpha/m_:.5f}"}

    # ------------------------------------------------ predicciones
    lt, li = liga["Tactical"], liga["Injury"]
    pred = [
        {"n": 1, "texto": "liga, perdiendo: Delta M2 > 0 tras el primer cambio tactico",
         "valor": lt["M2"]["perdiendo"], "cumple": lt["M2"]["perdiendo"][0] > 0},
        {"n": 2, "texto": "liga, perdiendo: Delta FT > 0 tras el primer cambio tactico",
         "valor": lt["FT"]["perdiendo"], "cumple": lt["FT"]["perdiendo"][0] > 0},
        {"n": 3, "texto": "a lo sumo 5 rechazos en ADR-52 y 5 en casos",
         "valor": [resumen["adr52"].get("rechazan"), resumen["adr52"].get("m"),
                   resumen["casos"].get("rechazan"), resumen["casos"].get("m")],
         "cumple": (resumen["adr52"].get("rechazan") or 0) <= 5 and (resumen["casos"].get("rechazan") or 0) <= 5},
        {"n": 4, "texto": "liga, perdiendo: |Delta M2| por lesion < |Delta M2| tactico",
         "valor": [li["M2"]["perdiendo"], lt["M2"]["perdiendo"]],
         "cumple": (None if not np.isfinite(li["M2"]["perdiendo"][0]) else
                    abs(li["M2"]["perdiendo"][0]) < abs(lt["M2"]["perdiendo"][0]))},
    ]

    salida = {"adr": "ADR-58", "preinscripcion": "docs/preinscritos/ADR-58_BORRADOR.md (commit db715ef)",
              "reglas": REGLAS,
              "parametros": {"n_boot": args.n_boot, "seed": args.seed, "ventana_s": VENT, "exclusion_s": EXCL,
                             "franja_s": [T_MIN, T_MAX], "min_partidos_torneo": MIN_PARTIDOS_TORNEO,
                             "min_minutos_rol": MIN_MINUTOS_ROL, "torneos": torneos},
              "diagnostico": {"reloj_positions": reloj, "muestras_reloj": len(muestras),
                              "union_acciones_eventos": tasa_union, "partidos_con_alineacion": len(lineups),
                              "eventos_tacticos": len(tac), "eventos_lesion": len(eventos) - len(tac)},
              "universo": {"partidos": len(completos), "excluidos_d54_12": sorted(int(m) for m in incompletos)},
              "eras_bloqueadas_por_candado": bloqueadas,
              "liga": liga, "familias": resumen, "predicciones": pred,
              "unidades": filas, "segundos": round(time.time() - t0, 1)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False,
                                   default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("\n== familias ==")
    for k, r in resumen.items():
        print(f"  {k}: {r}")
    print("\n== predicciones preinscritas ==")
    for p_ in pred:
        v_ = p_["cumple"]
        print(f"  P{p_['n']}. {'CUMPLE' if v_ else ('n/e   ' if v_ is None else 'FALLA ')}  {p_['texto']}  "
              f"{json.dumps(p_['valor'], default=float)}")
    print(f"\nescrito {args.out}  ({salida['segundos']:,.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
