"""
Generador sintetico con el ESQUEMA REAL de StatsBomb.

Sirve para dos cosas:
  1. Tests: el pipeline se valida sin depender del API.
  2. Recuperacion de parametros: se genera un DT con un sesgo conocido y se
     comprueba que la Fase 3 lo detecta. Ese experimento es la mejor evidencia
     de que tu metodo funciona, y va en el reporte.
"""

from __future__ import annotations

import numpy as np
import polars as pl

PLAY_PATTERNS = ["Regular Play", "From Counter", "From Corner", "From Free Kick", "From Throw In"]

# Plantilla sintetica por equipo. `player`/`player_id` faltaban pese a que el
# docstring promete "el ESQUEMA REAL": los tests pasaban en verde mientras el
# generador omitia columnas que el pipeline real si recibe. Cuando
# `build_transitions` empezo a exigir `player_id` (para separar el efecto del
# entrenador del efecto del plantel), 20 tests reventaron de golpe.
#
# Leccion: un generador sintetico que no reproduce el esquema completo es un
# test que valida menos de lo que aparenta.
JUGADORES_POR_EQUIPO = 14


def synth_events(
    n_matches: int = 40,
    teams: tuple[str, ...] = ("Club A", "Club B", "Club C", "Club D"),
    dt_team: str = "Club A",
    dt_bias: float = 0.35,
    seed: int = 7,
) -> pl.DataFrame:
    """Genera eventos con columnas del volcado plano de Hudl StatsBomb.

    `dt_bias` inclina a `dt_team` a progresar por el centro del campo; el resto
    de la liga progresa uniformemente. Es el efecto que la Fase 3 debe recuperar.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    ev_index = 0

    # id de jugador unico y estable por (equipo, dorsal)
    plantillas = {
        t: [(1000 * (k + 1) + d, f"Jugador {d} de {t}") for d in range(JUGADORES_POR_EQUIPO)]
        for k, t in enumerate(teams)
    }

    for match in range(n_matches):
        pair = rng.choice(len(teams), size=2, replace=False)
        home, away = teams[pair[0]], teams[pair[1]]
        poss_id = 0
        minute = 0
        for _ in range(rng.integers(140, 200)):
            poss_id += 1
            team = home if rng.random() < 0.5 else away
            biased = team == dt_team
            pattern = str(rng.choice(PLAY_PATTERNS, p=[0.7, 0.1, 0.06, 0.08, 0.06]))

            x = float(rng.uniform(10, 60))
            y = float(rng.uniform(5, 75))
            n_actions = int(rng.integers(2, 9))
            minute = min(94, minute + int(rng.integers(0, 2)))

            for a in range(n_actions):
                dx = float(rng.gamma(2.0, 5.0))
                if biased:
                    # tira al centro del carril
                    dy = float(rng.normal((40.0 - y) * dt_bias, 8.0))
                else:
                    dy = float(rng.normal(0.0, 12.0))
                nx_ = float(np.clip(x + dx, 0, 119.9))
                ny_ = float(np.clip(y + dy, 0, 79.9))

                shoot_p = 0.02 + 0.20 * max(0.0, (nx_ - 90.0) / 30.0)
                is_last = a == n_actions - 1
                if is_last and rng.random() < shoot_p * 3:
                    etype, outcome = "Shot", ("Goal" if rng.random() < 0.11 else "Saved")
                elif rng.random() < 0.25:
                    etype, outcome = "Carry", None
                else:
                    fail = rng.random() < (0.14 if not is_last else 0.5)
                    etype = "Pass"
                    outcome = ("Out" if rng.random() < 0.3 else "Incomplete") if fail else None

                pid, pname = plantillas[team][int(rng.integers(0, JUGADORES_POR_EQUIPO))]
                base = {
                    "id": f"e{ev_index}",
                    "index": ev_index,
                    "match_id": match,
                    "period": 1 if minute < 45 else 2,
                    "minute": minute,
                    "second": int(rng.integers(0, 60)),
                    "type": etype,
                    "team": team,
                    "possession": poss_id,
                    "possession_team": team,
                    "play_pattern": pattern,
                    "player": pname,
                    "player_id": pid,
                    "location": [x, y],
                    "duration": float(rng.gamma(2.0, 0.6)),
                    "pass_end_location": [nx_, ny_] if etype == "Pass" else None,
                    "carry_end_location": [nx_, ny_] if etype == "Carry" else None,
                    "shot_end_location": [120.0, 40.0] if etype == "Shot" else None,
                    "pass_outcome": outcome if etype == "Pass" else None,
                    "shot_outcome": outcome if etype == "Shot" else None,
                    "shot_statsbomb_xg": float(rng.beta(1.4, 9.0)) if etype == "Shot" else None,
                    # StatsBomb escribe la llave o la OMITE; NUNCA `false`.
                    # Medido sobre el volcado real: 114,552 true, 0 false,
                    # 468,963 null. Un generador que emite False reproduce un
                    # esquema que no existe, y los tests del fill_null pasarian
                    # en verde sin probar nada. Es el error de proceso #2 del
                    # proyecto, repetido.
                    "under_pressure": True if rng.random() < 0.25 else None,
                }
                rows.append(base)
                ev_index += 1
                if etype == "Shot" or (etype == "Pass" and outcome is not None):
                    break
                x, y = nx_, ny_

    return pl.DataFrame(rows, strict=False)


def write_synth(path: str, **kwargs) -> str:
    synth_events(**kwargs).write_parquet(path)
    return path
