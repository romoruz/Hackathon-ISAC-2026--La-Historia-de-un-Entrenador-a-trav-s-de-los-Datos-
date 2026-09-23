"""ADR-62 adenda 1c y ADR-59 adenda 10: la red de pases en la página, sin resolver."""
import pathlib
import re
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import REPORTS, RAIZ, gen, hay_reales, humo, modelo_desde

# adenda 10 §3: lo que el cuerpo NO puede decir
NO_DICE = [r"(se mueve|cambia) lo mismo", r"cambie o no", r"placebo", r"percentil",
           r"(la red|el cambio de red) (cambia|se mueve) m[aá]s cuando cambia el t[eé]cnico",
           r"el t[eé]cnico (cambi[oó]|caus[oó]|provoc[oó]) (la red|el cambio)"]


def _sec(datos):
    return next(s for s in datos["cierre"] if s["id"] == "c-red")


def _texto(s):
    # las fuentes van en atributos (data-f, data-tip) y no son texto de la página
    limpia = lambda h: re.sub(r"<[^>]+>", "", re.sub(r'\s(data-f|data-tip)="[^"]*"', "", h))
    return " ".join(limpia(b.get("html") or "") for b in s.get("bloques", []))


def revisa(datos):
    s = _sec(datos)
    assert [x["id"] for x in datos["cierre"]] == ["c-1", "c-red", "c-2"]
    assert "bloques" in s, s.get("falta")
    t = _texto(s)
    assert "No sabemos si la red cambia más cuando cambia el técnico." in t
    assert "error nuestro" in t and "no quién lo causó" in t
    # la frase literal «No sabemos si la red cambia más...» es la única forma permitida
    t2 = t.replace("No sabemos si la red cambia más cuando cambia el técnico.", "")
    malas = [p for p in NO_DICE if re.search(p, t2, re.I)]
    assert not malas, malas
    frases = [b for b in s["bloques"] if b["tipo"] == "frase"]
    assert frases and all(b["nivel"] == "C" for b in frases)
    figs = [b for b in s["bloques"] if b["tipo"] == "fig"]
    assert [f["id"] for f in figs] == ["red_phi"]
    return s


def _marcador_62(dir_):
    J, _ = gen.recolecta(dir_, dir_ / "no_existe.parquet")
    return [p for p in gen.marcador(J) if p["adr"] == 62]


def test_sintetico(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, _, _ = modelo_desde(tmp_path)
    revisa(datos)
    m = _marcador_62(tmp_path)
    assert [p["n"] for p in m] == [1, 2, 3]
    assert m[0]["cumple"] is None and "sin resolver" in m[0]["texto"]


@pytest.mark.skipif(not hay_reales(), reason="sin reports/")
def test_real():
    datos, _, _ = modelo_desde(REPORTS)
    revisa(datos)
    assert _marcador_62(REPORTS)[0]["cumple"] is None


def test_la_prueba_puede_fallar(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, _, _ = modelo_desde(tmp_path)
    _sec(datos)["bloques"].append({"tipo": "frase", "nivel": "C",
                                   "html": "La red se mueve lo mismo cambie o no el técnico."})
    with pytest.raises(AssertionError):
        revisa(datos)


def test_el_placebo_esta_inerte():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "51_placebo_red.py")],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "adenda 1c" in r.stderr
