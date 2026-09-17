"""Piezas puras de scripts/37_docs_resultados.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("docs37", RAIZ / "scripts" / "37_docs_resultados.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


class _D:
    def __init__(self, casos, filas):
        self.cx = {"casos": casos, "unidades": filas}


def _u(coach, club, th):
    return {"coach": coach, "club": club, "contrastes": {"marcador|M1": {"theta": th}}}


def test_viaja_cuenta_los_nueve_sin_el_america():
    casos = {"Jardine": ["América", "San Luis"], "Solari": ["América"],
             "Vucetich": ["Mazatlán", "Monterrey"], "Herrera": ["Tigres", "Tijuana"]}
    filas = [_u("Jardine", "América", .1), _u("Jardine", "San Luis", .2),
             _u("Vucetich", "Mazatlán", -.2), _u("Vucetich", "Monterrey", -.9),
             _u("Herrera", "Tigres", -.7), _u("Herrera", "Tijuana", .4)]
    res, n = m.viaja_nueve(_D(casos, filas))
    assert [r[0] for r in res] == ["Herrera", "Vucetich"]   # Jardine fuera: dirigio al America
    assert n == 1


def test_tabla_de_predicciones_escapa_barras():
    t = m.preds_tabla([{"n": 5, "texto": "|a - b| / a < 0.25", "valor": 0.9, "cumple": False}])
    fila = t.split("\n")[-1]
    assert "\\|a - b\\|" in fila and fila.count("|") - fila.count("\\|") == 5


def test_formatos():
    assert m.pp(0.0123) == "+1.23 pp" and m.pp(None) == "—"
    assert m.icpp([None, None]) == "—"
    assert m.marca(None) == "n/e"
