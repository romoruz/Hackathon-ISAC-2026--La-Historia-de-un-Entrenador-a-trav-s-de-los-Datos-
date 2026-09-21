"""ADR-60 §5: el mapa se recalcula desde los JSON y coincide con el barrido."""
import csv
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
REP = RAIZ / "reports"


def _mod():
    spec = importlib.util.spec_from_file_location("estilos43", RAIZ / "scripts" / "43_mapa_estilos.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def est():
    if not all((REP / f).exists() for f in ("did_h4_v1.json", "metricas_v1.json", "jugadores_v1.json")):
        pytest.skip("sin reports/")
    return _mod().construye(REP)


def test_coincide_con_el_barrido(est):
    ruta = REP / "barrido" / "eras.csv"
    if not ruta.exists():
        pytest.skip("sin reports/barrido/eras.csv")
    filas = {(r["club"], r["coach"]): r for r in csv.DictReader(ruta.open(encoding="utf-8"))}
    for e in est["eras"]:
        r = filas[(e["club"], e["coach"])]
        assert abs(e["PC1"] - float(r["PC1"])) < 5e-4 and abs(e["PC2"] - float(r["PC2"])) < 5e-4


def test_forma(est):
    assert len(est["relevos"]) == 21
    assert all(0 <= t["percentil"] <= 1 for t in est["traslados"] + est["relevos"])
    assert est["nivel"] == "C" and set(est["ejes"]) >= {"PC1", "PC2", "varianza"}
    assert est["distancias_todas"]["n"] == len(est["eras"]) * (len(est["eras"]) - 1) // 2
