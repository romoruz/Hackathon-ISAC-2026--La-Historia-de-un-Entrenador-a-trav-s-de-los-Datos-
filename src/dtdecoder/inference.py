"""
Fase 3 -- Inferencia: huella tactica con control de error.

TRES CORRECCIONES QUE CASI NADIE HACE Y QUE AQUI ESTAN IMPLEMENTADAS:

1. BOOTSTRAP POR POSESION, NO POR EVENTO.
   Los eventos dentro de una posesion estan fuertemente correlacionados.
   Remuestrear acciones individuales asume independencia y produce intervalos
   artificialmente angostos: se "detecta" estilo donde solo hay ruido. La
   unidad de remuestreo correcta es la posesion completa (block bootstrap).

2. SE BOOTSTRAPEA LA DIFERENCIA, NO DOS INTERVALOS.
   Intervalos disjuntos implican diferencia significativa, pero intervalos
   que se traslapan NO implican no-significancia. Aqui se construye
   directamente el IC de (p*_DT - p*_liga) y se revisa si el cero queda fuera.

3. LA NULA DEL LRT SE CALIBRA POR BOOTSTRAP, NO SE ASUME CHI-CUADRADA.
   El estadistico

       G2_i = 2 * sum_j n_ij log( n_ij / (n_i * q_ij) )

   es el cociente de verosimilitudes para H0: p_i. = q_i. (simple vs
   compuesta, multinomial). Su distribucion asintotica chi2_{k-1} supone
   observaciones independientes, supuesto que la dependencia intra-posesion
   rompe. Se obtiene la nula remuestreando posesiones del pool de la liga con
   el MISMO numero de posesiones que tiene el DT.

4. MULTIPLICIDAD. Con nx*ny*n_fases renglones se testean decenas de hipotesis.
   Se controla la tasa de falso descubrimiento con Benjamini-Hochberg.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from .estimate import shrink
from .grid import StateSpace

_EPS = 1e-12


# --------------------------------------------------------------------------
# Indexado de posesiones para remuestreo rapido
# --------------------------------------------------------------------------
@dataclass
class PossessionIndex:
    """Estructura tipo CSR: transiciones agrupadas por posesion.

    Permite remuestrear miles de replicas sin reconstruir DataFrames.
    """

    flat: np.ndarray  # indices aplanados from*n_states + to, en orden de posesion
    starts: np.ndarray
    lens: np.ndarray
    n_transient: int
    n_states: int

    @property
    def n_poss(self) -> int:
        return len(self.starts)

    @classmethod
    def build(cls, trans: pl.DataFrame, space: StateSpace) -> PossessionIndex:
        df = trans.sort("poss_uid")
        codes = df["poss_uid"].to_numpy()
        i = df["from_state"].to_numpy().astype(np.int64)
        j = df["to_state"].to_numpy().astype(np.int64)
        flat = i * space.n_states + j
        # fronteras de grupo
        change = np.empty(len(codes), dtype=bool)
        change[0] = True
        change[1:] = codes[1:] != codes[:-1]
        starts = np.flatnonzero(change)
        ends = np.append(starts[1:], len(codes))
        return cls(flat, starts, ends - starts, space.n_transient, space.n_states)

    def counts_from(self, chosen: np.ndarray) -> np.ndarray:
        """Matriz de conteos a partir de una seleccion de posesiones."""
        idx = _gather_ranges(self.starts[chosen], self.lens[chosen])
        bc = np.bincount(self.flat[idx], minlength=self.n_transient * self.n_states)
        return bc.reshape(self.n_transient, self.n_states).astype(np.float64)

    def counts_all(self) -> np.ndarray:
        bc = np.bincount(self.flat, minlength=self.n_transient * self.n_states)
        return bc.reshape(self.n_transient, self.n_states).astype(np.float64)


def _gather_ranges(starts: np.ndarray, lens: np.ndarray) -> np.ndarray:
    """Concatena rangos [s, s+l) de forma vectorizada."""
    total = int(lens.sum())
    if total == 0:
        return np.empty(0, dtype=np.int64)
    out = np.ones(total, dtype=np.int64)
    ends = np.cumsum(lens)
    out[0] = starts[0]
    if len(starts) > 1:
        out[ends[:-1]] = starts[1:] - (starts[:-1] + lens[:-1]) + 1
    return np.cumsum(out)


# --------------------------------------------------------------------------
# Estadistico G2
# --------------------------------------------------------------------------
def g2_rows(C: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """G2 por renglon contra la matriz de referencia Q (liga)."""
    n = C.sum(axis=1, keepdims=True)
    expected = n * Q
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(C > 0, C * np.log(np.maximum(C, _EPS) / np.maximum(expected, _EPS)), 0.0)
    return 2.0 * term.sum(axis=1)


@dataclass
class TacticalFingerprint:
    g2_obs: np.ndarray
    pvalue: np.ndarray
    qvalue: np.ndarray
    rejected: np.ndarray
    row_counts: np.ndarray
    tested: np.ndarray

    def to_frame(self, space: StateSpace) -> pl.DataFrame:
        labels = space.transient_labels()
        return pl.DataFrame(
            {
                "state": labels,
                "n": self.row_counts,
                "G2": self.g2_obs,
                "p_value": self.pvalue,
                "q_value": self.qvalue,
                "rejected": self.rejected,
                "tested": self.tested,
            }
        ).sort("G2", descending=True)


def tactical_fingerprint(
    trans_dt: pl.DataFrame,
    trans_league: pl.DataFrame,
    space: StateSpace,
    league_P: np.ndarray,
    n_boot: int = 2000,
    seed: int = 0,
    min_row_count: int = 15,
    alpha: float = 0.05,
) -> TacticalFingerprint:
    """Mapa de huella tactica: en que estados el DT se sale de la liga."""
    idx_dt = PossessionIndex.build(trans_dt, space)
    idx_lg = PossessionIndex.build(trans_league, space)

    C_dt = idx_dt.counts_all()
    g2_obs = g2_rows(C_dt, league_P)
    row_counts = C_dt.sum(axis=1)
    tested = row_counts >= min_row_count

    rng = np.random.default_rng(seed)
    m = idx_dt.n_poss
    null = np.empty((n_boot, space.n_transient))
    for b in range(n_boot):
        chosen = rng.integers(0, idx_lg.n_poss, size=m)
        null[b] = g2_rows(idx_lg.counts_from(chosen), league_P)

    # p-valor bootstrap con correccion +1 (evita p=0, Davison & Hinkley 1997)
    pval = (1.0 + (null >= g2_obs[None, :]).sum(axis=0)) / (1.0 + n_boot)
    pval = np.where(tested, pval, 1.0)

    qval, rejected = benjamini_hochberg(pval, alpha, mask=tested)
    return TacticalFingerprint(g2_obs, pval, qval, rejected, row_counts, tested)


# --------------------------------------------------------------------------
# Bootstrap de la diferencia celda a celda
# --------------------------------------------------------------------------
@dataclass
class DiffCI:
    diff: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    excludes_zero: np.ndarray

    def top_cells(self, space: StateSpace, k: int = 20) -> pl.DataFrame:
        labels_from = space.transient_labels()
        labels_to = space.state_labels()
        ii, jj = np.where(self.excludes_zero)
        rows = [
            {
                "from": labels_from[a],
                "to": labels_to[b],
                "diff": float(self.diff[a, b]),
                "lo": float(self.lo[a, b]),
                "hi": float(self.hi[a, b]),
            }
            for a, b in zip(ii, jj)
        ]
        if not rows:
            return pl.DataFrame(
                schema={"from": pl.Utf8, "to": pl.Utf8, "diff": pl.Float64,
                        "lo": pl.Float64, "hi": pl.Float64}
            )
        return (
            pl.DataFrame(rows)
            .with_columns(pl.col("diff").abs().alias("_abs"))
            .sort("_abs", descending=True)
            .drop("_abs")
            .head(k)
        )


def _diff_estimate(
    C_focus: np.ndarray, C_base: np.ndarray, prior: np.ndarray, lam: float
) -> np.ndarray:
    """Receta unica del estimador de la diferencia.

    CRITICO: el estimador puntual y cada replica bootstrap DEBEN calcularse con
    esta misma funcion. Si el observado usa una linea base distinta a la de las
    replicas, el IC deja de estar centrado en el estimador y pueden salir
    intervalos que no contienen su propio punto -- sintoma inequivoco de que el
    remuestreo no esta estimando la incertidumbre de la cantidad reportada.
    """
    P_base = shrink(C_base, prior, 0.0)
    P_focus = shrink(C_focus, P_base, lam)
    return P_focus - P_base


def bootstrap_diff(
    trans_focus: pl.DataFrame,
    trans_base: pl.DataFrame,
    space: StateSpace,
    prior: np.ndarray,
    lam: float,
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
    method: str = "basic",
) -> DiffCI:
    """IC de p*_foco - p*_base, remuestreando AMBOS lados por posesion.

    `method`:
      "percentile" -- cuantiles crudos de las replicas.
      "basic"      -- percentil invertido, [2*theta - q_hi, 2*theta - q_lo].
                      Corrige el sesgo de primer orden del bootstrap y es el
                      default: el encogimiento introduce sesgo hacia el prior,
                      justo el caso donde el percentil crudo se descentra.
    """
    idx_f = PossessionIndex.build(trans_focus, space)
    idx_b = PossessionIndex.build(trans_base, space)
    rng = np.random.default_rng(seed)

    diff_obs = _diff_estimate(idx_f.counts_all(), idx_b.counts_all(), prior, lam)

    boots = np.empty((n_boot, space.n_transient, space.n_states), dtype=np.float32)
    for b in range(n_boot):
        c_f = idx_f.counts_from(rng.integers(0, idx_f.n_poss, size=idx_f.n_poss))
        c_b = idx_b.counts_from(rng.integers(0, idx_b.n_poss, size=idx_b.n_poss))
        boots[b] = _diff_estimate(c_f, c_b, prior, lam).astype(np.float32)

    a = (1.0 - level) / 2.0
    q_lo = np.quantile(boots, a, axis=0)
    q_hi = np.quantile(boots, 1.0 - a, axis=0)
    if method == "percentile":
        lo, hi = q_lo, q_hi
    elif method == "basic":
        lo, hi = 2.0 * diff_obs - q_hi, 2.0 * diff_obs - q_lo
    else:
        raise ValueError(f"method desconocido: {method}")
    return DiffCI(diff_obs, lo, hi, (lo > 0) | (hi < 0))


# --------------------------------------------------------------------------
# Control de multiplicidad
# --------------------------------------------------------------------------
def benjamini_hochberg(
    p: np.ndarray, alpha: float = 0.05, mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (q-valores, rechazos) controlando FDR al nivel alpha."""
    p = np.asarray(p, dtype=float)
    if mask is None:
        mask = np.ones_like(p, dtype=bool)
    idx = np.flatnonzero(mask)
    q = np.ones_like(p)
    rej = np.zeros_like(p, dtype=bool)
    if idx.size == 0:
        return q, rej

    sub = p[idx]
    order = np.argsort(sub)
    m = len(sub)
    ranked = sub[order]
    q_sub = ranked * m / np.arange(1, m + 1)
    q_sub = np.minimum.accumulate(q_sub[::-1])[::-1]
    q_sub = np.clip(q_sub, 0.0, 1.0)

    q_final = np.empty(m)
    q_final[order] = q_sub
    q[idx] = q_final
    rej[idx] = q_final <= alpha
    return q, rej


