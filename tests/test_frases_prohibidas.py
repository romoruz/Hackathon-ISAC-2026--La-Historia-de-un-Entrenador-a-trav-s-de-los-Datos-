"""ADR-59 §3: ninguna frase prohibida en el texto generado."""
import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import REPORTS, gen, hay_reales, humo, modelo_desde
from frases_prohibidas import revisa


@pytest.mark.parametrize("frase", [
    "El éxito de Jardine", "gracias a la rotación", "la rotación permite sostener el nivel",
    "para sobrevivir al calendario", "se apoya en la posesión", "esto provoca remates",
    "lo que explica el dominio", "el mejor técnico", "su firma táctica", "el ADN del club",
    "no hay efecto", "una diferencia Significativa", "Jardine impone su estilo",
    "el equipo se adapta al rival",
    # adenda 2 §8
    "el club pesa más que el técnico", "esto demuestra que viaja", "su idea sí viaja",
])
def test_la_lista_detecta(frase):
    assert revisa(frase), frase


@pytest.mark.parametrize("frase", [
    "la firma temporal de la deriva baja", "es compatible con que el equipo se adapta al club",
    "no detectamos una diferencia mayor a 4.2 pp", "Bajo Jardine, el América tuvo posesiones más largas",
    "ningún par demuestra equivalencia al 3%", "la idea de la sección",
])
def test_la_lista_no_sobrerreacciona(frase):
    assert not revisa(frase), frase


def test_plantilla_limpia():
    assert revisa(gen.HTML) == []


def test_reporte_sintetico_limpio(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    _, _, pagina = modelo_desde(tmp_path)
    assert revisa(pagina) == []


@pytest.mark.skipif(not hay_reales(), reason="sin reports/ (los JSON no se versionan)")
def test_reporte_real_limpio():
    _, _, pagina = modelo_desde(REPORTS)
    assert revisa(pagina) == []


def test_el_generador_aborta_con_una_prohibida(tmp_path, monkeypatch):
    humo.escribe_sinteticos(tmp_path)
    monkeypatch.setattr(gen, "LIMITES", gen.LIMITES + " La rotación permite sostener el calendario.")
    monkeypatch.setattr("sys.argv", ["x", "--reports", str(tmp_path), "--out", str(tmp_path / "r.html")])
    with pytest.raises(SystemExit) as e:
        gen.main()
    assert "prohibidas" in str(e.value)
    assert not (tmp_path / "r.html").exists()
