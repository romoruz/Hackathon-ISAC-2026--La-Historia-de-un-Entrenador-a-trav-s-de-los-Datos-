"""Geometría del `shot_freeze_frame`: cuánta portería ve realmente el rematador.

Portado del proyecto de córners (`02_capa2_supresion.py::goal_open_fraction`)
con tres correcciones. Ver ADR-51.

QUÉ MIDE
--------
`goal_open` es una **integral de visibilidad**: la fracción de la boca de meta
NO tapada por los defensores de campo, vista desde el punto de remate.

Desde $s$, la portería subtiende el intervalo angular
$I=[\\varphi(P_1),\\varphi(P_2)]$. Cada defensor, modelado como disco de radio
$r$, proyecta una sombra angular centrada en su rumbo $\\varphi(D_j)$ de
semiancho $\\arcsin(r/\\lVert s-D_j\\rVert)$. Entonces:

$$\\text{goal\\_open} = 1 - \\frac{|I \\cap \\bigcup_j S_j|}{|I|}$$

Se calcula por unión de intervalos en 1-D: $O(m\\log m)$.

POR QUÉ REEMPLAZA AL CONTEO EN EL CONO
--------------------------------------
Un defensor "dentro del cono de tiro" pero descolocado **no bloquea la línea de
visión**. `goal_open` mide bloqueo real y es mucho menos colineal que
`n_def_cone` / `n_def_ahead` / `n_def_box`, que además son colineales entre sí.

LAS TRES CORRECCIONES RESPECTO AL ORIGINAL
------------------------------------------
1. **La frontera de `arctan2` en $x_s > 120$.** `04_DATA_CONTRACT.md` §3.2
   documenta que StatsBomb reporta $x = 120.1$ en remates: el balón cruzando la
   línea no es un error de los datos. Con $x_s > 120$ la portería queda DETRÁS
   del tirador, los rumbos saltan cerca de $\\pm\\pi$, y `min/max` deja de
   definir el intervalo. El original devolvía un número plausible y equivocado,
   sin avisar. Aquí se recorta a `X_MAX_TIRO` y se **cuenta** cuántas veces pasa.
2. **Sin imputación silenciosa.** Devuelve `nan` en los casos degenerados en vez
   de un valor por defecto. Quien llame decide si descarta o imputa, y lo
   declara.
3. **`r` es explícito.** El original traía `r=0.5` cableado. El radio del disco
   es una decisión, no un hecho, y debe poder barrerse en sensibilidad.

MEDIDA ANGULAR, NO LINEAL
-------------------------
`goal_open` es una fracción **de ángulo**. La proyección de las sombras sobre la
línea de meta (para dibujar) es una fracción **lineal**, y NO es la misma
cantidad: la proyección comprime distinto según el rumbo. `segmentos_bloqueados`
existe solo para dibujar, y su docstring lo repite.
"""
from __future__ import annotations

import numpy as np

# Marco StatsBomb: campo 120x80, portería atacada en x=120, postes en y=36 y 44.
POSTE_1 = (120.0, 36.0)
POSTE_2 = (120.0, 44.0)
CENTRO_META = (120.0, 40.0)

# Recorte para remates registrados sobre o más allá de la línea de fondo.
X_MAX_TIRO = 119.9

# Radio del disco que modela a un jugador, en metros. Es una DECISIÓN.
# 0.3 m ~ el ancho del torso; 0.5 m incluye el alcance de la pierna.
RADIO_DEFENSOR = 0.3


class Contadores:
    """Cuenta lo que se corrige o se descarta, para poder declararlo.

    Existe porque una corrección silenciosa sobre 2,454 remates es
    indistinguible de un bug. Si se recortaron 40 remates por cruzar la línea de
    fondo, el reporte tiene que poder decir 40.
    """

    def __init__(self) -> None:
        self.recortados_x = 0      # remates con x_s > X_MAX_TIRO
        self.sin_defensores = 0    # ningún defensor por delante
        self.degenerados = 0       # intervalo de portería nulo
        self.defensor_encima = 0   # rho < r: el disco envuelve al tirador

    def resumen(self) -> str:
        return (f"recortados_x={self.recortados_x}  "
                f"sin_defensores={self.sin_defensores}  "
                f"degenerados={self.degenerados}  "
                f"defensor_encima={self.defensor_encima}")


def intervalo_porteria(sx: float, sy: float) -> tuple[float, float]:
    """Intervalo angular que subtiende la portería desde (sx, sy).

    Con `sx < 120` los dos rumbos caen en $(-\\pi/2, \\pi/2)$, así que no hay
    salto de rama y `min/max` es correcto. Recortar `sx` antes es lo que
    garantiza esa precondición.
    """
    b1 = np.arctan2(POSTE_1[1] - sy, POSTE_1[0] - sx)
    b2 = np.arctan2(POSTE_2[1] - sy, POSTE_2[0] - sx)
    return (b1, b2) if b1 <= b2 else (b2, b1)