# --------------------------------------------------------------------------
# Contraste entre contextos (el hallazgo vendible)
# --------------------------------------------------------------------------
def context_contrast(
    trans: pl.DataFrame,
    space: StateSpace,
    league_P: np.ndarray,
    lam: float,
    by: str = "score_state",
) -> pl.DataFrame:
    """Compara P(.|c) entre niveles de contexto: filosofia vs reactividad.

    Si P(.|ganando) y P(.|perdiendo) difieren mucho, el "estilo" es reactivo al
    marcador y no una idea de juego impuesta. Si se parecen, hay evidencia de
    filosofia. Distancia reportada: TV por renglon, ponderada por masa.
    """
    from .estimate import count_matrix

    groups = {
        str(key[0]): count_matrix(sub, space)
        for key, sub in trans.group_by([by], maintain_order=True)
    }
    keys = sorted(groups)
    rows = []
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            ka, kb = keys[a], keys[b]
            Pa = shrink(groups[ka], league_P, lam)
            Pb = shrink(groups[kb], league_P, lam)
            w = groups[ka].sum(axis=1) + groups[kb].sum(axis=1)
            w = w / max(w.sum(), _EPS)
            tv = 0.5 * np.abs(Pa - Pb).sum(axis=1)
            rows.append(
                {
                    "context_a": ka,
                    "context_b": kb,
                    "tv_weighted": float((tv * w).sum()),
                    "tv_max": float(tv.max()),
                    "n_a": float(groups[ka].sum()),
                    "n_b": float(groups[kb].sum()),
                }
            )
    return pl.DataFrame(rows)
