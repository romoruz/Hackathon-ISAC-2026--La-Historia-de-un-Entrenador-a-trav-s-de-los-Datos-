"""scripts/32_docs_adr53.py: las cifras salen del JSON y nada se escribe a medias."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("docs_adr53", RAIZ / "scripts" / "32_docs_adr53.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def _par(club, a, b, cr, dd, q, rech, flip=False):
    e = {"rel": dd, "ic95": [dd - 0.03, dd + 0.03], "q": q, "rechaza_fdr": rech, "p": q}
    return {"club": club, "a": a, "b": b, "n_poss_a": 3000, "n_poss_b": 3000,
            "did": {"E_T": e}, "crudo": {"E_T": {"rel": cr, "ic95": [0, 0]}},
            "cambia_signo_por_correccion": flip}


def _repo(tmp_path, rel_js=0.1759):
    (tmp_path / "docs").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "docs/06_DECISIONS.md").write_text(
        "# 06\n\n**Estado.** Cerrada como aclaracion; la mejora queda pendiente.\n\n"
        "H7, así que ese contraste puede no llegar siquiera a calcularse.\n", encoding="utf-8")
    (tmp_path / "docs/10_RESULTADOS.md").write_text(
        "# 10\n\n> Corte: 2026-08-20 · `dtdecoder 0.5.0` · **Fases 0–3 completas**\n\n## 0.\n"
        "Es el patrón de los doce bugs aplicado a la estadística: x\n",
        encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "02_STATE_OF_PLAY.md").write_text("## 8. Los doce bugs: doce silenciosos\n", encoding="utf-8")
    (docs / "05_VALIDATION.md").write_text(
        "Los **ocho** bugs encontrados hasta ahora\n(`02_STATE_OF_PLAY.md` §8) fueron "
        "todos silenciosos. Ocho de ocho.\n", encoding="utf-8")
    (docs / "13_CONTEXTO_IA.md").write_text(
        "**Doce bugs encontrados, doce silenciosos.**\n"
        "| 1 | x | dónde estamos, qué está validado, los doce bugs |\n"
        "| 3 | y | 51 ADRs. **No reabrir debates cerrados** |\n"
        "> - Los **doce** bugs del proyecto fueron **silenciosos**; x\n", encoding="utf-8")
    (docs / "15_REPORTE_HTML.md").write_text(
        "Los doce bugs de este\nproyecto compilaban.\n", encoding="utf-8")
    (docs / "17_BITACORA_MIGRACION.md").write_text(
        "> El patrón es el mismo que el proyecto lleva catorce bugs documentando:\n"
        "Ahí es donde salieron los catorce bugs, y todos fueron\nsilenciosos.\n",
        encoding="utf-8")
    (docs / "07_AI_HANDOFF.md").write_text(
        "**Doce bugs encontrados. Doce silenciosos.** Ninguno\n"
        "> - Los **doce** bugs del proyecto fueron silenciosos, y el #13 se\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "**Doce bugs encontrados. Doce silenciosos. Cero excepciones.** Uno más (#13) se\n"
        "> - Los doce bugs del proyecto fueron **silenciosos**, y el #13 se evitó\n",
        encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# portada\n\n## 1. Titulares y Hallazgos Principales\n\n| x |\n\n"
        "> ⚠️ **Advertencia**: Doce bugs encontrados, doce silenciosos. Ninguno.\n\n"
        "## 2. Los Seis Pilares de Validación\n\n1. x\n", encoding="utf-8")
    (tmp_path / "docs/README.md").write_text(
        "# R\n\n| 06 | [Decisiones (51 ADRs)](06_DECISIONS.md) | equipo | x |\n"
        "| 15 | [El reporte HTML](15_REPORTE_HTML.md) | desarrollador | **antes de tocar el entregable** |\n"
        "\n## Estado\n\nviejo\n\n## Advertencia\n\nDoce bugs.\n", encoding="utf-8")
    d = {"n_unidades": 53, "n_pares": 3, "n_rechazados_did": 2, "n_rechazados_crudo": 3,
         "n_cambian_signo_por_correccion": 1, "parametros": {"n_boot": 4000},
         "aviso_piso_p": None, "eras_bloqueadas_por_candado": [],
         "firma_temporal": {"crudo": {"posterior_mas_largo": 3, "de": 3},
                            "did": {"posterior_mas_largo": 1, "de": 2}},
         "unidades": [
             {"club": "América", "coach": "Andre Jardine", "rel_E_T_vs_liga": .25,
              "rel_E_T_vs_liga_ic95": [.22, .27]},
             {"club": "Atlético San Luis", "coach": "Andre Jardine", "rel_E_T_vs_liga": -.10,
              "rel_E_T_vs_liga_ic95": [-.12, -.08]}],
         "pares": [
             _par("América", "Andre Jardine", "Santiago Solari", .3142, rel_js, .001, True),
             _par("Atlas", "Diego Cocca I", "Diego Cocca II", -.0701, .0489, .0389, True, True),
             _par("América", "Andre Jardine", "Fernando Ortiz", .1281, .0354, .0562, False)],
         "control_negativo": {"n_no_rechazados": 1, "elegido": None,
                              "menor_margen_demostrable_E_T": .0705,
                              "candidatos": [{"club": "América", "a": "Andre Jardine",
                                              "b": "Fernando Ortiz",
                                              "margen_demostrable_E_T": .0705}]},
         "comparacion_v5": {"v5_rechaza_y_did_no": 1, "did_rechaza_y_v5_no": 0}}
    (tmp_path / "reports/did_h4_v1.json").write_text(json.dumps(d), encoding="utf-8")
    return tmp_path


def _corre(monkeypatch, raiz, *extra):
    monkeypatch.setattr(sys, "argv", ["x", "--raiz", str(raiz),
                                      "--vista", str(raiz / "vista"), *extra])
    return m.main()


def test_las_cifras_salen_del_json(tmp_path, monkeypatch):
    raiz = _repo(tmp_path, rel_js=0.1234)
    _corre(monkeypatch, raiz, "--escribir")
    r = (raiz / "docs/README.md").read_text(encoding="utf-8")
    assert "**+12.3%**" in r and "17.6" not in r
    assert "(53 ADRs)" in r and "viejo" not in r
    assert "## ADR-53" in (raiz / "docs/06_DECISIONS.md").read_text(encoding="utf-8")


def test_predicciones_calculadas():
    raiz = None
    d = m.Datos.__new__(m.Datos)
    d.did = json.loads(json.dumps({
        "firma_temporal": {"crudo": {"posterior_mas_largo": 37, "de": 47},
                           "did": {"posterior_mas_largo": 23, "de": 44}},
        "control_negativo": {"elegido": None, "menor_margen_demostrable_E_T": .0402}}))
    d.pares = {("Atlas", "Diego Cocca I", "Diego Cocca II"):
               _par("Atlas", "Diego Cocca I", "Diego Cocca II", -.07, -.05, .01, True)}
    ps = {p["n"]: p["cumple"] for p in m.predicciones(d)}
    assert ps[1] is True and ps[4] is True
    assert ps[2] is False                  # sigue negativo y significativo: FALLA


def test_idempotente(tmp_path, monkeypatch):
    raiz = _repo(tmp_path)
    _corre(monkeypatch, raiz, "--escribir")
    todos = lambda: {str(p): p.read_text(encoding="utf-8")
                     for p in list((raiz / "docs").glob("*.md")) + list(raiz.glob("*.md"))}
    antes = todos()
    assert _corre(monkeypatch, raiz, "--escribir") == 0
    assert todos() == antes
    assert antes[str(raiz / "README.md")].count("RETIRADOS (2026-09-15)") == 1


def test_fragmento_ausente_aborta_sin_escribir(tmp_path, monkeypatch):
    raiz = _repo(tmp_path)
    (raiz / "docs/README.md").write_text("# otro README sin anclas\n", encoding="utf-8")
    antes = {p.name: p.read_text(encoding="utf-8") for p in (raiz / "docs").glob("*.md")}
    with pytest.raises(SystemExit, match="ABORTA"):
        _corre(monkeypatch, raiz, "--escribir")
    assert {p.name: p.read_text(encoding="utf-8")
            for p in (raiz / "docs").glob("*.md")} == antes
    assert not list((raiz / "docs").glob("*.anterior_*"))


def test_el_conteo_de_bugs_queda_unificado(tmp_path, monkeypatch):
    raiz = _repo(tmp_path)
    _corre(monkeypatch, raiz, "--escribir")
    q = m.conteos_restantes(raiz, {})
    assert set(q) == {"dieciocho"}, q
    assert "53 ADRs" in (raiz / "docs/13_CONTEXTO_IA.md").read_text(encoding="utf-8")


def test_no_escribe_si_verificar_falla(tmp_path, monkeypatch):
    raiz = _repo(tmp_path)
    (raiz / "docs/verificar_docs.py").write_text(
        "import sys\nprint('1 CONTRADICCIONES')\nsys.exit(1)\n", encoding="utf-8")
    antes = {p.name: p.read_text(encoding="utf-8") for p in (raiz / "docs").glob("*.md")}
    assert _corre(monkeypatch, raiz, "--escribir") == 1
    assert {p.name: p.read_text(encoding="utf-8")
            for p in (raiz / "docs").glob("*.md")} == antes
    assert _corre(monkeypatch, raiz, "--escribir", "--forzar") == 0


def test_portada_marca_retirados(tmp_path, monkeypatch):
    raiz = _repo(tmp_path)
    _corre(monkeypatch, raiz, "--escribir")
    r = (raiz / "README.md").read_text(encoding="utf-8")
    assert "🔴 **RETIRADOS (2026-09-15).**" in r
    assert "pendientes de replicar" in r
    assert "Dieciocho bugs encontrados" in r and "Doce" not in r
    assert (raiz / "vista" / "RAIZ_README.md").exists()
