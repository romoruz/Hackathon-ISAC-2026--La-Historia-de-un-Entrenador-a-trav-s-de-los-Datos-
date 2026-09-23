"""ADR-59 adendas 2 y 3: tres actos, cinco historias, cuerpo corto con frase y figura, anexo completo."""
import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # noqa: E402
from _reporte_comun import RAIZ, REPORTS, gen, hay_reales, humo, modelo_desde

ESPERADO = {  # historia: (eras, principal), ADR-59 adenda 2 §2
    "jardine": ({"América", "Atlético San Luis"}, "América"),
    "larcamon": ({"Puebla", "León", "Cruz Azul"}, "Puebla"),
    "ambriz": ({"Toluca", "Santos Laguna"}, "Toluca"),
    "herrera": ({"Tigres UANL", "Tijuana"}, "Tigres UANL"),
    "ortiz": ({"América", "Monterrey"}, "América"),
}


@pytest.fixture(scope="module")
def sint(tmp_path_factory):
    d = tmp_path_factory.mktemp("rep")
    humo.escribe_sinteticos(d)
    return (d, *modelo_desde(d))


@pytest.fixture(scope="module")
def real():
    if not hay_reales():
        pytest.skip("sin reports/ (los JSON no se versionan)")
    return modelo_desde(REPORTS)


def _h(datos, hid):
    return next(h for h in datos["historias"] if h["id"] == hid)


def test_cinco_historias_en_orden(sint):
    _, datos, _, _ = sint
    assert [h["id"] for h in datos["historias"]] == ["jardine", "larcamon", "ambriz", "herrera", "ortiz"]


def test_homonimo_no_entra(sint):
    _, datos, _, _ = sint
    assert {e["club"] for e in _h(datos, "herrera")["eras"]} == {"Tigres UANL", "Tijuana"}


def test_eras_y_principal_reales(real):
    datos, _, _ = real
    for hid, (eras, principal) in ESPERADO.items():
        h = _h(datos, hid)
        assert {e["club"] for e in h["eras"]} == eras, hid
        assert h["principal"] == principal, hid


def _capas_completas(datos):
    """Adenda 3 §3: cada sección del cuerpo lleva frase y figura, o las declara."""
    for h in datos["historias"]:
        for s in h["acto2"] + h["acto3"]:
            if "pendiente" in s or "falta" in s:
                continue
            capas = {b.get("capa") for b in s["bloques"]}
            assert {1, 2} <= capas, (h["id"], s["id"], capas)


def test_cuatro_capas_sintetico(sint):
    _capas_completas(sint[1])


def test_cuatro_capas_real(real):
    _capas_completas(real[0])


def _portada(datos):
    for h in datos["historias"]:
        ranuras = [b["portada"] for s in h["acto2"] + h["acto3"] for b in s.get("bloques", [])
                   if b.get("portada")]
        assert sorted(ranuras) == [1, 2, 3, 4, 5], (h["id"], ranuras)


def test_portada_cinco_ranuras_fijas(sint):
    _portada(sint[1])


def test_portada_real(real):
    _portada(real[0])


def test_pendientes_declarados(sint):
    _, datos, _, _ = sint
    for h in datos["historias"]:
        pend = {s["id"]: s["pendiente"]["adr"] for s in h["acto2"] + h["acto3"] if "pendiente" in s}
        assert pend == {}, h["id"]


def _a2_4(datos, hid):
    h = _h(datos, hid)
    cuerpo = next(s for s in h["acto2"] if s["id"] == "a2-4")
    anexo = next((s for s in h.get("anexo", []) if s["id"] == "x-a2-4"), None)
    return cuerpo, anexo