def goal_open(sx: float, sy: float, defensores, r: float = RADIO_DEFENSOR,
              cont: Contadores | None = None) -> float:
    """Fracción angular de portería NO tapada. En [0, 1], o `nan`.

    `defensores`: iterable de (x, y) de los defensores **de campo**. El portero
    se excluye a propósito: tapa por definición y su información va en
    `gk_depth` / `gk_offset`.
    """
    cont = cont if cont is not None else Contadores()

    if not np.isfinite(sx) or not np.isfinite(sy):
        cont.degenerados += 1
        return np.nan

    # (1) La corrección del borde. Sin esto, un remate en x=120.1 devuelve
    #     basura sin lanzar nada.
    #
    #     EFECTO SECUNDARIO, declarado: recortar mueve al tirador hacia atrás,
    #     así que un defensor entre X_MAX_TIRO y la x original pasa de estar
    #     "detrás" a estar "delante" y empieza a proyectar sombra. Es el
    #     comportamiento deseable —ese defensor está entre el balón y la meta—
    #     pero es consecuencia del recorte, no del dato. Cubierto por
    #     `test_el_recorte_puede_poner_por_delante_a_un_defensor_que_estaba_detras`.
    if sx > X_MAX_TIRO:
        cont.recortados_x += 1
        sx = X_MAX_TIRO

    lo, hi = intervalo_porteria(sx, sy)
    ancho = hi - lo
    if ancho <= 1e-9:
        cont.degenerados += 1
        return np.nan

    sombras: list[tuple[float, float]] = []
    for dx, dy in defensores:
        if not (np.isfinite(dx) and np.isfinite(dy)):
            continue
        if dx <= sx:                       # detrás del tirador: no tapa
            continue
        rho = float(np.hypot(dx - sx, dy - sy))
        if rho < 1e-9:
            continue
        if rho <= r:
            # El disco envuelve al tirador: tapa todo lo que haya por delante.
            cont.defensor_encima += 1
            return 0.0
        phi = float(np.arctan2(dy - sy, dx - sx))
        semi = float(np.arcsin(min(1.0, r / rho)))
        a, b = max(lo, phi - semi), min(hi, phi + semi)
        if b > a:
            sombras.append((a, b))

    if not sombras:
        cont.sin_defensores += 1
        return 1.0

    # Unión de intervalos por barrido. Dos defensores que se solapan NO deben
    # contarse dos veces: es el motivo entero de hacer la unión.
    sombras.sort()
    bloqueado = 0.0
    ca, cb = sombras[0]
    for a, b in sombras[1:]:
        if a <= cb:
            cb = max(cb, b)
        else:
            bloqueado += cb - ca
            ca, cb = a, b
    bloqueado += cb - ca

    return float(np.clip(1.0 - bloqueado / ancho, 0.0, 1.0))


# ----------------------------------------------------------------------
def goal_open_por_rayos(sx: float, sy: float, defensores,
                        r: float = RADIO_DEFENSOR, n_rayos: int = 200_001) -> float:
    """IMPLEMENTACIÓN INDEPENDIENTE por trazado de rayos. Solo para tests.

    Lanza `n_rayos` uniformemente en ÁNGULO a través del intervalo de la
    portería y cuenta cuántos llegan sin tocar ningún disco. No comparte una
    sola línea de lógica con `goal_open`: ni intervalos, ni unión, ni barrido.

    Es la comprobación fuerte. Dos implementaciones que no se parecen en nada y
    coinciden a 1e-4 es evidencia real de que la geometría está bien. Un test
    que reimplementa la misma fórmula solo comprueba que sabes copiar.

    Deliberadamente lenta: no usarla en producción.
    """
    if sx > X_MAX_TIRO:
        sx = X_MAX_TIRO
    lo, hi = intervalo_porteria(sx, sy)
    if hi - lo <= 1e-9:
        return np.nan

    ths = np.linspace(lo, hi, n_rayos)
    ux, uy = np.cos(ths), np.sin(ths)          # dirección de cada rayo
    libre = np.ones(n_rayos, dtype=bool)

    for dx, dy in defensores:
        if dx <= sx:
            continue
        vx, vy = dx - sx, dy - sy
        t = ux * vx + uy * vy                   # proyección sobre el rayo
        # distancia perpendicular del centro del disco a la recta del rayo
        perp = np.abs(ux * vy - uy * vx)
        libre &= ~((t > 0) & (perp <= r))

    return float(libre.mean())


# ----------------------------------------------------------------------
def segmentos_bloqueados(sx: float, sy: float, defensores,
                         r: float = RADIO_DEFENSOR) -> list[tuple[float, float]]:
    """Tramos [y_lo, y_hi] de la línea de meta tapados. **SOLO PARA DIBUJAR.**

    OJO: esto es una fracción LINEAL sobre el segmento x=120, y `goal_open` es
    una fracción ANGULAR. **No son la misma cantidad** y no tienen por qué
    coincidir: la proyección comprime distinto según el rumbo.

    El proyecto anterior documentaba estos segmentos como "la visualización
    directa de la feature goal_open". No lo son. Al dibujar, la leyenda debe
    decir "portería tapada (proyección)" y el número de `goal_open` citarse
    aparte.
    """
    if sx > X_MAX_TIRO:
        sx = X_MAX_TIRO
    segs = []
    for dx, dy in defensores:
        if dx <= sx:
            continue
        rho = np.hypot(dx - sx, dy - sy)
        if rho <= r:
            return [(POSTE_1[1], POSTE_2[1])]
        phi = np.arctan2(dy - sy, dx - sx)
        semi = np.arcsin(min(1.0, r / rho))
        ys = []
        for ang in (phi - semi, phi + semi):
            # cot del rumbo; el recorte de sx garantiza 120-sx > 0
            ys.append(sy + (120.0 - sx) * np.tan(np.clip(ang, -1.5, 1.5)))
        a, b = sorted(ys)
        a, b = max(POSTE_1[1], a), min(POSTE_2[1], b)
        if b > a:
            segs.append((float(a), float(b)))
    return segs
