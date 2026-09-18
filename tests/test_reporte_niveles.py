"""Niveles de ADR-59 §2 y cifras de §9 (marcador)."""
import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import REPORTS, gen, hay_reales, humo, modelo_desde


def test_B_sin_intervalo_no_se_construye():
    M = gen.Modelo({})
    with pytest.raises(ValueError):
        M.frase("B", "algo", ic=False)


def test_un_nivel_por_frase(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    datos, _, _ = modelo_desde(tmp_path)
    for _, s in gen.todas_las_secciones(datos):
        for b in s.get("bloques", []):
            if b["tipo"] == "frase":
                assert b["nivel"] in ("A", "B", "C")
                assert "significativ" not in b["html"].lower()
                if b["nivel"] == "B":
                    assert "[" in b["html"], b["html"][:80]


def test_nulo_con_margen():
    assert gen.margen([-0.042, 0.003]) == pytest.approx(0.042)
    assert gen.margen([0.001, 0.0705]) == pytest.approx(0.0705)


def test_formato_redondeo_y_cero():
    assert gen.f_pct(0.07049) == "+7.0%"
    assert gen.f_pp(-0.0000001) == "+0.0 pp"
    assert gen.f_pp(-0.027) == "−2.7 pp"


def test_seccion_sin_insumo_declara_comando(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    (tmp_path / "balon_parado_v2.json").unlink()
    datos, _, _ = modelo_desde(tmp_path)
    for h in datos["historias"]:
        s27 = next(s for s in h["acto2"] if s["id"] == "a2-7")
        assert s27["falta"]["comando"].startswith("python scripts/35_"), h["id"]


@pytest.mark.skipif(not hay_reales(), reason="sin reports/")
def test_marcador_real():
    datos, M, _ = modelo_desde(REPORTS)
    J, _ = gen.recolecta(REPORTS, REPORTS / "x")
    mk = gen.marcador(J)
    por = {}
    for p in mk:
        por.setdefault(p["adr"], [0, 0])
        por[p["adr"]][0] += p["cumple"]
        por[p["adr"]][1] += 1
    assert (sum(p["cumple"] for p in mk), len(mk)) == (20, 26)
    assert por == {53: [4, 4], 54: [2, 4], 55: [5, 7], 56: [5, 6], 57: [0, 1], 58: [4, 4]}
    assert gen.viajan_marcador(J["ctx"])[:2] == (3, 9)


@pytest.mark.skipif(not hay_reales(), reason="sin reports/")
def test_cifras_clave_de_adr59():
    _, M, _ = modelo_desde(REPORTS)
    t = {c["t"] for c in M.cifras}
    for v in ["+24.6%", "[+22.3, +26.9]", "+17.6%", "0.001", "0.056", "+11.0 pp",
              "[+8.0, +14.2]", "−0.32", "0 de 48", "6 de 6", "20 de 26", "3 de 9",
              "−10.0%", "+0.026", "4.2 pp"]:
        assert v in t, v
