"""ADR-63: toques por jugador y zona. Prueba las piezas y las guardas sobre
parquets sintéticos, sin tocar los datos reales.

No valida hallazgos (no los hay: todo es descriptivo). Valida que las
distribuciones suman 1, que T es la distancia de variación total, que el umbral
de toques y el mínimo de jugadores se aplican, y que el script aborta cuando
falta `player_id`."""
import importlib.util
import json
import pathlib
import subprocess
import sys

import numpy as np
import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
pl = pytest.importorskip("polars")


def mod():
    spec = importlib.util.spec_from_file_location("jz47", RAIZ / "scripts" / "47_jugadores_zona.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class G:                      # lo mínimo de 45 que usa 47
    NF = 4

    class Aborta(Exception):
        pass


def filas(club, coach, jug_zonas, m0=0):
    """jug_zonas: {player_id: [(zona, veces), ...]}"""
    import datetime as dt
    base = dt.date(2024, 1, 1)
    r = []
    n = 0
    for pid, zs in jug_zonas.items():
        for z, veces in zs:
            for _ in range(veces):
                mid = m0 + n // 30
                r.append({"match_id": mid, "team": club, "coach": coach,
                          "from_state": z * G.NF, "match_date": base + dt.timedelta(days=mid),
                          "player_id": pid, "player": f"J{pid}"})
                n += 1
    return r


def tabla(rs):
    return pl.DataFrame(rs)


def test_reparto_suma_uno_y_cuenta_toques():
    m = mod()
    t = tabla(filas("A", "X", {7: [(3, 40), (5, 60)]}))
    r = m.reparto(G, t)
    p, n = r[7]
    assert n == 100
    assert abs(p.sum() - 1) < 1e-12
    assert p[3] == pytest.approx(.4) and p[5] == pytest.approx(.6)
    assert p[0] == 0


def test_T_es_la_variacion_total():
    m = mod()
    a, b = np.zeros(20), np.zeros(20)
    a[0] = a[1] = .5
    b[2] = b[3] = .5
    assert m.T_de(a, a) == 0
    assert m.T_de(a, b) == pytest.approx(1.0)
    c = a.copy(); c[0] = .4; c[1] = .6
    assert m.T_de(a, c) == pytest.approx(.1)


def test_T_no_depende_del_orden():
    m = mod()
    rng = np.random.default_rng(0)
    a = rng.random(20); a /= a.sum()
    b = rng.random(20); b /= b.sum()
    assert m.T_de(a, b) == pytest.approx(m.T_de(b, a))


def test_un_jugador_que_no_se_mueve_da_cero():
    m = mod()
    zs = {9: [(2, 150), (8, 150)]}
    ra = m.reparto(G, tabla(filas("A", "X", zs)))
    rb = m.reparto(G, tabla(filas("A", "Y", zs)))
    assert m.T_de(ra[9][0], rb[9][0]) == 0


def _corre(tmp_path, con_player_id=True, n_jug=6, toques=300):
    """Monta data/processed_api_* + reports/did_h4_v1.json y corre el script."""
    raiz = tmp_path
    (raiz / "reports").mkdir(parents=True)
    d = raiz / "data" / "processed_api_uno"
    d.mkdir(parents=True)
    rs = []
    for j in range(n_jug):
        rs += filas("Uno", "Ana", {100 + j: [(3, toques // 2), (5, toques - toques // 2)]})
        rs += filas("Uno", "Bea", {100 + j: [(3, toques // 4), (9, toques - toques // 4)]}, m0=500)
    t = tabla(rs)
    if not con_player_id:
        t = t.drop("player_id")
    t.write_parquet(d / "transitions.parquet")
    (raiz / "reports" / "did_h4_v1.json").write_text(json.dumps(
        {"pares": [{"club": "Uno", "a": "Ana", "b": "Bea"}]}), encoding="utf-8")
    src = (RAIZ / "scripts" / "47_jugadores_zona.py").read_text()
    src = src.replace('RAIZ = Path(__file__).resolve().parent.parent',
                      f'RAIZ = Path({str(raiz)!r})')
    src = src.replace('if len(indirs) != 18:', 'if len(indirs) != 1:')
    src = src.replace('coaches = {c for _, c in G.HISTORIAS}',
                      'coaches = {"Ana", "Bea"}')
    src = src.replace('    G = _g45()', '''    class G:
        NF = 4
        class Aborta(Exception): pass
''')
    p = raiz / "s47.py"
    p.write_text(src, encoding="utf-8")
    out = raiz / "reports" / "jz.json"
    r = subprocess.run([sys.executable, str(p), "--out", str(out)], capture_output=True, text=True)
    return r, out


def test_corrida_completa(tmp_path):
    r, out = _corre(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    J = json.loads(out.read_text(encoding="utf-8"))
    par = J["pares"][0]
    assert par["n_jugadores"] == 6 and "hueco" not in par
    assert len(par["jugadores"]) == 6
    j = par["jugadores"][0]
    assert abs(sum(j["p_a"]) - 1) < 1e-6 and abs(sum(j["p_b"]) - 1) < 1e-6
    assert 0 <= j["T"] <= 1
    # ordenado de mayor a menor movimiento
    assert [x["T"] for x in par["jugadores"]] == sorted((x["T"] for x in par["jugadores"]), reverse=True)


def test_umbral_de_jugadores_declara_el_hueco(tmp_path):
    r, out = _corre(tmp_path, n_jug=3)
    assert r.returncode == 0, r.stdout + r.stderr
    par = json.loads(out.read_text(encoding="utf-8"))["pares"][0]
    assert "hueco" in par and "3 jugadores" in par["hueco"] and "jugadores" not in par


def test_umbral_de_toques_deja_fuera_al_que_jugo_poco(tmp_path):
    r, out = _corre(tmp_path, toques=100)     # por debajo de los 200 preinscritos
    assert r.returncode == 0, r.stdout + r.stderr
    par = json.loads(out.read_text(encoding="utf-8"))["pares"][0]
    assert par["n_jugadores"] == 0 and "hueco" in par


def test_sin_player_id_aborta(tmp_path):
    r, _ = _corre(tmp_path, con_player_id=False)
    assert r.returncode != 0
    assert "D63-8" in (r.stdout + r.stderr) and "player_id" in (r.stdout + r.stderr)
