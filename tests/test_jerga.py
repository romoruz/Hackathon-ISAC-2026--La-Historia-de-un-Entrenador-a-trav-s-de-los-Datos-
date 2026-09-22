"""ADR-59 adenda 3 §5: nada técnico del proyecto en el cuerpo de la página.

Revisa el modelo (frases, títulos, pies, notas, huecos) del cuerpo de las cinco
historias, el acto 1 y el cierre. El humo JS repite la revisión sobre el DOM
real, que además cubre las etiquetas de las figuras, los tooltips y los
aria-label. En el anexo, estos términos están permitidos."""
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import REPORTS, gen, hay_reales, humo, modelo_desde

JERGA = [r"ADR-\d", r"\bq =", r"\bp = 0\.\d", r"IC \[", r"N80", r"τ", r"λ", r"π", r"bootstrap",
         r"Benjamini", r"BH al", r"\bf = 0\.\d", r"\bF\d\d\b", r"D\d\d-\d", r"h2_\d\d",
         r"\bera principal\b", r"\bla base\b", r"cuasi-estacionaria"]


def textos_cuerpo(datos):
    for hid, s in gen.todas_las_secciones(datos, anexo=False):
        yield f"{hid}:{s['id']}:tit", s.get("tit", "")
        for b in s.get("bloques", []):
            for k in ("html", "pie", "titulo"):
                if isinstance(b.get(k), str):
                    # el cuerpo no lleva tooltips de fuente (adenda 3 §3)
                    t = re.sub(r' data-f="[^"]*"', "", b[k])
                    yield f"{hid}:{s['id']}:{k}", t


def jerga(datos):
    malas = []
    for donde, t in textos_cuerpo(datos):
        for p in JERGA:
            m = re.search(p, t, re.I if p.startswith(r"\b") and p[2:3].isalpha() else 0)
            if m:
                malas.append((donde, p, t[max(0, m.start() - 40):m.end() + 30]))
    return malas


def test_sintetico(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, _, _ = modelo_desde(tmp_path)
    assert not jerga(datos), jerga(datos)[:8]


@pytest.mark.skipif(not hay_reales(), reason="sin reports/")
def test_real():
    datos, _, _ = modelo_desde(REPORTS)
    assert not jerga(datos), jerga(datos)[:8]


def test_la_prueba_puede_fallar(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, _, _ = modelo_desde(tmp_path)
    datos["acto1"][0]["bloques"].append({"tipo": "frase", "html": "según ADR-53, q = 0.01"})
    assert len(jerga(datos)) >= 2


def test_el_anexo_si_puede_llevarla(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, _, _ = modelo_desde(tmp_path)
    anexo = " ".join(b.get("html") or "" for s in datos["anexo"] for b in s.get("bloques", []))
    assert "ADR-" in anexo or "q = " in anexo
