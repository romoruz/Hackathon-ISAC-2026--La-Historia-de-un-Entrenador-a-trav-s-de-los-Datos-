"""h2_32: el mapa de zonas no falla en silencio.

Parquet ausente = hueco declarado. Parquet presente pero ilegible (sin polars,
archivo roto) o sin filas para la era = error: la página no se escribe.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import gen, humo, modelo_desde

pl = pytest.importorskip("polars")
RUTA = "data/processed_api_america/transitions.parquet"


def _datos(tmp_path):
    rep = tmp_path / "reports"
    humo.escribe_sinteticos(rep)
    return rep, tmp_path / "raiz"


def _construye(rep, raiz):
    J, traza = gen.recolecta(rep, raiz)
    return gen.construye(J, traza)


def test_sin_parquet_es_hueco(tmp_path):
    rep, raiz = _datos(tmp_path)
    datos, _ = _construye(rep, raiz)
    h = datos["historias"][0]
    fig = next(b for b in next(x for x in h["acto2"] if x["id"] == "a2-1")["bloques"] if b.get("id") == "fig2")
    assert "falta" in fig["datos"]


def test_parquet_roto_aborta(tmp_path):
    rep, raiz = _datos(tmp_path)
    (raiz / RUTA).parent.mkdir(parents=True)
    (raiz / RUTA).write_bytes(b"esto no es un parquet")
    with pytest.raises(gen.ZonasIlegibles, match="no se pudo leer"):
        _construye(rep, raiz)


def test_sin_polars_aborta(tmp_path, monkeypatch):
    rep, raiz = _datos(tmp_path)
    (raiz / RUTA).parent.mkdir(parents=True)
    pl.DataFrame({"team": ["América"], "coach": ["Andre Jardine"], "from_state": [0]}).write_parquet(raiz / RUTA)
    monkeypatch.setitem(sys.modules, "polars", None)
    with pytest.raises(gen.ZonasIlegibles, match="polars"):
        _construye(rep, raiz)


def test_cero_filas_aborta(tmp_path):
    rep, raiz = _datos(tmp_path)
    (raiz / RUTA).parent.mkdir(parents=True)
    pl.DataFrame({"team": ["Club América"], "coach": ["Andre Jardine"], "from_state": [0]}).write_parquet(raiz / RUTA)
    with pytest.raises(gen.ZonasIlegibles, match="0 filas"):
        _construye(rep, raiz)


def test_main_sale_con_error_y_no_escribe(tmp_path, monkeypatch):
    rep, raiz = _datos(tmp_path)
    (raiz / RUTA).parent.mkdir(parents=True)
    (raiz / RUTA).write_bytes(b"roto")
    out = tmp_path / "r.html"
    monkeypatch.setattr("sys.argv", ["x", "--reports", str(rep), "--datos", str(raiz), "--out", str(out)])
    with pytest.raises(SystemExit) as e:
        gen.main()
    assert "ZONAS ILEGIBLES" in str(e.value) and not out.exists()


def test_parquet_bueno_pinta(tmp_path):
    rep, raiz = _datos(tmp_path)
    (raiz / RUTA).parent.mkdir(parents=True)
    pl.DataFrame({"team": ["América"] * 3, "coach": ["Andre Jardine"] * 3,
                  "from_state": [0, 4, 79]}).write_parquet(raiz / RUTA)
    datos, _ = _construye(rep, raiz)
    fig = next(b for b in next(x for x in datos["historias"][0]["acto2"] if x["id"] == "a2-1")["bloques"] if b.get("id") == "fig2")
    assert fig["datos"]["n"] == 3 and fig["datos"]["fuera"] == 0
