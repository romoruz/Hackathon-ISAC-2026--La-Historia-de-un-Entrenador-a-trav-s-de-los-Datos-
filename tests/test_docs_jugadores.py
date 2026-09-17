"""Tests de scripts/39_docs_jugadores.py: las cifras salen del JSON, no del texto."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("docs39", RAIZ / "scripts" / "39_docs_jugadores.py")
dj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dj)


def _c(theta, ic, q=0.9, rech=False):
    return {"theta": theta, "ic95": ic, "q_adr52": q, "rechaza_adr52": rech, "q_casos": q,
            "rechaza_casos": False, "sin_exclusion_theta": theta}


def _A(pct_cont, parcial=False):
    a = {"n80": 15, "continuidad": 0.6, "jugadores_distintos": 27, "cambios_tacticos_por_partido": 1.5,
         "partidos": 17, "parcial": parcial}
    if not parcial:
        a.update(percentil_n80=0.8, percentil_continuidad=pct_cont,
                 percentil_jugadores_distintos=0.7, percentil_cambios_tacticos_por_partido=0.3)
    return a


def _J():
    liga = {tipo: {mt: {k: [0.01, 10] for k in ("perdiendo", "empatando", "ganando")}
                   for mt in ("M1", "M2", "M4", "FT")} for tipo in ("Tactical", "Injury")}
    u1 = {"club": "América", "coach": "Andre Jardine", "n_partidos": 34, "en_adr52": True, "en_casos": True,
          "A": {"A2023": _A(0.0), "C2024": _A(0.12), "A2024": _A(0.40), "C2025": _A(None, parcial=True)},
          "B": [{"player_id": 1, "minutos": 900.0, "posicion_modal": "Right Back", "acciones": 10,
                 "centro_ix": 2.0, "centro_iy": 2.8},
                {"player_id": 2, "minutos": 800.0, "posicion_modal": "Left Wing", "acciones": 10,
                 "centro_ix": 3.0, "centro_iy": 0.2}],
          "C": {"eventos": 20, "M1": _c(0.5, [-0.4, 1.4]), "M2": _c(0.04, [0.01, 0.08]),
                "M4": _c(-0.02, [-0.07, 0.03]), "FT": _c(0.02, [-0.07, 0.10])}}
    u2 = {"club": "Atlas", "coach": "Otro", "n_partidos": 30, "en_adr52": True, "en_casos": False,
          "A": {"A2023": _A(0.9)},
          "B": [{"player_id": 3, "minutos": 700.0, "posicion_modal": "Right Wing", "acciones": 5,
                 "centro_ix": 3.0, "centro_iy": 1.0}],
          "C": {"eventos": 5, "M1": _c(0.1, [-1, 1]), "M2": _c(0.2, [0.1, 0.3], q=0.01, rech=True),
                "M4": _c(0.0, [-1, 1]), "FT": _c(0.0, [None, None])}}
    return {"parametros": {"min_partidos_torneo": 12, "min_minutos_rol": 450.0, "n_boot": 6000},
            "diagnostico": {"reloj_positions": "acumulado", "muestras_reloj": 7,
                            "union_acciones_eventos": 1.0, "partidos_con_alineacion": 64,
                            "eventos_tacticos": 25, "eventos_lesion": 3},
            "liga": liga, "familias": {"adr52": {"m": 8, "rechazan": 1}, "casos": {"m": 4, "rechazan": 0}},
            "predicciones": [{"n": 1, "texto": "algo", "valor": [0.1, 5], "cumple": True}],
            "unidades": [u1, u2]}


class _D:
    def __init__(self, J):
        self.j = J


def test_rotacion_cuenta_solo_torneos_completos():
    r = dj.rotacion_era(_J()["unidades"][0])
    assert r["torneos"] == 3 and r["bajos"] == 2
    assert r["med_cont"] == pytest.approx(0.12)


def test_orientacion_sin_nombres():
    o = dj.orientacion(_J())
    assert o["Right"]["n"] == 2 and o["Right"]["frac_derecha"] == 0.5
    assert o["Left"]["n"] == 1 and o["Left"]["frac_derecha"] == 0.0


def test_excluye_cero_y_rechazos():
    J = _J()
    assert dj.excluye_cero(J["unidades"][0]["C"]["M2"])
    assert not dj.excluye_cero(J["unidades"][0]["C"]["M1"])
    assert not dj.excluye_cero(J["unidades"][1]["C"]["FT"])
    assert [(u["coach"], mt) for u, mt, _ in dj.rechazos(J)] == [("Otro", "M2")]


def test_adr58_sale_del_json():
    t = dj.adr58(_D(_J()))
    assert t.count("## ADR-58 ·") == 1 and dj.MARCA in t
    assert "ADR-52: 1 de 8 rechazan" in t and "Atlas · Otro · M2" in t
    assert "25 tácticos y 3 por lesión" in t
    assert not re.search(r"ADR-59", t)        # verificar_docs exige ADR definidas


def test_seccion_33_sale_del_json():
    t = dj.seccion_33(_D(_J()))
    assert t.lstrip().startswith(dj.MARCA)
    assert "# 33. 🟢 Uso de jugadores (ADR-58)" in t
    assert "en 2 de 3 torneos completos" in t
    assert "1 de 4 intervalos excluyen el cero" in t      # solo las eras del América
    assert "(parcial)" in t and "banda derecha" in t
    assert "eje Y" not in t                               # verificar_docs, chequeo 2
    assert "Otro" not in t.split("## 33.2")[0].split("Las eras de casos")[0]


def test_readme_linea():
    l = dj.readme_linea(_D(_J()))
    assert l.startswith("- **Jugadores (ADR-58).**") and l.rstrip().endswith(dj.MARCA)
    assert "Andre Jardine 2 de 3" in l


def test_construye_es_idempotente(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "13_CONTEXTO_IA.md").write_text("| 3 | `06` | 57 ADRs. **No reabrir debates cerrados** |\n")
    (docs / "README.md").write_text("| 06 | [Decisiones (57 ADRs)](06_DECISIONS.md) |\n\n- casos §31.\n\n## Retirados\n")
    (docs / "06_DECISIONS.md").write_text("# 06\n\n" + dj.NOTA_54 + "\n")
    (docs / "10_RESULTADOS.md").write_text("# 10\n\n" + dj.NOTA_28 + " (2) algo\n")
    D = _D(_J())
    nuevos = dj.construye(D, docs)
    assert len(nuevos) == 4
    for p, t in nuevos.items():
        p.write_text(t)
    assert "58 ADRs" in (docs / "README.md").read_text()
    assert dj.NOTA_54_NUEVA in (docs / "06_DECISIONS.md").read_text()
    assert dj.NOTA_28_NUEVA in (docs / "10_RESULTADOS.md").read_text()
    assert dj.construye(D, docs) == {}                    # segunda pasada: nada
