"""Modelo de xG sobre el `shot_freeze_frame`: features y logística sin sklearn.

Vive en `src/` y no en `scripts/` porque lo consumen DOS scripts:
`25_goal_open_eras.py` (un par de eras) y `26_goal_open_barrido.py` (la familia
completa con FDR).

Tenerlo duplicado sería el bug #2 del proyecto —"estimador puntual e IC con
recetas distintas"— con otra cara: dos copias que divergen en silencio y dan
números que no cuadran entre secciones del mismo reporte.

La logística va implementada con numpy (IRLS). No entra sklearn: ADR-19
restringe las dependencias, y ver la verosimilitud escrita conecta con el curso
de inferencia mejor que una llamada a `.fit()`.
"""
from __future__ import annotations

import ast

import numpy as np

from dtdecoder.geometria_remate import (
    CENTRO_META, POSTE_1, POSTE_2, goal_open,
)

SEED = 20260826

# Las dos listas de features, en un solo sitio: xG_base usa solo ATA, xG_full
# usa ATA + DEF. La diferencia entre los dos ES el aporte de la geometría.
ATA = ["dist_meta", "angulo"]
DEF = ["goal_open", "d_def_cerca", "n_def_3m", "gk_prof", "gk_desv"]


# ======================================================================
# Parseo — el freeze frame es un REPR DE PYTHON, no JSON (scripts/24 §2)
# ======================================================================
def _lit(s):
    if s is None or isinstance(s, (list, tuple)):
        return s
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None


def xy(s):
    v = _lit(s)
    try:
        return float(v[0]), float(v[1])
    except Exception:
        return (np.nan, np.nan)


# ======================================================================
# Features
# ======================================================================
def angulo_porteria(sx, sy):
    """Ángulo subtendido por los postes desde el punto de remate."""
    a = np.array([POSTE_1[0] - sx, POSTE_1[1] - sy])
    b = np.array([POSTE_2[0] - sx, POSTE_2[1] - sy])
    c = a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
    return float(np.arccos(np.clip(c, -1, 1)))


def dist_punto_recta(px, py, x1, y1, x2, y2):
    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    return float(num / (np.hypot(y2 - y1, x2 - x1) + 1e-12))


def features(loc, frame, r, cont):
    sx, sy = xy(loc)
    ff = _lit(frame)
    if ff is None or not np.isfinite(sx):
        return None

    rivales = [j for j in ff if not j.get("teammate", False)]
    def pos(j):
        return (j.get("position") or {}).get("name")
    porteros = [j for j in rivales if pos(j) == "Goalkeeper"]
    campo = [j for j in rivales if pos(j) != "Goalkeeper"]

    def loc_de(j):
        c = j.get("location") or [np.nan, np.nan]
        return float(c[0]), float(c[1])

    xy_campo = [loc_de(j) for j in campo]
    d_min = min((np.hypot(sx - a, sy - b) for a, b in xy_campo), default=np.nan)
    n_cerca = sum(1 for a, b in xy_campo if np.hypot(sx - a, sy - b) <= 3.0)

    if porteros:
        gx, gy = loc_de(porteros[0])
        gk_prof = 120.0 - gx
        gk_desv = dist_punto_recta(gx, gy, sx, sy, *CENTRO_META)
    else:
        # Sin portero en la foto no hay feature de portero. NO se imputa.
        gk_prof = gk_desv = np.nan

    return {
        "dist_meta": float(np.hypot(CENTRO_META[0] - sx, CENTRO_META[1] - sy)),
        "angulo": angulo_porteria(sx, sy),
        "goal_open": goal_open(sx, sy, xy_campo, r=r, cont=cont),
        "d_def_cerca": float(d_min) if np.isfinite(d_min) else np.nan,
        "n_def_3m": float(n_cerca),
        "gk_prof": gk_prof,
        "gk_desv": gk_desv,
        "n_def_campo": float(len(xy_campo)),
    }


# ======================================================================
# Logística regularizada por IRLS. Sin sklearn (ADR-19).
# ======================================================================
def ajusta_logistica(X, y, lam=3.0, iters=60):
    """Máxima verosimilitud penalizada con L2 sobre X ya estandarizado.

    El intercepto NO se penaliza. `lam` es el inverso de la C de sklearn:
    lam=3 ~ C=0.33, comparable al C=0.3 del proyecto de córners, elegido por la
    misma razón: con ~270 goles y 7 features, sin penalización el ajuste es
    inestable.
    """
    n, p = X.shape
    Z = np.hstack([np.ones((n, 1)), X])
    b = np.zeros(p + 1)
    pen = np.full(p + 1, lam)
    pen[0] = 0.0
    for _ in range(iters):
        eta = np.clip(Z @ b, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = np.clip(mu * (1 - mu), 1e-9, None)
        g = Z.T @ (y - mu) - pen * b
        H = -(Z.T * W) @ Z - np.diag(pen)
        try:
            paso = np.linalg.solve(H, -g)
        except np.linalg.LinAlgError:
            paso = np.linalg.lstsq(H, -g, rcond=None)[0]
        b_new = b + paso
        if np.max(np.abs(b_new - b)) < 1e-9:
            b = b_new
            break
        b = b_new
    return b


def predice(b, X):
    eta = np.clip(np.hstack([np.ones((len(X), 1)), X]) @ b, -30, 30)
    return 1.0 / (1.0 + np.exp(-eta))


def fuera_de_pliegue(X, y, bloques, lam=3.0, k=5, rng=None):
    """Predicciones OOF con pliegues POR BLOQUE.

    Partir por remate metería remates del mismo partido en entrenamiento y
    validación: fuga optimista. Los pliegues respetan el partido, igual que la
    validación cruzada por bloques de `09_GLOSSARY.md`.
    """
    rng = rng or np.random.default_rng(SEED)
    ubloq = np.unique(bloques)
    orden = np.sort(ubloq)                     # ordenar ANTES de barajar (bug #8)
    rng.shuffle(orden)
    pliegue_de = {b: i % k for i, b in enumerate(orden)}
    pl_idx = np.array([pliegue_de[b] for b in bloques])

    p = np.zeros(len(y))
    for f in range(k):
        tr, te = pl_idx != f, pl_idx == f
        if y[tr].sum() < 5 or te.sum() == 0:
            p[te] = y[tr].mean() if tr.sum() else y.mean()
            continue
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        b = ajusta_logistica((X[tr] - mu) / sd, y[tr], lam=lam)
        p[te] = predice(b, (X[te] - mu) / sd)
    return p