def test_presion_fuera_de_adr54_se_declara(real):
    """ADR-54 midió presión en seis clubes. Ninguna historia puede quedarse
    callada: o trae las frases de presión, o dice por qué no las tiene.

    Desde la adenda 3 el cuerpo se queda con UNA frase (la de npxG concedido) y
    las de presión viven completas en el anexo; por eso se exigen ahí. Lo que el
    cuerpo sí debe traer es el hueco cuando NINGÚN club de la historia se midió.
    (Antes este test pedía la frase en el cuerpo y llevaba dormido desde h2_31:
    solo corre con los siete JSON reales, y `simulador_v2.json` no existió hasta
    h2_37.)"""
    datos, _, _ = real
    for hid in ("ambriz", "herrera"):        # ningún club suyo está entre los seis
        cuerpo, _a = _a2_4(datos, hid)
        huecos = [b["html"] for b in cuerpo["bloques"] if b["tipo"] == "hueco"]
        assert huecos and "seis clubes" in huecos[0], hid
    # Larcamón sí tiene clubes medidos (León, Cruz Azul) aunque su principal, Puebla, no lo esté
    cuerpo, anexo = _a2_4(datos, "larcamon")
    assert anexo is not None
    assert any("Presión (E2" in b.get("html", "") for b in anexo["bloques"])
    assert not [b for b in cuerpo["bloques"] if b["tipo"] == "hueco"], "no hay hueco que declarar"
    assert any(b["tipo"] == "enlace" for b in cuerpo["bloques"]), "sin enlace al anexo"


def test_ninguna_historia_calla_la_presion(real):
    """El contrato, para las cinco: frases de presión en el anexo o hueco en el cuerpo."""
    datos, _, _ = real
    for hid in ESPERADO:
        cuerpo, anexo = _a2_4(datos, hid)
        con = anexo is not None and any("Presión (E2" in b.get("html", "") for b in anexo["bloques"])
        hueco = any(b["tipo"] == "hueco" and "seis clubes" in b.get("html", "")
                    for b in cuerpo["bloques"])
        assert con != hueco, f"{hid}: presión medida={con}, hueco={hueco}"


def test_antes_y_despues(sint):
    _, datos, _, _ = sint
    s31 = next(s for s in _h(datos, "larcamon")["anexo"] if s["id"] == "x-a3-1")
    txt = " ".join(b.get("html", "") for b in s31["bloques"])
    assert "Holan llegó antes" in txt and "Berizzo llegó después" in txt


def test_macros_solo_de_jardine_y_unicas(sint):
    _, _, M, _ = sint
    con = [c for c in M.cifras if c["k"]]
    assert con and all(c["h"] in ("jardine", "comun") for c in con)
    por = {}
    for c in con:
        por.setdefault(c["k"], set()).add(c["t"])
    assert all(len(v) == 1 for v in por.values()), {k: v for k, v in por.items() if len(v) > 1}


def test_la_guia_encuentra_sus_macros(real):
    _, M, _ = real
    guia = (RAIZ / "docs" / "20_GUIA_REPORTE.tex")
    if not guia.exists():
        pytest.skip("sin la guía LaTeX")
    usadas = set(re.findall(r"\\cifra([A-Z][A-Za-z]*)", guia.read_text(encoding="utf-8")))
    assert usadas <= {c["k"] for c in M.cifras if c["k"]}


def test_no_lee_el_barrido(tmp_path):
    humo.escribe_sinteticos(tmp_path)
    (tmp_path / "barrido").mkdir()
    (tmp_path / "barrido" / "traslados.csv").write_text("coach,distancia_perfil\nCENTINELA_BARRIDO,6.00\n")
    _, _, pagina = modelo_desde(tmp_path)
    assert "CENTINELA_BARRIDO" not in pagina
    src = (RAIZ / "scripts" / "12_reporte_html.py").read_text(encoding="utf-8")
    assert "read_csv" not in src


def test_el_cuerpo_no_trae_intervalos_ni_q(sint):
    """Adenda 3 §3: en el cuerpo, ni intervalos ni el número de q; la lectura en palabras sí."""
    _, datos, _, _ = sint
    for _, s in gen.todas_las_secciones(datos, anexo=False):
        for b in s.get("bloques", []):
            h = b.get("html") or ""
            assert '<span class="tec">' not in h, h[:120]
            assert not re.search(r"\bq = ", re.sub(r"<[^>]+>", " ", h)), h[:120]


