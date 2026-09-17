#!/usr/bin/env python3
"""
35_balon_parado.py — ADR-55: balon parado, la cadena para la prevencion y la
geometria del remate para la supresion.

Preinscrito en `docs/preinscritos/ADR-55_BORRADOR.md` (commit 9aa5524), con
las adendas 1 y 2 de ADR-54 heredadas (vista defensora, universo de partidos
completos). Donde hubo que concretar algo que el documento no fijaba: [IMPL].

  C1  P(S | secuencia)        remate del atacante dentro de la secuencia
  C2  E[xG_full | remate]     modelo de balon parado ajustado UNA vez (liga)

Secuencia de corner: empieza en el evento `pass_type = Corner`; incluye su
posesion y las siguientes del mismo partido y periodo con
`play_pattern = From Corner`, hasta la primera con otro patron o con otro
cobro. Igual para tiro libre indirecto (x >= 60) y saque de banda (x >= 80).

[IMPL] Las secuencias salen de los EVENTOS, que traen todas las posesiones: C1
no depende de `min_actions`. La vista defensora (min_actions = 1) alimenta solo
la parte de la cadena.
[IMPL] Un remate del DEFENSOR dentro de la secuencia (contragolpe) no cuenta
como S. Penales fuera siempre.
[IMPL] La disposicion de los coeficientes de `xg_remate.ajusta_logistica` se
IDENTIFICA en tiempo de ejecucion comparando contra `predice`; si no se puede,
el script aborta. Una sola ruta para el modelo.

Uso:
    nohup python -u scripts/35_balon_parado.py --out reports/balon_parado_v1.json \\
        > logs/balon_parado_v1.log 2>&1 &
    # humo:
    python scripts/35_balon_parado.py --n-boot 200 --n-boot-coef 100 \\
        --out /tmp/balon_parado_humo.json
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
TIPOS = {                     # pass_type inicial, patron de continuacion, x minima
    "corner": ("Corner", "From Corner", None),
    "tiro_libre": ("Free Kick", "From Free Kick", 60.0),
    "banda": ("Throw-in", "From Throw In", 80.0),
}
REGLAS = {
    "D55-1": "C1 = P(S|secuencia), empirica; la version de la cadena es descriptiva",
    "D55-2": "C2 = E[xG_full|remate], modelo de balon parado ajustado una vez para la liga",
    "D55-3": "xG_base: distancia, angulo, cabeza (binaria); xG_full: + geometria defensiva",
    "D55-4": "sensibilidad: interaccion cabeza x distancia",
    "D55-5": "segunda jugada: max V(s)=B[s,GOAL] tras la primera posesion; 10 s como sensibilidad",
    "D55-6": "comparacion contra la liga sin el club en los mismos torneos; bootstrap por partido",
    "D55-7": "familia: {C1,C2} x {ofensivo,defensivo} de corner, 21 unidades de ADR-52, BH 5%",
    "D55-8": "vista defensora (D54-10) y universo de partidos completos (D54-12)",
    "D55-9": "adenda 1: la definicion principal de C1 no cambia",
    "D55-10": "adenda 1: S_10s y S_fase, exploratorios, fuera de la familia",
    "D55-11": "adenda 1: se aborta si menos de 100 remates tienen geometria",
    "D57-2": "segunda familia: casos de ADR-57, BH por separado",
}


# ==========================================================================
# Nucleo puro
# ==========================================================================
def construye_secuencias(poss: list[dict], tipo_pase: str, patron: str,
                         x_min: float | None) -> list[dict]:
    """Secuencias de un partido. `poss` ordenado por numero de posesion.

    Cada elemento: {possession, period, patron, equipo, inicia: {pass_type, x}
    o None, tiros: [(equipo, es_gol)]}.
    """
    out, i, n = [], 0, len(poss)
    while i < n:
        p = poss[i]
        ini = p.get("inicia")
        ok = (ini is not None and ini["pass_type"] == tipo_pase
              and (x_min is None or (ini["x"] is not None and ini["x"] >= x_min)))
        if not ok:
            i += 1
            continue
        atac = p["equipo"]
        miembros = [p["possession"]]
        S = G = 0
        for eq, gol in p["tiros"]:
            if eq == atac:
                S = 1; G |= int(gol)
        j = i + 1
        while j < n:
            q = poss[j]
            if (q["period"] != p["period"] or q["patron"] != patron
                    or q.get("inicia") is not None):
                break
            miembros.append(q["possession"])
            for eq, gol in q["tiros"]:
                if eq == atac:
                    S = 1; G |= int(gol)
            j += 1
        out.append({"atacante": atac, "posesiones": miembros, "S": S, "G": G,
                    "period": p["period"]})
        i = j
    return out


def agrega_por_partido(filas: list[dict], clave: str) -> dict:
    """{(match, atacante): [n, suma]} para promedios por partido."""
    d: dict = {}
    for f in filas:
        k = (f["match_id"], f["atacante"])
        a = d.setdefault(k, [0.0, 0.0])
        a[0] += 1
        a[1] += f[clave]
    return d


def tasa_estandarizada(n_u: np.ndarray, s_u: np.ndarray, n_b: np.ndarray,
                       s_b: np.ndarray) -> tuple[float, float, float]:
    """(tasa unidad, base estandarizada a la mezcla por torneo de la unidad, DiD).

    n_*, s_*: vectores por torneo (conteos y sumas).
    """
    tu = s_u.sum() / max(n_u.sum(), _EPS)
    with np.errstate(invalid="ignore", divide="ignore"):
        rb = np.where(n_b > 0, s_b / n_b, np.nan)
    w = n_u / max(n_u.sum(), _EPS)
    if np.any((w > 0) & ~np.isfinite(rb)):
        return float(tu), float("nan"), float("nan")
    base = float(np.nansum(w * np.where(w > 0, rb, 0.0)))
    return float(tu), base, float(tu - base)


def auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return float("nan")
    r = np.argsort(np.argsort(p)) + 1.0
    n1, n0 = y.sum(), (1 - y).sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def sigm(z):
    return 1.0 / (1.0 + np.exp(-z))


def disposicion_coef(b: np.ndarray, Z: np.ndarray, pred: np.ndarray) -> str:
    """Identifica como usa `predice` al vector b: intercepto al inicio o al final."""
    b = np.asarray(b, float).ravel()
    p = Z.shape[1]
    cands = {}
    if b.size == p + 1:
        cands["inicio"] = sigm(b[0] + Z @ b[1:])
        cands["final"] = sigm(Z @ b[:-1] + b[-1])
    if b.size == p:
        cands["sin_intercepto"] = sigm(Z @ b)
    for k, v in cands.items():
        if np.allclose(v, np.asarray(pred).ravel(), atol=1e-8):
            return k
    return "desconocida"


def pendientes(b: np.ndarray, disp: str) -> np.ndarray:
    b = np.asarray(b, float).ravel()
    return {"inicio": b[1:], "final": b[:-1], "sin_intercepto": b}[disp]


def zona_remate(x: float, y: float) -> str:
    if x >= 114 and 30 <= y <= 50:
        return "area_chica"
    if x >= 102 and 30 <= y <= 50:
        return "area_central"
    if x >= 102 and 18 <= y <= 62:
        return "area_lateral"
    return "fuera_del_area"


def zona_destino(y_ini: float, y_fin: float) -> str:
    if not np.isfinite(y_fin):
        return "desconocida"
    if 36 <= y_fin <= 44:
        return "central"
    cercano = (y_ini < 40) == (y_fin < 40)
    return "primer_palo" if cercano else "segundo_palo"


def xy_de(s) -> tuple[float, float]:
    if s is None:
        return float("nan"), float("nan")
    try:
        v = json.loads(s) if isinstance(s, str) else s
        return float(v[0]), float(v[1])
    except Exception:
        return float("nan"), float("nan")


def a_literal(s):
    """JSON (true/false/null) -> texto que `ast.literal_eval` acepta (bug #21)."""
    if not isinstance(s, str):
        return s
    try:
        return repr(json.loads(s))
    except Exception:
        return s


def elige_formato(ok_crudo: int, ok_literal: int, n: int, minimo: float = 0.9) -> str | None:
    """Que formato usar con `xg_remate.features`, segun una muestra."""
    mejor = max(("crudo", ok_crudo), ("literal", ok_literal), key=lambda t: t[1])
    return mejor[0] if n and mejor[1] >= minimo * n else None


def seg(ts: str | None) -> float:
    if not ts:
        return float("nan")
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


# ==========================================================================
def _carga(nombre: str):
    spec = importlib.util.spec_from_file_location("m_" + nombre[:2] + "_bp", RAIZ / "scripts" / nombre)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=Path("data"))
    ap.add_argument("--eventos", type=Path, default=Path("data/api/eventos_api_ligamx"))
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--n-boot", type=int, default=6000, dest="n_boot")
    ap.add_argument("--n-boot-coef", type=int, default=1000, dest="n_boot_coef")
    ap.add_argument("--lam", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=20260916)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=Path("reports/balon_parado_v1.json"))
    args = ap.parse_args()
    if args.out.exists():
        sys.exit(f"{args.out} ya existe: escribe a un archivo NUEVO.")

    import polars as pl
    from dtdecoder.config import Config
    from dtdecoder.eras import check_verificada
    from dtdecoder.estimate import count_matrix
    from dtdecoder.geometria_remate import Contadores, RADIO_DEFENSOR
    from dtdecoder.inference import benjamini_hochberg
    from dtdecoder import xg_remate as XG

    m08 = _carga("08_ic_derivados.py")
    m24 = _carga("24_linea_base_contemporanea.py")
    m30 = _carga("30_did_contemporaneo.py")
    m33 = _carga("33_did_presion.py")
    m36 = _carga("36_contexto.py")
    sp = m08._space(Config.load(args.config))
    rng = np.random.default_rng(args.seed)
    t0 = time.time()

    # ------------------------------------------------ vista defensora (D55-8)
    cols_v = ["poss_uid", "match_id", "team", "event_index", "action_type",
              "from_state", "to_state", "match_date", "coach_faced"]
    dirs = sorted(p for p in args.datos.glob("processed_api_*")
                  if (p / "phase0_report.json").exists())
    if len(dirs) != 18:
        sys.exit(f"D54-10: hacen falta los 18 directorios; hay {len(dirs)}")
    partes, unidades_rep = [], []
    for d in dirs:
        rep = json.loads((d / "phase0_report.json").read_text()).get("coaches") or {}
        club_d = rep["club"]
        t = pl.read_parquet(d / "transitions.parquet", columns=cols_v)
        partes.append(t.filter(pl.col("team") != club_d).with_columns(pl.lit(club_d).alias("defensor")))
        for c in rep.get("coverage", []):
            if c.get("suficiente"):
                unidades_rep.append((d.name.replace("processed_api_", ""), club_d, c["coach"]))
    vista = pl.concat(partes, how="vertical_relaxed")
    ternas = vista.select("match_id", "team", "defensor").unique()
    completos, incompletos = m33.partidos_completos(
        ternas["match_id"].to_numpy(), ternas["team"].to_numpy(), ternas["defensor"].to_numpy())
    vista = vista.filter(pl.col("match_id").is_in(sorted(completos))).with_columns(m24.torneo_cols())
    orden_t = dict(vista.select("torneo", "torneo_orden").unique().iter_rows())
    torneos = sorted(orden_t, key=orden_t.get)
    tpos = {t: i for i, t in enumerate(torneos)}
    torneo_de = dict(vista.select("match_id", "torneo").unique().iter_rows())
    # entrenador por (partido, club): el club defiende -> coach_faced
    coach_de = {(m, c): e for m, c, e in vista.filter(pl.col("coach_faced").is_not_null())
                .select("match_id", "defensor", "coach_faced").unique().iter_rows()}
    equipos_de: dict = {}
    for m, a, d_ in ternas.iter_rows():
        equipos_de.setdefault(m, set()).update((a, d_))
    print(f"vista: {vista.height:,} filas · {len(completos)} partidos · "
          f"excluidos D54-12: {sorted(int(m) for m in incompletos)}")

    # ------------------------------------------------------------ eventos
    ev_files = sorted(glob.glob(str(args.eventos / "*.parquet")))
    lf = pl.scan_parquet(ev_files).filter(pl.col("match_id").is_in(sorted(completos)))
    poss_tab = (lf.group_by(["match_id", "possession"])
                .agg(pl.col("period").first(), pl.col("play_pattern").first(),
                     pl.col("possession_team").first().alias("equipo"))
                .collect())
    inicios = (lf.filter(pl.col("pass_type").is_in([v[0] for v in TIPOS.values()]))
               .select("match_id", "possession", "index", "team", "pass_type", "location",
                       "pass_end_location", "pass_technique", "pass_height", "timestamp", "period")
               .sort(["match_id", "possession", "index"]).collect())
    tiros = (lf.filter((pl.col("type") == "Shot") & (pl.col("shot_type") != "Penalty"))
             .select("match_id", "possession", "index", "team", "shot_type", "shot_outcome",
                     "shot_body_part", "location", "shot_freeze_frame", "shot_statsbomb_xg",
                     "play_pattern", "timestamp", "period", "set_piece_phase")
             .collect())
    print(f"eventos: {poss_tab.height:,} posesiones · {inicios.height:,} cobros · "
          f"{tiros.height:,} remates sin penales ({time.time()-t0:,.0f} s)")

    ini_de: dict = {}
    for r in inicios.iter_rows(named=True):
        k = (r["match_id"], r["possession"])
        if k in ini_de:                       # un cobro por posesion (el primero)
            continue
        x, y = xy_de(r["location"])
        ini_de[k] = {"pass_type": r["pass_type"], "x": x, "y": y, "row": r}
    tiros_de: dict = {}
    for r in tiros.iter_rows(named=True):
        tiros_de.setdefault((r["match_id"], r["possession"]), []).append(r)

    # ---------------------------------------------------------- secuencias
    por_partido: dict = {}
    for r in poss_tab.sort(["match_id", "possession"]).iter_rows(named=True):
        k = (r["match_id"], r["possession"])
        por_partido.setdefault(r["match_id"], []).append({
            "possession": r["possession"], "period": r["period"], "patron": r["play_pattern"],
            "equipo": r["equipo"], "inicia": ini_de.get(k),
            "tiros": [(t["team"], t["shot_outcome"] == "Goal") for t in tiros_de.get(k, [])],
        })
    secs = {tipo: [] for tipo in TIPOS}
    for m, lista in por_partido.items():
        for tipo, (tp, pat, xmin) in TIPOS.items():
            for s_ in construye_secuencias(lista, tp, pat, xmin):
                s_["match_id"] = m
                s_["defensor"] = next(iter(equipos_de[m] - {s_["atacante"]}), None)
                s_["torneo"] = torneo_de[m]
                s_["ini"] = ini_de[(m, s_["posesiones"][0])]["row"]
                secs[tipo].append(s_)
    for tipo, lista_s in secs.items():
        for s_ in lista_s:
            t0s, per, at = seg(s_["ini"]["timestamp"]), s_["period"], s_["atacante"]
            tt = [t for pn in s_["posesiones"] for t in tiros_de.get((s_["match_id"], pn), [])
                  if t["team"] == at]
            s_["S10"] = int(any(t["period"] == per and 0 < seg(t["timestamp"]) - t0s <= 10 for t in tt))
            s_["Sfase"] = int(any(t["set_piece_phase"] is not None for t in tt))
    print("secuencias:", {k: len(v) for k, v in secs.items()},
          "· P(S) liga:", {k: round(float(np.mean([s["S"] for s in v])), 4) for k, v in secs.items() if v})

    # --------------------------------------- formato del freeze frame (bug #21)
    muestra = tiros.filter(pl.col("shot_freeze_frame").is_not_null()).head(500)
    def _ok(transf):
        n = 0
        for r in muestra.iter_rows(named=True):
            try:
                f = XG.features(transf(r["location"]), transf(r["shot_freeze_frame"]),
                                RADIO_DEFENSOR, Contadores())
            except Exception:
                f = None
            if f is not None and np.all(np.isfinite([f[c] for c in XG.ATA + XG.DEF])):
                n += 1
        return n
    ok_c, ok_l = _ok(lambda v: v), _ok(a_literal)
    formato = elige_formato(ok_c, ok_l, muestra.height)
    print(f"freeze frame: muestra {muestra.height} · validos crudo {ok_c} · "
          f"literal {ok_l} · formato elegido: {formato}")
    if formato is None:
        sys.exit("bug #21: xg_remate.features no acepta el formato del API ni convertido. "
                 "Revisa XG.xy / XG.features.")
    conv = (lambda v: v) if formato == "crudo" else a_literal

    # ------------------------------------------- remates y modelo (D55-2/3)
    cont = Contadores()
    filas_tiro = []
    for tipo in ("corner", "tiro_libre"):
        for s_ in secs[tipo]:
            for pnum in s_["posesiones"]:
                for t in tiros_de.get((s_["match_id"], pnum), []):
                    if t["team"] != s_["atacante"] or t["shot_type"] == "Free Kick":
                        continue
                    f = XG.features(conv(t["location"]), conv(t["shot_freeze_frame"]), RADIO_DEFENSOR, cont)
                    if f is None:
                        continue
                    vals = [f[c] for c in XG.ATA + XG.DEF]
                    if not np.all(np.isfinite(vals)):
                        continue
                    sx, sy = xy_de(t["location"])
                    filas_tiro.append({
                        "tipo": tipo, "match_id": s_["match_id"], "atacante": s_["atacante"],
                        "defensor": s_["defensor"], "torneo": s_["torneo"],
                        "y": int(t["shot_outcome"] == "Goal"),
                        "cabeza": int(t["shot_body_part"] == "Head"),
                        "sb_xg": t["shot_statsbomb_xg"], "zona": zona_remate(sx, sy),
                        **{c: f[c] for c in XG.ATA + XG.DEF}})
    n_tiros_sp = len(filas_tiro)
    if n_tiros_sp < 100:
        sys.exit(f"D55-11: solo {n_tiros_sp} remates con geometria valida ({cont.resumen()}).")
    Y = np.array([f["y"] for f in filas_tiro], float)
    BLO = np.array([f["match_id"] for f in filas_tiro])
    Xb = np.array([[f[c] for c in XG.ATA] + [f["cabeza"]] for f in filas_tiro], float)
    Xf = np.hstack([Xb, np.array([[f[c] for c in XG.DEF] for f in filas_tiro], float)])
    zs = lambda X: (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1.0)
    Zb, Zf = zs(Xb), zs(Xf)
    p_base = XG.fuera_de_pliegue(Zb, Y, BLO, lam=args.lam, rng=rng)
    p_full = XG.fuera_de_pliegue(Zf, Y, BLO, lam=args.lam, rng=rng)
    for f, pb, pf in zip(filas_tiro, p_base, p_full):
        f["xg_base"], f["xg_full"] = float(pb), float(pf)
    b0 = XG.ajusta_logistica(Zb, Y, lam=args.lam)
    disp = disposicion_coef(b0, Zb, XG.predice(b0, Zb))
    if disp == "desconocida":
        sys.exit("[IMPL] no se pudo identificar la disposicion de los coeficientes de xg_remate")
    nombres_b = XG.ATA + ["cabeza"]
    beta0 = pendientes(b0, disp)
    # interaccion (D55-4)
    Xi = np.hstack([Xb, (Xb[:, 0] * Xb[:, -1])[:, None]])
    bi = XG.ajusta_logistica(zs(Xi), Y, lam=args.lam)
    beta_i = pendientes(bi, disposicion_coef(bi, zs(Xi), XG.predice(bi, zs(Xi))))

    ub = np.unique(BLO)
    idx_de = {b: np.flatnonzero(BLO == b) for b in ub}
    reps_beta, reps_dauc = [], []
    for _ in range(args.n_boot_coef):
        idx = np.concatenate([idx_de[b] for b in rng.choice(ub, ub.size, replace=True)])
        bb = XG.ajusta_logistica(Zb[idx], Y[idx], lam=args.lam)
        reps_beta.append(pendientes(bb, disp))
        reps_dauc.append(auc(Y[idx], p_full[idx]) - auc(Y[idx], p_base[idx]))
    reps_beta = np.array(reps_beta)
    q = lambda v: [float(np.nanquantile(v, 0.025)), float(np.nanquantile(v, 0.975))]
    dauc = auc(Y, p_full) - auc(Y, p_base)
    sbm = np.array([f["sb_xg"] if f["sb_xg"] is not None else np.nan for f in filas_tiro], float)
    okx = np.isfinite(sbm)
    modelo = {
        "n_remates": n_tiros_sp, "n_goles": int(Y.sum()), "geometria": cont.resumen(),
        "disposicion_coeficientes": disp,
        "beta_base_estandarizado": {n: float(b) for n, b in zip(nombres_b, beta0)},
        "beta_base_ic95": {n: q(reps_beta[:, i]) for i, n in enumerate(nombres_b)},
        "beta_interaccion": {n: float(b) for n, b in zip(nombres_b + ["dist_x_cabeza"], beta_i)},
        "auc_base": auc(Y, p_base), "auc_full": auc(Y, p_full),
        "delta_auc": dauc, "delta_auc_ic95_percentil": q(np.array(reps_dauc)),
        "auc_statsbomb": auc(Y[okx], sbm[okx]),
        "nota": "bootstrap por partido con predicciones fijas (el modelo es un estorbo; regla 3 de 26)",
    }
    print(f"modelo: {n_tiros_sp} remates, {int(Y.sum())} goles · AUC base {modelo['auc_base']:.3f} "
          f"full {modelo['auc_full']:.3f} SB {modelo['auc_statsbomb']:.3f} · "
          f"beta cabeza {modelo['beta_base_estandarizado']['cabeza']:+.3f} "
          f"{[round(v,3) for v in modelo['beta_base_ic95']['cabeza']]} ({time.time()-t0:,.0f} s)")

    # goal_open de juego abierto (P7)
    go_ab = []
    for r in tiros.filter(pl.col("play_pattern") == "Regular Play").iter_rows(named=True):
        if r["shot_type"] != "Open Play":
            continue
        f = XG.features(conv(r["location"]), conv(r["shot_freeze_frame"]), RADIO_DEFENSOR, Contadores())
        if f is not None and np.isfinite(f["goal_open"]):
            go_ab.append((r["match_id"], f["goal_open"]))
    go_ab_m = np.array([g for _, g in go_ab])
    go_co = np.array([f["goal_open"] for f in filas_tiro if f["tipo"] == "corner"])

    # ------------------------------------------------ cadena de la liga (D55-5)
    Cl = count_matrix(vista, sp)
    Pl = m30.normaliza_filas(Cl)
    ch = m08.derivadas  # E_T, P_gol, P_remate con alpha
    n_tr = sp.n_transient
    A = np.eye(n_tr) - Pl[:, :n_tr]
    Bl = np.linalg.solve(A, Pl[:, n_tr:])
    V = Bl[:, sp.absorbing.index("GOAL")]
    primera = vista.sort(["poss_uid", "event_index"]).group_by("poss_uid", maintain_order=True).agg(
        pl.col("from_state").first(), pl.col("team").first(), pl.col("match_id").first())
    ini_estado = {u: s for u, s in primera.select("poss_uid", "from_state").iter_rows()}
    vt = vista.filter(pl.col("from_state") < n_tr)
    vt = vt.with_columns(pl.Series("v", V[vt["from_state"].to_numpy().astype(int)]))
    vmax_de = dict(vt.group_by("poss_uid").agg(pl.col("v").max()).iter_rows())

    def vmax_segunda(s_):
        vals = [vmax_de.get(f"{s_['match_id']}_{p}") for p in s_["posesiones"][1:]]
        vals = [v for v, p in zip(vals, s_["posesiones"][1:]) if v is not None]
        return max(vals) if vals else 0.0

    corners = secs["corner"]
    alpha = np.zeros(n_tr)
    for s_ in corners:
        e = ini_estado.get(f"{s_['match_id']}_{s_['posesiones'][0]}")
        if e is not None and e < n_tr:
            alpha[e] += 1
    alpha /= max(alpha.sum(), _EPS)
    der_l = ch(Cl, alpha, Pl, 0.0, sp)
    # empirico a nivel de POSESION (P5)
    s_pos = [int(any(t["team"] == s_["atacante"] for t in tiros_de.get((s_["match_id"], s_["posesiones"][0]), [])))
             for s_ in corners]
    xg_pos = [f["xg_full"] for f in filas_tiro if f["tipo"] == "corner"]
    prod = float(np.mean(s_pos)) * float(np.mean(xg_pos)) if xg_pos else float("nan")
    liga = {
        "P_S_secuencia": {k: float(np.mean([s["S"] for s in v])) for k, v in secs.items() if v},
        "P_G_secuencia": {k: float(np.mean([s["G"] for s in v])) for k, v in secs.items() if v},
        "exploratorio_adenda_1": {
            "P_S_10s": {k: float(np.mean([s["S10"] for s in v])) for k, v in secs.items() if v},
            "P_S_fase": {k: float(np.mean([s["Sfase"] for s in v])) for k, v in secs.items() if v},
            "nota": "anadido tras ver P(S)=0.396; fuera de la familia (D55-10)"},
        "cadena_corner": der_l,
        "producto_posesion": {"P_S_posesion": float(np.mean(s_pos)), "E_xg_full": float(np.mean(xg_pos)),
                              "producto": prod, "cadena_P_gol": der_l["P_gol"] if der_l else None},
        "goal_open_medio": {"corner": float(go_co.mean()), "juego_abierto": float(go_ab_m.mean())},
        "vmax_segunda_media": float(np.mean([vmax_segunda(s) for s in corners])),
    }

    # sensibilidad 10 s (D55-5): requiere que event_index == index de los eventos
    ts_ev = (lf.select("match_id", "index", "timestamp", "period").collect())
    j = vista.filter(pl.col("action_type") != "TERMINAL").select("match_id", "event_index").join(
        ts_ev.rename({"index": "event_index"}), on=["match_id", "event_index"], how="left")
    tasa_join = float(j["timestamp"].is_not_null().mean())
    liga["sensibilidad_10s"] = {"tasa_union_event_index": tasa_join}
    if tasa_join >= 0.99:
        vv = (vt.join(ts_ev.rename({"index": "event_index"}), on=["match_id", "event_index"], how="left")
              .filter(pl.col("timestamp").is_not_null())
              .with_columns(pl.col("timestamp").str.split(":").list.eval(pl.element().cast(pl.Float64))
                            .alias("_p"))
              .with_columns((pl.col("_p").list.get(0) * 3600 + pl.col("_p").list.get(1) * 60
                             + pl.col("_p").list.get(2)).alias("seg")))
        grupos = {}
        for (m, a, per), g in vv.group_by(["match_id", "team", "period"]):
            o = np.argsort(g["seg"].to_numpy())
            grupos[(m, a, per)] = (g["seg"].to_numpy()[o], g["v"].to_numpy()[o])
        vals = []
        for s_ in corners:
            g = grupos.get((s_["match_id"], s_["atacante"], s_["period"]))
            if g is None:
                vals.append(0.0); continue
            t0s = seg(s_["ini"]["timestamp"])
            lo, hi = np.searchsorted(g[0], [t0s, t0s + 10], side="right")
            vals.append(float(g[1][lo:hi].max()) if hi > lo else 0.0)
        liga["sensibilidad_10s"]["vmax_10s_media"] = float(np.mean(vals)) if vals else None
    print(f"liga: {json.dumps({k: liga[k] for k in ('P_S_secuencia', 'producto_posesion')}, default=float)} "
          f"({time.time()-t0:,.0f} s)")

    # --------------------------------------------- unidades y familia (D55-7)
    def tablas_tipo(tipo):
        """{(match, atacante): (n_sec, n_S, n_tiros, suma_xg)}."""
        d: dict = {}
        for s_ in secs[tipo]:
            a = d.setdefault((s_["match_id"], s_["atacante"]), [0, 0, 0, 0.0])
            a[0] += 1; a[1] += s_["S"]
        for f in filas_tiro:
            if f["tipo"] == tipo:
                a = d.setdefault((f["match_id"], f["atacante"]), [0, 0, 0, 0.0])
                a[2] += 1; a[3] += f["xg_full"]
        return d

    TB = tablas_tipo("corner")
    partidos = sorted(completos)
    n_t = len(torneos)

    def matriz(pares_ma):
        """(valores K x 4, torneo K) para una lista de (partido, atacante)."""
        vals = np.array([TB.get(k, (0, 0, 0, 0.0)) for k in pares_ma], float).reshape(-1, 4)
        tor = np.array([tpos[torneo_de[m]] for m, _ in pares_ma], dtype=np.int64)
        return vals, tor

    def vectores(vals, tor, w):
        """Sumas por torneo (4 x n_t) con pesos por fila."""
        return np.stack([np.bincount(tor, weights=w * vals[:, j], minlength=n_t) for j in range(4)])

    familia_slugs = set(CLUBES_ADR52)
    bloqueadas, filas_u, reps_u = [], [], {}
    por_club: dict = {}
    for slug, club, dt in unidades_rep:
        try:
            check_verificada(club, dt)
        except SystemExit:
            bloqueadas.append({"club": club, "coach": dt}); continue
        por_club.setdefault(club, {"slug": slug, "coaches": []})["coaches"].append(dt)

    casos = m36.casos_desde([(c, e) for c, inf in por_club.items() for e in inf["coaches"]])
    for club, info in sorted(por_club.items()):
        base_m = np.array([m for m in partidos if club not in equipos_de[m]])
        base_t = np.array([tpos[torneo_de[m]] for m in base_m])
        base_ma = [(m, a) for m in base_m for a in sorted(equipos_de[m])]
        base_idx = {m: i for i, m in enumerate(base_m)}
        b_vals, b_tor = matriz(base_ma)
        b_row = np.array([base_idx[m] for m, _ in base_ma], dtype=np.int64)
        rng_b = m30.semilla(args.seed, club, "__base__")
        pesos_b = [np.ones(len(base_m))]
        for _ in range(args.n_boot):
            w = np.zeros(len(base_m))
            for t in range(n_t):
                ix = np.flatnonzero(base_t == t)
                if ix.size:
                    w[ix] = np.bincount(rng_b.integers(0, ix.size, ix.size), minlength=ix.size)
            pesos_b.append(w)
        Vb = [vectores(b_vals, b_tor, w[b_row]) for w in pesos_b]
        for dt in info["coaches"]:
            mids = np.array([m for m in partidos if coach_de.get((m, club)) == dt])
            if mids.size == 0:
                continue
            rival = {m: next(iter(equipos_de[m] - {club})) for m in mids}
            rng_u = m30.semilla(args.seed, club, dt)
            pesos_u = [np.ones(mids.size)] + [
                np.bincount(rng_u.integers(0, mids.size, mids.size), minlength=mids.size).astype(float)
                for _ in range(args.n_boot)]
            res = {}
            for lado, quien in (("of", lambda m: club), ("def", lambda m: rival[m])):
                u_vals, u_tor = matriz([(m, quien(m)) for m in mids])
                R = []
                for w_u, V_b in zip(pesos_u, Vb):
                    V_u = vectores(u_vals, u_tor, w_u)
                    c1 = tasa_estandarizada(V_u[0], V_u[1], V_b[0], V_b[1])
                    c2 = tasa_estandarizada(V_u[2], V_u[3], V_b[2], V_b[3])
                    R.append(c1 + c2)
                R = np.array(R)
                res[lado] = R
            reps_u[(club, dt)] = res
            V0 = vectores(*matriz([(m, club) for m in mids]), np.ones(mids.size))
            D0 = vectores(*matriz([(m, rival[m]) for m in mids]), np.ones(mids.size))
            fila = {"club": club, "coach": dt, "slug": info["slug"], "n_partidos": int(mids.size),
                    "en_familia": info["slug"] in familia_slugs,
                    "en_casos": dt in casos and club in casos[dt],
                    "corners_por_partido_of": float(V0[0].sum() / mids.size),
                    "corners_por_partido_def": float(D0[0].sum() / mids.size),
                    "remates_of": int(V0[2].sum()), "remates_def": int(D0[2].sum())}
            for lado in ("of", "def"):
                R = res[lado]
                for nom, (it, ib, idd) in (("C1", (0, 1, 2)), ("C2", (3, 4, 5))):
                    th, r = R[0, idd], R[1:, idd]
                    fila[f"{nom}_{lado}"] = {
                        "unidad": float(R[0, it]), "base": float(R[0, ib]), "did": float(th),
                        "ic95": list(m30.ic_basic(r, th)) if np.isfinite(th) else [None, None],
                        "p": m30.p_basic(r, th) if np.isfinite(th) else float("nan")}
            # descriptivos
            mi = set(mids.tolist())
            s_of = [s for s in corners if s["match_id"] in mi and s["atacante"] == club]
            s_df = [s for s in corners if s["match_id"] in mi and s["atacante"] != club]
            t_df = [f for f in filas_tiro if f["tipo"] == "corner" and f["match_id"] in mi and f["defensor"] == club]
            t_of = [f for f in filas_tiro if f["tipo"] == "corner" and f["match_id"] in mi and f["atacante"] == club]
            def perfil(ss):
                if not ss:
                    return {}
                tec = [s["ini"]["pass_technique"] or "sin_dato" for s in ss]
                zon = [zona_destino(xy_de(s["ini"]["location"])[1], xy_de(s["ini"]["pass_end_location"])[1]) for s in ss]
                return {"tecnica": {k: tec.count(k) / len(tec) for k in sorted(set(tec))},
                        "destino": {k: zon.count(k) / len(zon) for k in sorted(set(zon))}}
            def mapa(tt):
                return {z: {"n": sum(f["zona"] == z for f in tt),
                            "xg": float(sum(f["xg_full"] for f in tt if f["zona"] == z))}
                        for z in ("area_chica", "area_central", "area_lateral", "fuera_del_area")}
            fila["descriptivos"] = {
                "perfil_cobro_of": perfil(s_of),
                "mapa_remates_of": mapa(t_of), "mapa_remates_def": mapa(t_df),
                "xD_shot_medio_def": float(np.mean([f["xg_base"] - f["xg_full"] for f in t_df])) if t_df else None,
                "goal_open_medio_def": float(np.mean([f["goal_open"] for f in t_df])) if t_df else None,
                "goal_open_medio_of": float(np.mean([f["goal_open"] for f in t_of])) if t_of else None,
                "vmax_segunda_of": float(np.mean([vmax_segunda(s) for s in s_of])) if s_of else None,
                "vmax_segunda_def": float(np.mean([vmax_segunda(s) for s in s_df])) if s_df else None,
                "exploratorio_S10_of": float(np.mean([s["S10"] for s in s_of])) if s_of else None,
                "exploratorio_S10_def": float(np.mean([s["S10"] for s in s_df])) if s_df else None,
                "exploratorio_Sfase_of": float(np.mean([s["Sfase"] for s in s_of])) if s_of else None,
                "exploratorio_Sfase_def": float(np.mean([s["Sfase"] for s in s_df])) if s_df else None,
                "P_S_tiro_libre_of": float(np.mean([s["S"] for s in secs["tiro_libre"]
                                                    if s["match_id"] in mi and s["atacante"] == club] or [np.nan])),
                "P_S_banda_of": float(np.mean([s["S"] for s in secs["banda"]
                                               if s["match_id"] in mi and s["atacante"] == club] or [np.nan])),
            }
            filas_u.append(fila)
            print(f"  {club:<20}{dt:<26} n={mids.size:>3}  C1 of {100*fila['C1_of']['did']:+6.2f} pp  "
                  f"def {100*fila['C1_def']['did']:+6.2f} pp  C2 of {fila['C2_of']['did']:+.4f} "
                  f"def {fila['C2_def']['did']:+.4f}  ({time.time()-t0:,.0f} s)")

    fam = [(f, k) for f in filas_u if f["en_familia"]
           for k in ("C1_of", "C1_def", "C2_of", "C2_def") if np.isfinite(f[k]["p"])]
    if fam:
        qv, rech = benjamini_hochberg(np.array([f[k]["p"] for f, k in fam]), alpha=args.alpha)
        for (f, k), qi, ri in zip(fam, qv, rech):
            f[k]["q"], f[k]["rechaza"] = float(qi), bool(ri)
    n_rech = sum(f[k].get("rechaza", False) for f, k in fam)
    piso = 2.0 / (args.n_boot + 1)
    aviso = lambda m: (None if not m or piso <= args.alpha / m else
                       f"piso del p {piso:.5f} > alpha/m {args.alpha/m:.5f}: un contraste aislado no puede rechazar")
    fam_c = [(f, k) for f in filas_u if f["en_casos"]
             for k in ("C1_of", "C1_def", "C2_of", "C2_def") if np.isfinite(f[k]["p"])]
    if fam_c:
        qc, rc = benjamini_hochberg(np.array([f[k]["p"] for f, k in fam_c]), alpha=args.alpha)
        for (f, k), qi, ri in zip(fam_c, qc, rc):
            f[k]["q_casos"], f[k]["rechaza_casos"] = float(qi), bool(ri)
    n_rech_c = sum(f[k].get("rechaza_casos", False) for f, k in fam_c)

    # ---------------------------------------------------- predicciones
    try:
        prior = pl.read_parquet(args.datos / "prior_liga/transitions.parquet", columns=["poss_uid"])
        en_prior = set(prior["poss_uid"].unique().to_list())
        uid_c = [f"{s['match_id']}_{s['posesiones'][0]}" for s in corners]
        en_vista = [u for u in uid_c if u in ini_estado]
        perdida = 1 - sum(u in en_prior for u in en_vista) / max(len(en_vista), 1)
    except Exception:
        perdida = float("nan")
    ib = modelo["beta_base_ic95"]["cabeza"]
    di = modelo["delta_auc_ic95_percentil"]
    ps = liga["P_S_secuencia"].get("corner", float("nan"))
    rel = abs(prod - der_l["P_gol"]) / der_l["P_gol"] if der_l and der_l["P_gol"] > 0 else float("nan")
    pred = [
        {"n": 1, "texto": "min_actions=2 descartaba >15% de las posesiones que inician con corner",
         "valor": perdida, "cumple": perdida > 0.15,
         "nota": "la sonda (adenda 2) ya mostro 19.8% sobre TODAS las posesiones From Corner"},
        {"n": 2, "texto": "P(S|secuencia de corner) de la liga en [0.18, 0.30]", "valor": ps,
         "cumple": 0.18 <= ps <= 0.30},
        {"n": 3, "texto": "beta_cabeza < 0 con IC95 que excluye 0",
         "valor": [modelo["beta_base_estandarizado"]["cabeza"]] + ib, "cumple": ib[1] < 0},
        {"n": 4, "texto": "delta AUC > 0 con IC95 que excluye 0", "valor": [dauc] + di, "cumple": di[0] > 0},
        {"n": 5, "texto": "|cadena - producto| / cadena < 0.25 (posesion)", "valor": rel, "cumple": rel < 0.25},
        {"n": 6, "texto": "a lo sumo 10 de 84 rechazan", "valor": [n_rech, len(fam)], "cumple": n_rech <= 10},
        {"n": 7, "texto": "goal_open medio de corner < juego abierto",
         "valor": [float(go_co.mean()), float(go_ab_m.mean())], "cumple": go_co.mean() < go_ab_m.mean()},
    ]

    salida = {"adr": "ADR-55", "preinscripcion": "docs/preinscritos/ADR-55_BORRADOR.md (commit 9aa5524)",
              "reglas": REGLAS,
              "parametros": {"n_boot": args.n_boot, "n_boot_coef": args.n_boot_coef, "lam": args.lam,
                             "seed": args.seed, "torneos": torneos, "radio": RADIO_DEFENSOR},
              "universo": {"partidos": len(completos), "excluidos_d54_12": sorted(int(m) for m in incompletos)},
              "eras_bloqueadas_por_candado": bloqueadas,
              "modelo": modelo, "liga": liga, "predicciones": pred,
              "familia": {"m": len(fam), "rechazan": n_rech, "aviso_piso_p": aviso(len(fam))},
              "familia_casos": {"m": len(fam_c), "rechazan": n_rech_c, "aviso_piso_p": aviso(len(fam_c)),
                                "casos": {c: sorted(v_) for c, v_ in casos.items()}},
              "unidades": filas_u, "segundos": round(time.time() - t0, 1)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=2, ensure_ascii=False,
                                   default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("\n== predicciones preinscritas ==")
    for p_ in pred:
        print(f"  {p_['n']}. {'CUMPLE' if p_['cumple'] else 'FALLA '}  {p_['texto']}  "
              f"{json.dumps(p_['valor'], default=float)}")
    print(f"\nfamilia ADR-52: {len(fam)} contrastes, {n_rech} rechazan · "
          f"familia casos: {len(fam_c)} contrastes, {n_rech_c} rechazan · {len(filas_u)} unidades")
    for nom, m_ in (("ADR-52", len(fam)), ("casos", len(fam_c))):
        if aviso(m_):
            print(f"AVISO {nom}: {aviso(m_)}")
    print(f"escrito {args.out}  ({salida['segundos']:,.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
