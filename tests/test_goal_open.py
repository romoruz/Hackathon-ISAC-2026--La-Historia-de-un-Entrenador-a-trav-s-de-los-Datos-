"""Tests numéricos de `goal_open`. Fase 0: aquí se originan los errores silenciosos.

La regla del proyecto: un test no comprueba que el código corra, comprueba que
**el número sea el correcto**. Los doce bugs corrían sin excepción.

Estructura:
  1. Casos con forma cerrada, calculada a mano.
  2. Propiedades que la geometría debe cumplir (simetría, monotonía, unión).
  3. Contraste contra una implementación INDEPENDIENTE por trazado de rayos.
  4. Los tres bordes que rompían el original.
"""
import numpy as np
import pytest

from dtdecoder.geometria_remate import (
    Contadores, X_MAX_TIRO, goal_open, goal_open_por_rayos,
    intervalo_porteria, segmentos_bloqueados,
)


# ======================================================================
# 1. FORMA CERRADA
# ======================================================================
def test_caso_degenerado_valor_exacto():
    """Tirador (100,40), un defensor en (110,40) justo en la línea de visión.

    Cerrado:  goal_open = 1 - asin(r/rho) / atan(4/20)
    Con r=0.3 y rho=10:  1 - asin(0.03)/atan(0.2) = 0.847998092...
    """
    esperado = 1 - np.arcsin(0.03) / np.arctan2(4, 20)
    obtenido = goal_open(100, 40, [(110, 40)], r=0.3)
    assert obtenido == pytest.approx(esperado, abs=1e-12)
    assert obtenido == pytest.approx(0.847998092, abs=1e-9)


def test_caso_degenerado_r_medio_metro():
    esperado = 1 - np.arcsin(0.05) / np.arctan2(4, 20)
    assert goal_open(100, 40, [(110, 40)], r=0.5) == pytest.approx(esperado, abs=1e-12)
    assert goal_open(100, 40, [(110, 40)], r=0.5) == pytest.approx(0.746595, abs=1e-6)


def test_ancho_del_intervalo_de_porteria():
    """Desde (100,40), la portería subtiende 2·atan(4/20) rad."""
    lo, hi = intervalo_porteria(100, 40)
    assert hi - lo == pytest.approx(2 * np.arctan2(4, 20), abs=1e-12)
    assert lo == pytest.approx(-hi, abs=1e-12)      # simétrico desde el centro


# ======================================================================
# 2. PROPIEDADES
# ======================================================================
def test_sin_defensores_es_uno():
    assert goal_open(100, 40, []) == 1.0


def test_defensor_detras_del_tirador_no_tapa():
    """Un defensor rebasado no bloquea la visión. dx <= sx se descarta."""
    assert goal_open(100, 40, [(90, 40)]) == 1.0
    assert goal_open(100, 40, [(100, 40)]) == 1.0   # exactamente a la misma x


def test_defensor_muy_lateral_no_tapa():
    """Sombra fuera del intervalo de la portería: no descuenta nada."""
    assert goal_open(100, 40, [(110, 5)]) == pytest.approx(1.0, abs=1e-12)


def test_simetria_respecto_al_eje_del_campo():
    """Reflejar y en torno a 40 no puede cambiar la fracción visible."""
    a = goal_open(100, 34, [(110, 37), (112, 30)])
    b = goal_open(100, 46, [(110, 43), (112, 50)])
    assert a == pytest.approx(b, abs=1e-12)


def test_monotonia_al_acercar_al_defensor():
    """Más cerca del tirador ⇒ sombra angular mayor ⇒ menos portería visible."""
    vals = [goal_open(100, 40, [(100 + d, 40)]) for d in (2, 5, 10, 15, 19)]
    assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))


def test_monotonia_en_el_radio():
    """Un disco mayor tapa más."""
    rs = [0.1, 0.3, 0.5, 1.0]
    vals = [goal_open(100, 40, [(110, 40)], r=r) for r in rs]
    assert all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))


def test_defensores_solapados_no_se_cuentan_dos_veces():
    """LA razón de ser de la unión de intervalos.

    Dos defensores casi en el mismo sitio tapan casi lo mismo que uno solo. Si
    el barrido sumara sin unir, el bloqueo se duplicaría.
    """
    uno = goal_open(100, 40, [(110, 40)])
    dos = goal_open(100, 40, [(110, 40), (110.02, 40.01)])
    assert dos == pytest.approx(uno, abs=0.01)
    assert dos < uno                       # tapa un pelín más, no el doble
    bloqueo_uno, bloqueo_dos = 1 - uno, 1 - dos
    assert bloqueo_dos < 1.6 * bloqueo_uno


def test_defensores_disjuntos_suman():
    """Sombras separadas sí acumulan: la unión no debe fusionarlas."""
    a = 1 - goal_open(100, 40, [(110, 38.5)])
    b = 1 - goal_open(100, 40, [(110, 41.5)])
    ab = 1 - goal_open(100, 40, [(110, 38.5), (110, 41.5)])
    assert ab == pytest.approx(a + b, abs=1e-9)


def test_resultado_siempre_en_cero_uno():
    rng = np.random.default_rng(20260826)
    for _ in range(400):
        sx, sy = rng.uniform(60, 119), rng.uniform(5, 75)
        defs = [(rng.uniform(sx, 120), rng.uniform(0, 80))
                for _ in range(rng.integers(0, 11))]
        v = goal_open(sx, sy, defs)
        assert np.isnan(v) or 0.0 <= v <= 1.0


