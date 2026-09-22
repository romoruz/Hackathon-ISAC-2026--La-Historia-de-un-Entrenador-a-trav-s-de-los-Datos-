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
