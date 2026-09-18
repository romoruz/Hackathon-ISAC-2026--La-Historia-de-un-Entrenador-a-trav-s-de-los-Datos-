"""ADR-59 §6: ninguna cifra tecleada. Todo número del texto va dentro de una
cifra con fuente, salvo los rótulos de la lista blanca (nombres, no medidas)."""
import pathlib
import sys
import re

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import REPORTS, hay_reales, humo, modelo_desde

BLANCA = [
    r"ADR-\d+", r"\bP\d\b", r"§\d+(\.\d+)?", r"\bE\d\b", r"\bM\d\b", r"\b5\.\d\b",
    r"componente 0\d", r"\b[AC]20\d\d\b", r"\b360\b", r"minuto 60", r"min(>=|<)60",
    r"±1 partido", r"\b10_RESULTADOS\b", r"\b15_REPORTE_HTML\b", r"\b06_DECISIONS\b",
    r"20 × 4", r"\b20 zonas\b", r"(BH|Hochberg) al 5%", r"80% de los minutos",
    r"\bN80\b", r"_v\d\b", r"IC 95%", r"npxG", r"\bxG\b", r"adenda \d",
    r"\(I − Q\)\s*−1", r"N·1",   # notación de la cadena, en el plegable de §1
]


def textos(datos):
    for s in datos["secciones"]:
        for b in s.get("bloques", []):
            for k in ("html", "pie", "titulo"):
                if isinstance(b.get(k), str):
                    yield s["id"], b[k]


def sueltas(html):
    t = re.sub(r'<span class="cf"[^>]*>.*?</span>', " ", html)
    t = re.sub(r"<[^>]+>", " ", t)
    for p in BLANCA:
        t = re.sub(p, " ", t)
    return re.findall(r"\d[\d.,]*", t)


def _revisa(datos):
    malas = [(sid, n, h[:80]) for sid, h in textos(datos) for n in sueltas(h)]
    assert not malas, malas


def test_sintetico(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, M, _ = modelo_desde(tmp_path)
    _revisa(datos)
    assert all(c["f"] for c in M.cifras)


@pytest.mark.skipif(not hay_reales(), reason="sin reports/")
def test_real():
    datos, M, _ = modelo_desde(REPORTS)
    _revisa(datos)


def test_la_prueba_puede_fallar():
    assert sueltas('duró <span class="cf" data-f="x">+24.6%</span> y 12 acciones') == ["12"]
