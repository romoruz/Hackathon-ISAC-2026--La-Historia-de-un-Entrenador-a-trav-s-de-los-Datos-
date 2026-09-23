"""ADR-59 adenda 5: primero la historia, después el método; el selector de club
vive dentro de la sección y 2.2 no lo lleva.

El humo JS comprueba el DOM. Aquí se comprueba el MODELO, que es lo que el
generador promete: dónde vive cada bloque y qué secciones tienen versión por
club. Sin números: solo la forma."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import REPORTS, gen, hay_reales, humo, modelo_desde


def datos_de(p):
    d, _, _ = modelo_desde(p)
    return d


def _qh(datos):
    return [b for s in datos["acto1"] for b in s.get("bloques", []) if b.get("portada_solo")]


def _revisa(datos):
    # 1. «qué hicimos» existe una sola vez y está marcado para la portada
    qh = _qh(datos)
    assert len(qh) == 1, f"«qué hicimos» aparece {len(qh)} veces"
    assert qh[0]["tipo"] == "frase" and qh[0]["nivel"] == "C"

    # 2. las tres conclusiones de la carrera suben a la portada
    for h in datos["historias"]:
        if not h.get("acto2"):
            continue
        conc = [b for s in h["acto2"] for b in s.get("bloques", []) if b.get("conc")]
        assert [b["conc"] for b in conc] == sorted(b["conc"] for b in conc), h["id"]
        assert 2 <= len(conc) <= 3, f"{h['id']}: {len(conc)} conclusiones"
        assert all(b["nivel"] == "C" for b in conc), h["id"]

    # 3. el selector de club: ni la carrera ni llegar a la última franja lo llevan
    for h in datos["historias"]:
        por = h.get("por_club") or {}
        for club, secs in por.items():
            ids = [s["id"] for s in secs]
            assert "a2-0" not in ids and "a2-2" not in ids, f"{h['id']}/{club}: {ids}"
            assert len(ids) == len(set(ids)), f"{h['id']}/{club}: secciones repetidas"

    # 4. 2.2 dice que se midió solo en el club donde más dirigió
    for h in datos["historias"]:
        if len(h.get("eras") or []) < 2:
            continue
        s = next((x for x in h.get("acto2", []) if x["id"] == "a2-2"), None)
        if not s or s.get("falta") or s.get("pendiente"):
            continue
        txt = " ".join(b.get("html") or "" for b in s["bloques"])
        assert "el club donde más dirigió" in txt, h["id"]

    # 5. topes de la adenda 5 §9
    for hid, s in gen.todas_las_secciones(datos, anexo=False):
        pass
    for h in datos["historias"]:
        n = len(h.get("acto2", [])) + len(h.get("acto3", [])) + len(datos["acto1"]) + len(datos["cierre"])
        assert n <= 16, f"{h['id']}: {n} secciones en el cuerpo"


def test_sintetico(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    _revisa(datos_de(tmp_path))


@pytest.mark.skipif(not hay_reales(), reason="sin reports/")
def test_real():
    _revisa(datos_de(REPORTS))


def test_la_prueba_puede_fallar(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos = datos_de(tmp_path)
    _qh(datos)[0].pop("portada_solo")
    with pytest.raises(AssertionError):
        _revisa(datos)
