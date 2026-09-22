"""ADR-61: el álgebra de 45 contra simulación, y un extremo a extremo sintético."""
import datetime as dt
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("prog45", RAIZ / "scripts" / "45_progresion.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def cadena(avance=0.5, fin=0.15, seed=0):
    """P verdadera 80×84, diagonal por bloques de fase. `avance` empuja hacia
    columnas más altas de la malla."""
    rng = np.random.default_rng(seed)
    P = np.zeros((G.NT, G.NS))
    for s in range(G.NT):
        z, f = divmod(s, G.NF)
        ix, iy = divmod(z, 4)
        vec = []
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            jx, jy = ix + dx, iy + dy
            if 0 <= jx < 5 and 0 <= jy < 4:
                w = (1 + avance) if dx == 1 else (1 - avance / 2 if dx == -1 else 1.0)
                vec.append(((jx * 4 + jy) * G.NF + f, w * (0.5 + rng.random())))
        tot = sum(w for _, w in vec)
        for j, w in vec:
            P[s, j] = (1 - fin) * w / tot
        P[s, G.NT:] = fin * np.array([.1, .2, .5, .2])
    return P


def simula(P, alfa, n, rng):
    out = []
    for _ in range(n):
        s = rng.choice(G.NT, p=alfa)
        pasos = [s]
        while True:
            t = rng.choice(G.NS, p=P[s])
            pasos.append(t)
            if t >= G.NT:
                break
            s = t
        out.append(pasos)
    return out


def test_franja_son_los_estados_64_a_79():
    assert np.flatnonzero(G.franja()).tolist() == list(range(64, 80))
    assert np.flatnonzero(G.franja(3)).tolist() == list(range(48, 80))
    assert G.bloque(0).tolist() == list(range(0, 80, 4))


def test_llegada_contra_simulacion():
    P = cadena(seed=1)
    alfa = np.zeros(G.NT)
    alfa[[0, 4, 21, 40]] = [.4, .3, .2, .1]
    L, tau = G.llegada(P, alfa)
    rng = np.random.default_rng(2)
    fm = G.franja()
    llega, ks = 0, []
    for pos in simula(P, alfa / alfa.sum(), 20000, rng):
        k = next((i for i, t in enumerate(pos[1:], 1) if t < G.NT and fm[t]), None)
        if k is not None:
            llega += 1
            ks.append(k)
    assert abs(L - llega / 20000) < 0.012
    assert abs(tau - np.mean(ks)) < 0.12


def test_el_alfa_dentro_de_la_franja_no_cuenta():
    P = cadena(seed=1)
    a1 = np.zeros(G.NT); a1[0] = 1
    a2 = a1.copy(); a2[70] = 5
    assert G.llegada(P, a1) == G.llegada(P, a2)


def test_supervivencia_del_modelo_contra_simulacion():
    P = cadena(avance=0.2, fin=0.2, seed=3)
    alfa = np.full(G.NT, 1 / G.NT)
    rng = np.random.default_rng(4)
    largos = [len(p) - 1 for p in simula(P, alfa, 20000, rng)]
    so, sm = G.supervivencia_obs(largos, 15), G.supervivencia_modelo(P, alfa, 15)
    assert so[0] == 1.0 and sm[0] == pytest.approx(1.0)
    assert max(abs(a - b) for a, b in zip(so, sm)) < 0.015


def test_cuasi_eigen_y_potencias_y_bloque_reducible():
    P = cadena(seed=5)
    b = G.bloque(0)
    Qb = P[np.ix_(b, b)]
    r = G.cuasi(Qb, np.ones(20), frames=True)
    pi = np.array(r["pi"])
    assert pi.min() > 0 and pi.sum() == pytest.approx(1)
    assert np.allclose(pi @ Qb, r["lambda1"] * pi, atol=1e-10)
    assert 1 < len(r["frames"]) <= G.MAX_FRAMES
    assert r["vida"] == pytest.approx(1 / (1 - r["lambda1"]))
    Qr = Qb.copy()
    Qr[:10, 10:] = 0
    Qr[10:, :10] = 0
    assert G.cuasi(Qr, np.ones(20)) is None


def test_intervalo_basic_p_y_bh():
    rng = np.random.default_rng(0)
    reps = rng.normal(0.3, 0.1, 4000)
    ic = G.ic_basic(0.3, reps)
    assert ic[0] < 0.3 < ic[1] and ic[0] > 0
    assert G.p_basic(0.3, reps) < 0.01
    assert G.p_basic(0.0, rng.normal(0, 0.1, 4000)) > 0.5
    q, r = G.bh([0.001, 0.02, 0.04, 0.5])
    assert r == [True, True, False, False] and q[0] == pytest.approx(0.004)


def _parquet(tmp, club, rival, eras, P_por_coach, rng, n_pos=40):
    pl = pytest.importorskip("polars")
    filas = []
    mid = ord(club[0]) * 100000
    alfa = np.zeros(G.NT); alfa[[0, 4, 8, 16, 20, 24]] = 1; alfa /= alfa.sum()
    uid = 0
    for coach, fechas in eras:
        for f in fechas:
            mid += 1
            for pos in simula(P_por_coach[coach], alfa, n_pos, rng):
                uid += 1
                for i, (a, b) in enumerate(zip(pos[:-1], pos[1:])):
                    filas.append((mid, club, coach, uid, i, a, b, b >= G.NT, f, f"J{i % 5}", "Pass"))
            filas.append((mid, rival, None, -1, 0, 0, 80, True, f, "x", "Pass"))
    d = tmp / f"processed_api_{club.lower()}"
    d.mkdir()
    pl.DataFrame(filas, schema=["match_id", "team", "coach", "poss_uid", "event_index", "from_state",
                                "to_state", "is_absorbing", "match_date", "player", "action_type"],
                 orient="row").write_parquet(d / "transitions.parquet")
    return d


def test_extremo_a_extremo_sintetico(tmp_path):
    pytest.importorskip("polars")
    pytest.importorskip("scipy")
    if not (RAIZ / "scripts" / "25_pares_h4.py").exists():
        pytest.skip("sin 25_pares_h4.py (la regla del torneo vive ahí)")
    rng = np.random.default_rng(9)
    f = [dt.date(2023, 8, 1) + dt.timedelta(days=3 * i) for i in range(20)]
    Pa, Pb = cadena(avance=0.9, seed=6), cadena(avance=0.1, seed=7)
    dA = _parquet(tmp_path, "Alfa", "Beta", [("A1", f)], {"A1": Pa}, rng)
    dB = _parquet(tmp_path, "Beta", "Alfa", [("B1", f)], {"B1": Pb}, rng)
    df = G.carga([dA, dB])
    d0 = G.diagnostico_fase(df)
    assert d0["cambian"] == 0 and d0["rama"] == "bloques"
    r = G.mide_era(df, "Alfa", "A1", np.random.default_rng(0), 99)
    assert r["n_partidos"] == 20 and r["n_poss"] == 800
    assert r["L"]["evaluable"] and r["L"]["D"] > 0          # Alfa empuja hacia adelante
    assert r["L"]["ic95"][0] > 0 and r["L"]["p"] < 0.05
    assert r["L"]["era"] == pytest.approx(G.llegada(Pa, np.ones(G.NT))[0], abs=0.2)
    assert r["cuasi"]["evaluable"] and len(r["cuasi"]["era"]["pi"]) == 20
    j = r["jugada"]
    assert j["objetivo"] == round(r["tau"]["era"]) and abs(j["acciones"] - j["objetivo"]) <= 2
    assert j["zonas"][-1] // 4 == 4 and all(z // 4 < 4 for z in j["zonas"][:-1])
    assert len(j["jugadores"]) == j["acciones"]


def test_diagnostico_detecta_cambio_de_fase(tmp_path):
    pl = pytest.importorskip("polars")
    df = pl.DataFrame({"club": ["A"] * 4, "from_state": [0, 0, 1, 2], "to_state": [4, 5, 81, 7]})
    d = G.diagnostico_fase(df)
    assert d["n"] == 3 and d["cambian"] == 2 and d["rama"] == "aborta"


def test_era_principal_por_partidos_y_empate_por_antiguedad():
    met = {"unidades": [{"club": "X", "coach": "C", "n_partidos": 30},
                        {"club": "Y", "coach": "C", "n_partidos": 30},
                        {"club": "Z", "coach": "C", "n_partidos": 10}]}
    h4 = {"parametros": {"torneos_orden": ["A1", "C2", "A2"]},
          "unidades": [{"club": "X", "coach": "C", "torneos": ["A2"]},
                       {"club": "Y", "coach": "C", "torneos": ["C2", "A2"]}]}
    assert G.era_principal(met, h4, "C")["club"] == "Y"
