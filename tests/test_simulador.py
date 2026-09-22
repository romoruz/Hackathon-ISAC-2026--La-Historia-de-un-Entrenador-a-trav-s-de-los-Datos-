"""ADR-59 adenda 3 §6: 46 exporta la matriz y aborta si su distribución no es la publicada."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("sim46", RAIZ / "scripts" / "46_simulador.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def test_guarda_acepta_la_misma_y_rechaza_otra():
    pytest.importorskip("scipy")
    from test_progresion import G, cadena
    P = cadena(seed=5)
    Q, a = S.bloque_abierto(G, P, np.ones(G.NT))
    pi = G.cuasi(Q, a)["pi"]
    assert S.verifica(G, Q, a, pi, "prueba") <= S.TOL
    otra = np.roll(pi, 1)
    with pytest.raises(G.Aborta):
        S.verifica(G, Q, a, otra, "prueba")
    assert S.verifica(G, Q, a, None, "sin publicar") is None


def test_conteos_abierto_de_una_era_sintetica(tmp_path):
    pytest.importorskip("polars")
    if not (RAIZ / "scripts" / "25_pares_h4.py").exists():
        pytest.skip("sin 25_pares_h4.py")
    import datetime as dt
    from test_progresion import G, cadena, _parquet
    rng = np.random.default_rng(3)
    f = [dt.date(2023, 8, 1) + dt.timedelta(days=3 * i) for i in range(5)]
    d = _parquet(tmp_path, "Alfa", "Beta", [("A1", f)], {"A1": cadena(seed=2)}, rng, n_pos=30)
    df = G.carga([d])
    C, a = S.conteos_abierto(G, df)
    abiertas = df.filter(df["from_state"] % 4 == 0).height
    assert C.shape == (20, 24) and C.sum() == abiertas
    assert C[:, 20:].sum() == df.filter((df["from_state"] % 4 == 0) & (df["to_state"] >= 80)).height
    assert a.sum() > 0
