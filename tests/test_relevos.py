"""ADR-60 (42_relevos.py): álgebra, nula, deriva y extremo a extremo sintético."""
import datetime as dt
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("relevos42", RAIZ / "scripts" / "42_relevos.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def _dist(rng, n=20):
    v = rng.random(n) ** 2
    return v / v.sum()


def test_identidad_exacta_y_reparto_de_la_interaccion():
    rng = np.random.default_rng(1)
    J = 12
    Ya = rng.integers(0, 60, (J, 20)).astype(float)
    Yb = rng.integers(0, 60, (J, 20)).astype(float)
    Yb[9:] = 0            # tres que salen
    Ya[:2] = 0            # dos que llegan
    La, Lb = _dist(rng), _dist(rng)
    S = np.zeros(J, bool)
    S[2:9] = True
    d, U, C = R.descompone(Ya, Yb, La, Lb, S)
    assert np.abs(d - U - C).max() < 1e-12
    # un solo compartido: U = w̄·Δz* y la mitad de la interacción está en U
    S1 = np.zeros(J, bool)
    S1[4] = True
    d, U, C = R.descompone(Ya, Yb, La, Lb, S1)
    na, nb, Na, Nb = Ya[4].sum(), Yb[4].sum(), Ya.sum(), Yb.sum()
    wa, wb = na / Na, nb / Nb
    za, zb = Ya[4] / na - La, Yb[4] / nb - Lb
    assert np.allclose(U, (wa + wb) / 2 * (zb - za))
    assert np.allclose(U, wa * (zb - za) + 0.5 * (wb - wa) * (zb - za))


def test_sin_compartidos_todo_es_composicion():
    rng = np.random.default_rng(2)
    Ya = rng.integers(0, 50, (5, 20)).astype(float)
    Yb = rng.integers(0, 50, (5, 20)).astype(float)
    d, U, C = R.descompone(Ya, Yb, _dist(rng), _dist(rng), np.zeros(5, bool))
    assert np.abs(U).sum() == 0 and np.allclose(d, C)


def _partidos(rng, M, base, n=300):
    Xc = np.array([rng.multinomial(n, base) for _ in range(M)], float)
    return Xc, np.full(M, float(n))


def test_nula_no_rechaza_si_son_iguales_y_si_si_difieren():
    rng = np.random.default_rng(3)
    base = _dist(rng)
    Xc, n = _partidos(rng, 60, base)
    Xl = n[:, None] * base
    en_a = np.r_[np.ones(30), np.zeros(30)]
    Y = Xc[:, None, :]
    A = {"en_a": en_a, "n": n, "Xc": Xc, "Xl": Xl, "Y": Y, "jugadores": [1], "M": 60}
    r = R.analiza(A, np.random.default_rng(0), 499, 50)
    assert r["p"] > 0.05
    otra = base.copy()
    otra[:5] *= 2
    otra /= otra.sum()
    Xb, _ = _partidos(rng, 30, otra)
    A["Xc"] = np.r_[Xc[:30], Xb]
    A["Y"] = A["Xc"][:, None, :]
    r = R.analiza(A, np.random.default_rng(0), 499, 50)
    assert r["p"] < 0.01


def test_la_liga_del_torneo_absorbe_la_deriva():
    """Mismo exceso sobre su liga en las dos eras, pero la liga cambió de un
    torneo a otro: T casi cero. Sin restar la liga, T sería grande."""
    rng = np.random.default_rng(4)
    L1, L2 = _dist(rng), _dist(rng)
    exceso = np.zeros(20)
    exceso[:4], exceso[4:8] = 0.01, -0.01
    n = np.full(40, 5000.0)
    Xc = np.r_[[n[0] * (L1 + exceso)] * 20, [n[0] * (L2 + exceso)] * 20]
    Xl = np.r_[[n[0] * L1] * 20, [n[0] * L2] * 20]
    pa = np.r_[np.ones(20), np.zeros(20)]
    assert R.estadistico_T(Xc, Xl, n, pa, 1 - pa) < 1e-12
    assert R.estadistico_T(Xc, 0 * Xl, n, pa, 1 - pa) > 0.05


def test_bh_conocido():
    q = R.bh([0.01, 0.04, 0.03, 0.5])
    assert np.allclose(q, [0.04, 0.16 / 3, 0.16 / 3, 0.5])


def test_spearman():
    assert R.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1)
    assert R.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1)


