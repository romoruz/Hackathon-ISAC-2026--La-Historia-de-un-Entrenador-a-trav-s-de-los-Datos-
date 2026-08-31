"""
Fase 0.1 -- Particion del campo y espacio de estados.

El espacio de estados es s = (z, phi) donde:
  z   : zona de la malla nx x ny
  phi : fase de juego {open, transition, set_piece}

El contexto c (marcador) NO entra al estado: se usa como estratificacion,
porque meterlo al estado multiplica el numero de parametros sin multiplicar
los datos (ver README, seccion "El trade-off que decide tu alcance").

Estados absorbentes: GOAL, SHOT_NOGOAL, LOSS, OUT.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ABSORBING = ("GOAL", "SHOT_NOGOAL", "LOSS", "OUT")
PHASES = ("open", "transition", "restart", "set_piece")


@dataclass(frozen=True)
class StateSpace:
    """Espacio de estados producto (zona x fase) + estados absorbentes."""

    nx: int
    ny: int
    length: float = 120.0
    width: float = 80.0
    phases: tuple[str, ...] = PHASES
    absorbing: tuple[str, ...] = ABSORBING

    # ---------------------------------------------------------------- zonas
    @property
    def n_zones(self) -> int:
        return self.nx * self.ny

    @property
    def n_transient(self) -> int:
        return self.n_zones * len(self.phases)

    @property
    def n_absorbing(self) -> int:
        return len(self.absorbing)

    @property
    def n_states(self) -> int:
        return self.n_transient + self.n_absorbing

    def zone_of(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Mapea coordenadas StatsBomb a indice de zona en [0, n_zones).

        Las coordenadas se recortan al campo: StatsBomb a veces reporta
        x=120.1 en remates o y=-0.2 en centros desde la linea de fondo.
        """
        x = np.clip(np.asarray(x, dtype=float), 0.0, self.length - 1e-9)
        y = np.clip(np.asarray(y, dtype=float), 0.0, self.width - 1e-9)
        ix = np.floor(x / self.length * self.nx).astype(int)
        iy = np.floor(y / self.width * self.ny).astype(int)
        return ix * self.ny + iy

    def zone_centroid(self, z: int) -> tuple[float, float]:
        ix, iy = divmod(int(z), self.ny)
        cx = (ix + 0.5) * self.length / self.nx
        cy = (iy + 0.5) * self.width / self.ny
        return cx, cy

    def zone_centroids(self) -> np.ndarray:
        """(n_zones, 2) en metros -- metrica base para la W_1 de la Fase 8."""
        return np.array([self.zone_centroid(z) for z in range(self.n_zones)])

    # --------------------------------------------------------------- espejo
    def mirror_zone(self, z: np.ndarray) -> np.ndarray:
        """Zona en el marco del rival -> zona en el marco del club.

        StatsBomb normaliza al marco de ataque del EJECUTANTE. Verificado
        empiricamente sobre las filas de los rivales el 2026-08-24: los remates
        salen de x~104 (club) y x~103 (rivales), y los saques de meta de x~7 en
        ambos lados. Por tanto, para leer las zonas del rival desde nuestra
        perspectiva hay que reflejar (x, y) -> (120 - x, 80 - y).

        Como la malla es UNIFORME, esa reflexion de coordenadas es exactamente
        la permutacion de indices

            (ix, iy) -> (nx - 1 - ix, ny - 1 - iy)

        Se implementa sobre INDICES y no sobre coordenadas a proposito:

          - mantiene la estimacion de la cadena en el marco nativo, donde
            `coordinate_sanity` sigue siendo valido. Con coordenadas reflejadas
            daria corr ~ -0.72, o sea `ok = False` en cada corrida sin que nada
            estuviera realmente mal;
          - no interactua con el `clip` de `zone_of` ni con punto flotante;
          - aisla la transformacion riesgosa en una funcion pura y testeable,
            que es la leccion del bug #12 (eje Y espejeado).

        Es involutiva: mirror_zone(mirror_zone(z)) == z.
        """
        z = np.asarray(z, dtype=int)
        ix, iy = np.divmod(z, self.ny)
        return (self.nx - 1 - ix) * self.ny + (self.ny - 1 - iy)

    def mirror_state(self, s: np.ndarray) -> np.ndarray:
        """Igual, sobre indices de estado transitorio.

        La FASE no se refleja: `phase` describe el origen de la posesion
        (open / transition / restart / set_piece), no una posicion en el campo.
        """
        s = np.asarray(s, dtype=int)
        n_ph = len(self.phases)
        z, ph = np.divmod(s, n_ph)
        return self.mirror_zone(z) * n_ph + ph

    # -------------------------------------------------------------- indices
    def transient_index(self, zone: np.ndarray, phase_idx: np.ndarray) -> np.ndarray:
        """(z, phi) -> indice de estado transitorio en [0, n_transient)."""
        return np.asarray(zone, dtype=int) * len(self.phases) + np.asarray(phase_idx, dtype=int)

    def absorbing_index(self, name: str) -> int:
        """Nombre de estado absorbente -> indice global (offset por transitorios)."""
        return self.n_transient + self.absorbing.index(name)

    def phase_index(self, name: str) -> int:
        return self.phases.index(name)

    # --------------------------------------------------------------- labels
    def transient_labels(self) -> list[str]:
        out = []
        for z in range(self.n_zones):
            ix, iy = divmod(z, self.ny)
            for ph in self.phases:
                out.append(f"z{ix}{iy}|{ph}")
        return out

    def state_labels(self) -> list[str]:
        return self.transient_labels() + list(self.absorbing)


def phase_map(cfg_phases: dict[str, list[str]]) -> dict[str, str]:
    """Invierte el mapeo del config: play_pattern -> nombre de fase."""
    inv: dict[str, str] = {}
    for phase, patterns in cfg_phases.items():
        for p in patterns:
            inv[p] = phase
    return inv