def test_en_el_anexo_intervalos_y_q_son_tecnicos_y_el_margen_no(sint):
    _, datos, _, _ = sint
    for _, s in gen.todas_las_secciones(datos):
        if not s["id"].startswith("x-"):
            continue
        for b in s.get("bloques", []):
            if b["tipo"] != "frase":
                continue
            h = b["html"]
            for m in re.finditer(r"q = ", h):
                assert h[:m.start()].endswith('<span class="tec">, '), h[:120]
            if b["nivel"] == "B":
                assert '<span class="tec"> <span class="cf"' in h, h[:120]
            if b.get("nulo"):
                sin_tec = re.sub(r'<span class="tec">.*?</span></span>', "", h)
                assert re.search(r"(mayor|menor) a <span class=\"cf\"|sobreviven a la correcci", sin_tec), h[:160]


def test_lectura_de_jardine_rota_aborta(tmp_path, monkeypatch):
    humo.escribe_sinteticos(tmp_path)
    m = json.loads((tmp_path / "metricas_v1.json").read_text())
    for u in m["unidades"]:
        if (u["club"], u["coach"]) == ("Atlético San Luis", "Andre Jardine"):
            u["global"]["field_tilt"]["dif"] = 0.05
    (tmp_path / "metricas_v1.json").write_text(json.dumps(m))
    with pytest.raises(SystemExit, match="LECTURA PREINSCRITA ROTA.*jardine"):
        modelo_desde(tmp_path)


def test_otra_historia_no_tiene_lectura_preinscrita(tmp_path):
    """Si cambia el signo de Larcamón, la plantilla redacta otra cosa; no aborta."""
    humo.escribe_sinteticos(tmp_path)
    m = json.loads((tmp_path / "metricas_v1.json").read_text())
    for u in m["unidades"]:
        if (u["club"], u["coach"]) == ("Puebla", "Nicolas Larcamon"):
            u["global"]["field_tilt"].update(dif=0.2, ic95=[0.15, 0.25])
    (tmp_path / "metricas_v1.json").write_text(json.dumps(m))
    datos, _, _ = modelo_desde(tmp_path)
    s23 = next(s for s in _h(datos, "larcamon")["acto2"] if s["id"] == "a2-3")
    ft = next(b for b in s23["bloques"] if b.get("portada") == 2)
    assert "por encima de la liga" in ft["html"]


def test_T_y_descomposicion_en_cada_historia(sint):
    """ADR-60: 3.1 lleva T (A o nulo), 3.2 la descomposición, 3.3 el mapa."""
    _, datos, _, _ = sint
    for h in datos["historias"]:
        s31 = next(s for s in h["anexo"] if s["id"] == "x-a3-1")
        assert any("Uso del campo tras el relevo" in b.get("html", "") for b in s31["bloques"]), h["id"]
        c31 = next(s for s in h["acto3"] if s["id"] == "a3-1")
        assert any("reparto de las acciones" in b.get("html", "") for b in c31["bloques"]), h["id"]
        s32 = next(s for s in h["anexo"] if s["id"] == "x-plantel")
        niveles = {b["nivel"] for b in s32["bloques"] if b["tipo"] == "frase"}
        assert niveles <= {"B", "C"}, (h["id"], niveles)
        s33 = next(s for s in h["anexo"] if s["id"] == "x-a3-2")
        assert all(b["nivel"] == "C" for b in s33["bloques"] if b["tipo"] == "frase")


def test_inestable_baja_a_C_y_lo_dice(sint):
    _, datos, _, _ = sint
    s32 = next(s for s in _h(datos, "herrera")["anexo"] if s["id"] == "x-plantel")
    inest = [b for b in s32["bloques"] if b["tipo"] == "frase" and "depende del umbral" in b["html"]]
    assert inest and all(b["nivel"] == "C" for b in inest)


def test_sin_uso_estimable_no_da_cifra(sint):
    _, datos, _, _ = sint
    s32 = next(s for s in _h(datos, "ambriz")["anexo"] if s["id"] == "x-plantel")
    assert any("no se estima" in b["html"] for b in s32["bloques"] if b["tipo"] == "frase")


def test_marcador_separa_adr60_y_no_evaluables(sint):
    _, datos, _, _ = sint
    c1 = next(s for s in datos["anexo"] if s["id"] == "x-c-1")
    txt = " ".join(b.get("html", "") for b in c1["bloques"])
    assert "Relevos (ADR-60)" in txt and "no se pudo evaluar" in txt
