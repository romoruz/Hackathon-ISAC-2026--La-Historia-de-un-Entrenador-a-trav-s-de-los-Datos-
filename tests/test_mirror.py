"""El espejo de zonas: la funcion que impide un bug #12 defensivo.

El bug #12 (eje Y espejeado) no lanzo excepcion, no rompio nada y produjo
mapas perfectamente creibles durante semanas. Lo unico que lo habria atrapado
antes es un test que cruce los dos lados del contrato: la permutacion de
indices contra la reflexion de coordenadas.
"""
from __future__ import annotations

import numpy as np
import pytest

from dtdecoder.grid import StateSpace

MALLAS = [(5, 4), (4, 3), (6, 4), (6, 5), (3, 3), (1, 4), (5, 1)]


@pytest.mark.parametrize("nx,ny", MALLAS)
def test_mirror_zone_es_involutiva(nx, ny):
    sp = StateSpace(nx=nx, ny=ny)
    z = np.arange(sp.n_zones)
    assert np.array_equal(sp.mirror_zone(sp.mirror_zone(z)), z)


@pytest.mark.parametrize("nx,ny", MALLAS)
def test_mirror_zone_es_biyeccion(nx, ny):
    """Ninguna zona se pierde ni se duplica: es una permutacion."""
    sp = StateSpace(nx=nx, ny=ny)
    z = np.arange(sp.n_zones)
    assert sorted(sp.mirror_zone(z).tolist()) == z.tolist()


@pytest.mark.parametrize("nx,ny", MALLAS)
def test_mirror_zone_coincide_con_reflexion_de_coordenadas(nx, ny):
    """EL TEST QUE IMPORTA: cruza los dos lados del contrato.

    La permutacion de indices y la reflexion (120-x, 80-y) tienen que dar el
    mismo resultado sobre puntos arbitrarios del campo. Si alguien cambia
    `zone_of` -- el orden ix/iy, el sentido del floor, el clip -- este test
    truena. Eso es exactamente lo que NO paso con el bug #12.
    """
    sp = StateSpace(nx=nx, ny=ny)
    rng = np.random.default_rng(20260824)
    x = rng.uniform(0.0, sp.length, 20_000)
    y = rng.uniform(0.0, sp.width, 20_000)
    assert np.array_equal(
        sp.mirror_zone(sp.zone_of(x, y)),
        sp.zone_of(sp.length - x, sp.width - y),
    )


def test_mirror_state_preserva_la_fase():
    """`phase` describe el ORIGEN de la posesion, no una posicion: no se refleja."""
    sp = StateSpace(nx=5, ny=4)
    n_ph = len(sp.phases)
    s = np.arange(sp.n_transient)
    assert np.array_equal(sp.mirror_state(s) % n_ph, s % n_ph)
    assert np.array_equal(sp.mirror_state(sp.mirror_state(s)), s)


def test_mirror_lleva_el_ataque_rival_a_nuestro_campo():
    """Chequeo de sentido futbolistico, no solo algebraico."""
    sp = StateSpace(nx=5, ny=4)
    z_area_rival = int(sp.zone_of(np.array([115.0]), np.array([40.0]))[0])
    cx_nativo, _ = sp.zone_centroid(z_area_rival)
    assert cx_nativo > sp.length / 2

    z_nuestra = int(sp.mirror_zone(np.array([z_area_rival]))[0])
    cx, _ = sp.zone_centroid(z_nuestra)
    assert cx < sp.length / 2, "el espejo no llevo el ataque rival a nuestro campo"


def test_mirror_cruza_las_bandas():
    """La banda derecha del rival es nuestra izquierda, y viceversa.

    Con `y` creciendo HACIA ABAJO (origen arriba-izquierda de StatsBomb), para
    quien ataca hacia x=120 el borde y=0 queda a su IZQUIERDA. Al reflejar, esa
    banda pasa a ser la contraria. Es la mitad del bug #12 que se refiere al
    eje lateral.
    """
    sp = StateSpace(nx=5, ny=4)
    z_izq_rival = int(sp.zone_of(np.array([100.0]), np.array([5.0]))[0])
    z_esp = int(sp.mirror_zone(np.array([z_izq_rival]))[0])
    _, cy_orig = sp.zone_centroid(z_izq_rival)
    _, cy_esp = sp.zone_centroid(z_esp)
    assert cy_orig < sp.width / 2 and cy_esp > sp.width / 2
