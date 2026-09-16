"""scripts/31_backfill_club.py: infiere el club solo si es unico."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "backfill_club", RAIZ / "scripts" / "31_backfill_club.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

CSV = """club,coach,analizable
América,Andre Jardine,1
Atlético San Luis,Andre Jardine,1
América,Fernando Ortiz,1
Toluca,Ignacio Ambriz,1
Toluca,Renato Paiva,1
León,Ignacio Ambriz,0
León,Renato Paiva,0
"""


def _prepara(tmp_path):
    eras = tmp_path / "eras.csv"
    eras.write_text(CSV, encoding="utf-8")
    rep = tmp_path / "reports"
    rep.mkdir()
    (rep / "ic_andrejardine_fernandoortiz.json").write_text(
        json.dumps({"a": "Andre Jardine", "b": "Fernando Ortiz", "resultados": []}))
    (rep / "ic_ignacioambriz_renatopaiva.json").write_text(
        json.dumps({"a": "Ignacio Ambriz", "b": "Renato Paiva", "resultados": []}))
    return eras, rep


def test_solo_analizables_desambigua(tmp_path):
    eras, _ = _prepara(tmp_path)
    assert bf.infiere("Ignacio Ambriz", "Renato Paiva",
                      bf.clubes_por_entrenador(eras)) == ("Toluca", "ok")
    club, motivo = bf.infiere("Ignacio Ambriz", "Renato Paiva",
                              bf.clubes_por_entrenador(eras, False))
    assert club is None and motivo.startswith("AMBIGUO")


def test_escribe_con_respaldo(tmp_path, monkeypatch):
    eras, rep = _prepara(tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--reports", str(rep),
                                      "--eras", str(eras), "--escribir"])
    assert bf.main() == 0
    d = json.loads((rep / "ic_andrejardine_fernandoortiz.json").read_text())
    assert d["club"] == "América"
    assert list(d)[0] == "club"
    respaldos = list((rep / "_respaldo_h2_11").rglob("*.json"))
    assert len(respaldos) == 2
    assert all("club" not in json.loads(p.read_text()) for p in respaldos)


def test_sin_escribir_no_toca_nada(tmp_path, monkeypatch):
    eras, rep = _prepara(tmp_path)
    antes = {p.name: p.read_text() for p in rep.glob("*.json")}
    monkeypatch.setattr(sys, "argv", ["x", "--reports", str(rep), "--eras", str(eras)])
    bf.main()
    assert {p.name: p.read_text() for p in rep.glob("*.json")} == antes
