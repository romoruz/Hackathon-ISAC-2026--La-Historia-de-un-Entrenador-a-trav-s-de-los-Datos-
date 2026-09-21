"""ADR-60 adenda 1 §4: el placebo parte bien las eras y la lectura es la fijada."""
import datetime as dt
import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _m(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / archivo)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


P = _m("placebo44", "44_placebo_T.py")


def test_mitades_por_fecha_y_el_impar_a_la_primera():
    ps = [(dt.date(2024, 1, d), 100 + d) for d in (5, 1, 3, 9, 7)]
    a, b = P.mitades(ps)
    assert a == [101, 103, 105] and b == [107, 109]
    a, b = P.mitades(ps[:4])
    assert len(a) == len(b) == 2


def test_lectura_fijada_en_la_adenda():
    assert P.lectura(11) == "A" and P.lectura(21) == "A"
    assert P.lectura(10) == "B" and P.lectura(0) == "B"
    assert P.K_LECTURA_A == 11 and P.MIN_PARTIDOS == 20


def test_placebo_de_una_era_sintetica(tmp_path):
    pytest.importorskip("polars")
    if not (RAIZ / "scripts" / "25_pares_h4.py").exists():
        pytest.skip("sin 25_pares_h4.py")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    R = P._r42()
    from test_relevos import _parquet_sintetico  # noqa: E402
    rng = np.random.default_rng(7)
    f = [dt.date(2023, 8, 1) + dt.timedelta(days=3 * i) for i in range(24)]
    dA = _parquet_sintetico(tmp_path, "Alfa", "Beta", [("A1", f, list(range(1, 15)))], rng)
    dB = _parquet_sintetico(tmp_path, "Beta", "Alfa", [("B1", f, list(range(30, 44)))], rng)
    df = R.carga_acciones([dA, dB])
    liga = R.referencia_liga(df)
    r, n = P.placebo_era(R, df, liga, "Alfa", "A1", np.random.default_rng(0), 199)
    assert n == 24 and r["n_1"] == r["n_2"] == 12
    assert r["p"] > 0.01                 # la misma distribución en las dos mitades
    r, n = P.placebo_era(R, df.head(1000), liga, "Alfa", "A1", np.random.default_rng(0), 99)
    assert r is None