def test_familia_real_son_21():
    rep = RAIZ / "reports"
    if not (rep / "did_h4_v1.json").exists():
        pytest.skip("sin reports/")
    h4 = json.loads((rep / "did_h4_v1.json").read_text())
    met = json.loads((rep / "metricas_v1.json").read_text())
    fam, t0 = R.familia(h4, met)
    assert len(fam) == 21
    assert ("Tijuana", "Miguel Herrera", "Juan Carlos Osorio") in fam
    assert ("León", "Ariel Holan", "Nicolas Larcamon") in fam
    assert all(t0[(c, a)] < t0[(c, b)] for c, a, b in fam)


def test_familia_que_no_cuadra_aborta():
    h4 = {"parametros": {"torneos_orden": ["A2021"]},
          "unidades": [{"club": "X", "coach": "Andre Jardine", "torneos": ["A2021"]}], "pares": []}
    met = {"unidades": [{"club": "X", "coach": "Andre Jardine"}]}
    with pytest.raises(R.Aborta, match="21"):
        R.familia(h4, met)


def _parquet_sintetico(tmp, club, rival, eras, rng, sesgo=None):
    pl = pytest.importorskip("polars")
    filas = []
    mid = ord(club[0]) * 100000
    for coach, fechas, jugadores in eras:
        for f in fechas:
            mid += 1
            for _ in range(250):
                j = int(rng.choice(jugadores))
                z = int(rng.integers(0, 20)) if sesgo is None or coach != sesgo else int(rng.integers(0, 8))
                s = z * 4 + int(rng.integers(0, 4))
                filas.append((mid, club, coach, j, s, s, False, f))
            for _ in range(250):
                z = int(rng.integers(0, 20))
                filas.append((mid, rival, None, 999, z * 4, z * 4, False, f))
    d = tmp / f"processed_api_{club.lower()}"
    d.mkdir()
    pl.DataFrame(filas, schema=["match_id", "team", "coach", "player_id", "from_state", "to_state",
                                "is_absorbing", "match_date"], orient="row").write_parquet(d / "transitions.parquet")
    return d


def test_extremo_a_extremo_sintetico(tmp_path, monkeypatch):
    pytest.importorskip("polars")
    if not (RAIZ / "scripts" / "25_pares_h4.py").exists():
        pytest.skip("sin 25_pares_h4.py (la regla del torneo vive ahí)")
    rng = np.random.default_rng(5)
    f1 = [dt.date(2023, 8, d) for d in range(1, 21)]
    f2 = [dt.date(2024, 2, d) for d in range(1, 21)]
    dA = _parquet_sintetico(tmp_path, "Alfa", "Beta", [("A1", f1, list(range(1, 15))),
                                                       ("A2", f2, list(range(8, 22)))], rng, sesgo="A2")
    dB = _parquet_sintetico(tmp_path, "Beta", "Alfa", [("B1", f1 + f2, list(range(30, 44)))], rng)
    df = R.carga_acciones([dA, dB])
    assert set(df["club"].unique().to_list()) == {"Alfa", "Beta"}
    assert df.filter(df["coach"].is_null()).height == 0
    liga = R.referencia_liga(df)
    A = R.arreglos_pareja(df, liga, "Alfa", "A1", "A2")
    r = R.analiza(A, np.random.default_rng(0), 199, 50)
    assert r["p"] < 0.05                     # A2 concentra el juego en 8 zonas
    assert r["umbrales"]["200"]["compartidos"] >= 3
    assert r["estimable"] and 0 <= r["umbrales"]["200"]["phi_U"] <= 1
    assert r["ic95"]["T"][0] > 0 and r["ic95"]["phi_U"] is not None
