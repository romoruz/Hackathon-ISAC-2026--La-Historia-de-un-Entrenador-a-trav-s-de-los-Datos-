"""
Fase 2 -- Cadena absorbente: matriz fundamental, absorcion y xT propio.

Con la particion

    P = [ Q  R ]
        [ 0  I ]

y Q sub-estocastica, se tiene

    N = (I - Q)^-1 = sum_k Q^k        (serie de Neumann)
    B = N R                            (probabilidades de absorcion)
    t = N 1                            (longitud esperada de posesion)

La convergencia de la serie exige rho(Q) < 1, equivalente a que todo estado
transitorio tenga probabilidad positiva de alcanzar absorcion. En futbol es
razonable -- toda posesion termina -- pero DEBE verificarse numericamente
porque el encogimiento puede crear renglones patologicos. Se comprueba con
`spectral_radius`; si falla, hay que podar estados inalcanzables.

N NO se calcula invirtiendo. Se resuelve (I-Q) N = I con `scipy.linalg.solve`:
mismo resultado, mejor condicionamiento numerico y menos costo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import linalg

from .grid import StateSpace


@dataclass
class AbsorbingChain:
    P: np.ndarray  # (n_transient, n_states)
    space: StateSpace

    @property
    def Q(self) -> np.ndarray:
        return self.P[:, : self.space.n_transient]

    @property
    def R(self) -> np.ndarray:
        return self.P[:, self.space.n_transient :]

    # ------------------------------------------------------------- garantias
    def spectral_radius(self) -> float:
        return float(np.max(np.abs(linalg.eigvals(self.Q))))

    def check(self, tol: float = 1e-8) -> dict[str, float | bool]:
        rho = self.spectral_radius()
        row_sums = self.P.sum(axis=1)
        return {
            "rho_Q": rho,
            "rho_ok": rho < 1.0 - tol,
            "max_row_sum_error": float(np.abs(row_sums - 1.0).max()),
            "stochastic_ok": bool(np.allclose(row_sums, 1.0, atol=1e-8)),
            "Q_inf_norm": float(np.abs(self.Q).sum(axis=1).max()),
        }

    # -------------------------------------------------------------- nucleo
    def fundamental(self) -> np.ndarray:
        """N = (I - Q)^-1, resuelto como sistema lineal."""
        n = self.space.n_transient
        A = np.eye(n) - self.Q
        return linalg.solve(A, np.eye(n), assume_a="gen")

    def absorption(self) -> np.ndarray:
        """B = N R, forma (n_transient, n_absorbing)."""
        n = self.space.n_transient
        A = np.eye(n) - self.Q
        return linalg.solve(A, self.R, assume_a="gen")

    def expected_length(self) -> np.ndarray:
        """t_i = numero esperado de acciones antes de absorber, desde i."""
        n = self.space.n_transient
        A = np.eye(n) - self.Q
        return linalg.solve(A, np.ones(n), assume_a="gen")

    # --------------------------------------------------------------- valores
    def xt(self) -> np.ndarray:
        """P(gol en esta posesion | estado). Tu xT, construido desde cero."""
        return self.absorption()[:, self.space.absorbing.index("GOAL")]

    def shot_prob(self) -> np.ndarray:
        B = self.absorption()
        g = self.space.absorbing.index("GOAL")
        s = self.space.absorbing.index("SHOT_NOGOAL")
        return B[:, g] + B[:, s]

    def visit_distribution(self, alpha: np.ndarray | None = None) -> np.ndarray:
        """nu = distribucion de visitas esperadas, normalizada.

        Es el objeto que se compara entre DTs con W_1 en la Fase 8: resume
        "donde vive" el equipo en una sola medida de probabilidad sobre estados.
        """
        n = self.space.n_transient
        if alpha is None:
            alpha = np.ones(n) / n
        alpha = np.asarray(alpha, dtype=float)
        alpha = alpha / max(alpha.sum(), 1e-12)
        A = np.eye(n) - self.Q
        nu = linalg.solve(A.T, alpha, assume_a="gen")
        return nu / max(nu.sum(), 1e-12)

    # ------------------------------------------------------- agregacion zonal
    def by_zone(self, values: np.ndarray) -> np.ndarray:
        """Colapsa un vector de estados a la malla nx x ny promediando fases."""
        sp = self.space
        v = np.asarray(values).reshape(sp.n_zones, len(sp.phases))
        return v.mean(axis=1).reshape(sp.nx, sp.ny)

    def zone_weighted(self, values: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Igual que `by_zone` pero ponderando fases por masa observada."""
        sp = self.space
        v = np.asarray(values).reshape(sp.n_zones, len(sp.phases))
        w = np.asarray(weights).reshape(sp.n_zones, len(sp.phases))
        w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-12)
        return (v * w).sum(axis=1).reshape(sp.nx, sp.ny)


def empirical_start_distribution(trans, space: StateSpace) -> np.ndarray:
    """alpha empirico: donde arrancan realmente las posesiones del equipo."""
    import polars as pl

    first = trans.sort(["poss_uid", "event_index"]).group_by("poss_uid", maintain_order=True).first()
    alpha = np.zeros(space.n_transient)
    idx = first["from_state"].to_numpy().astype(int)
    np.add.at(alpha, idx, 1.0)
    del pl
    return alpha / max(alpha.sum(), 1e-12)