# ======================================================================
# 3. CONTRASTE CONTRA UNA IMPLEMENTACIÓN INDEPENDIENTE
# ======================================================================
@pytest.mark.parametrize("sx,sy,defs", [
    (100, 40, [(110, 40)]),
    (100, 40, [(110, 40), (105, 41), (112, 38)]),
    (95, 30, [(100, 33), (110, 35), (115, 39), (108, 28)]),
    (112, 44, [(115, 42), (116, 45)]),
    (80, 40, [(90, 40), (100, 41), (110, 39), (115, 40)]),
    (118, 20, [(119, 25), (119.5, 30)]),
])
def test_coincide_con_trazado_de_rayos(sx, sy, defs):
    """Barrido de intervalos vs. 200,001 rayos. Cero lógica compartida.

    Si las dos coinciden a 1e-3, la geometría está bien. Es la comprobación que
    de verdad protege: un test que reimplementa la misma fórmula solo verifica
    que sabes copiarla.
    """
    rapido = goal_open(sx, sy, defs)
    lento = goal_open_por_rayos(sx, sy, defs)
    assert rapido == pytest.approx(lento, abs=1e-3)


def test_coincide_con_rayos_en_escenas_aleatorias():
    rng = np.random.default_rng(11235)
    for _ in range(25):
        sx, sy = rng.uniform(85, 118), rng.uniform(20, 60)
        defs = [(rng.uniform(sx + 0.5, 119.8), rng.uniform(25, 55))
                for _ in range(rng.integers(1, 7))]
        assert goal_open(sx, sy, defs) == pytest.approx(
            goal_open_por_rayos(sx, sy, defs, n_rayos=50_001), abs=2e-3)


# ======================================================================
# 4. LOS TRES BORDES QUE ROMPÍAN EL ORIGINAL
# ======================================================================
def test_remate_mas_alla_de_la_linea_de_fondo():
    """`04_DATA_CONTRACT.md` §3.2: StatsBomb reporta x=120.1 en remates.

    Con x_s > 120 la portería queda detrás y los rumbos saltan cerca de ±π; el
    original devolvía basura SIN AVISAR. Aquí se recorta y se cuenta.
    """
    c = Contadores()
    v = goal_open(120.1, 40, [(119.95, 40)], cont=c)
    assert np.isfinite(v) and 0.0 <= v <= 1.0
    assert c.recortados_x == 1

    # y el recorte es equivalente a haber pasado X_MAX_TIRO directamente
    assert v == pytest.approx(goal_open(X_MAX_TIRO, 40, [(119.95, 40)]), abs=1e-12)


def test_x_justo_en_la_linea():
    c = Contadores()
    assert np.isfinite(goal_open(120.0, 40, [], cont=c))
    assert c.recortados_x == 1


def test_defensor_encima_del_tirador_tapa_todo():
    """rho <= r: el disco envuelve al tirador. arcsin se satura y tapa todo."""
    c = Contadores()
    assert goal_open(100, 40, [(100.1, 40)], r=0.3, cont=c) == 0.0
    assert c.defensor_encima == 1


def test_nan_en_vez_de_imputar():
    """Sin coordenada no hay geometría. Devuelve nan; NO inventa un valor.

    Imputar aquí con la mediana metería remates promedio disfrazados de dato
    real, que es la crítica al `fillna(median)` del proyecto anterior.
    """
    c = Contadores()
    assert np.isnan(goal_open(np.nan, 40, [(110, 40)], cont=c))
    assert c.degenerados == 1


def test_los_contadores_cuentan():
    c = Contadores()
    # el defensor de esta escena queda DETRÁS del tirador, así que además de
    # recortar la x cuenta como escena sin defensores por delante
    goal_open(120.5, 40, [(119, 40)], cont=c)
    goal_open(100, 40, [], cont=c)
    goal_open(np.nan, 40, [], cont=c)
    assert (c.recortados_x, c.sin_defensores, c.degenerados) == (1, 2, 1)
    assert "recortados_x=1" in c.resumen()


def test_el_recorte_puede_poner_por_delante_a_un_defensor_que_estaba_detras():
    """EFECTO SECUNDARIO DEL RECORTE, documentado a propósito.

    Tirador en x=120.1, defensor en x=119.95: originalmente el defensor está
    DETRÁS (119.95 < 120.1) y se descarta. Tras recortar el tirador a 119.9,
    el mismo defensor pasa a estar POR DELANTE y sí proyecta sombra.

    ¿Es correcto? Sí: un remate desde la línea de fondo con un defensor a 15 cm
    hacia dentro tiene a ese defensor entre el balón y la portería en cualquier
    sentido útil. Pero es una consecuencia del recorte, no del dato, y por eso
    se prueba explícitamente: si alguien cambia X_MAX_TIRO, este test cambia de
    valor y obliga a pensarlo.
    """
    c = Contadores()
    v = goal_open(120.1, 40, [(119.95, 40)], cont=c)
    assert c.recortados_x == 1
    assert c.sin_defensores == 0          # el defensor SÍ contó
    assert v < 1.0                        # y tapó algo


# ======================================================================
# 5. LA MEDIDA ANGULAR NO ES LA LINEAL
# ======================================================================
def test_proyeccion_lineal_difiere_de_la_angular():
    """Documenta la discrepancia en vez de fingir que no existe.

    `06_visualizaciones.md` del proyecto anterior afirmaba que los segmentos
    dibujados eran "la visualización directa de la feature goal_open". No lo
    son: una es fracción de ángulo y la otra de longitud.
    """
    sx, sy, defs = 95, 30, [(100, 33), (110, 35), (115, 39)]
    angular = 1 - goal_open(sx, sy, defs)
    lineal = sum(b - a for a, b in segmentos_bloqueados(sx, sy, defs)) / 8.0
    assert angular == pytest.approx(lineal, abs=0.25)   # mismo orden
    assert angular != pytest.approx(lineal, abs=1e-6)   # pero NO iguales
