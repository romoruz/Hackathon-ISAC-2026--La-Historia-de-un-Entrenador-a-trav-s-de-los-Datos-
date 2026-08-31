#!/usr/bin/env python3
"""Prueba de humo del reporte: genera datos sinteticos con la MISMA forma que
`recolecta()` y ejecuta la pagina en un DOM de verdad.

Por que hace falta: `node --check` solo dice que el JavaScript compila. Doce de
los doce bugs de este proyecto compilaban. Lo que hay que comprobar es que la
pagina se PINTA: que `render()` recorre las cinco secciones, que ninguna figura
lanza al leer una clave que no existe, y que el HTML resultante contiene lo que
deberia contener.

No valida numeros — para eso estan los scripts de `reports/`. Valida que la
plantilla no este rota, que es justo lo que un cambio de maquetacion rompe.

Uso:  python scripts/humo_reporte.py
      python scripts/humo_reporte.py ruta/al/12_reporte_html.py
"""
import json
import random
import shutil
import re
import subprocess
import sys
from pathlib import Path

rng = random.Random(20260826)

FASES = ["open", "transition", "restart", "set_piece"]


def mapa():
    m = [[rng.random() ** 2 + 0.05 for _ in range(4)] for _ in range(5)]
    t = sum(sum(f) for f in m)
    return [[round(v / t, 5) for v in f] for f in m]


def ic(a, b, pct):
    """Replica la forma que emite 08_ic_derivados.py."""
    d = (a - b) / b * 100
    w = abs(d) * 0.3 + 2
    lo, hi = d - w, d + w
    return {"a": a, "b": b, "diff_pct": round(d, 2),
            "lo_pct": round(lo, 2), "hi_pct": round(hi, 2),
            "excluye_cero": lo * hi > 0}


def club(nombre, dts):
    pares, huella, jugadores, dpares = {}, {}, {}, {}
    for a in dts:
        huella[a] = sorted(
            [{"estado": f"z{rng.randrange(5)}{rng.randrange(4)}|{rng.choice(FASES)}",
              "n": rng.randrange(60, 900), "tv": round(rng.uniform(.05, .3), 4),
              "ruido": round(rng.uniform(.02, .08), 4),
              "exceso": round(rng.uniform(.01, .22), 4)} for _ in range(9)],
            key=lambda d: -d["exceso"])

    for i, a in enumerate(dts):
        for b in dts[i + 1:]:
            ea, eb = rng.uniform(5.5, 8.5), rng.uniform(5.5, 8.5)
            ra, rb = rng.uniform(.07, .13), rng.uniform(.07, .13)
            ga, gb = rng.uniform(.010, .020), rng.uniform(.010, .020)
            # Un par SIN cambios (0 de N) y otro CON: la version anterior del
            # generador solo producia el caso con cambios, y por eso el humo
            # pasaba mientras la seccion 03 se quedaba en blanco con 0/12.
            ninguno = (i + len(dts)) % 2 == 0
            lista = [{"id": 1000 + k, "nombre": f"Jugador Sintetico {k}",
                      "exceso": round(rng.uniform(.01, .09), 3),
                      "cambio": (not ninguno) and k < 2} for k in range(6)]
            pares[f"{a}|{b}"] = {
                "et": ic(ea, eb, 1), "rem": ic(ra, rb, 1), "gol": ic(ga, gb, 1),
                "n_a": rng.randrange(2000, 12000), "n_b": rng.randrange(2000, 12000),
                "plantel": {"compartidos": 13, "jugadores_a": 24, "pct": 61.4,
                            "cambian": sum(1 for j in lista if j["cambio"]),
                            "total": len(lista), "lista": lista}}
            for j in lista:
                jugadores[str(j["id"])] = {
                    "nombre": j["nombre"],
                    "mapas": {co: mapa() for co in dts}}
            zonas = [{"ix": ix, "iy": iy, "pa": round(rng.uniform(.1, .45), 4),
                      "pb": round(rng.uniform(.1, .45), 4),
                      "d": round(rng.uniform(-.09, .09), 4),
                      "q": round(rng.choice([.004, .03, .2, .6]), 4),
                      "na": rng.randrange(200, 1400), "nb": rng.randrange(200, 1400)}
                     for ix in range(5) for iy in range(4)]
            dpares[f"{a}|{b}"] = {
                "zonas": zonas,
                "tercios": [{"tercio": t, "pi_a": rng.uniform(.15, .4),
                             "pi_b": rng.uniform(.15, .4),
                             "delta": rng.uniform(-.05, .05)}
                            for t in ("propio", "medio", "rival")],
                "pi_a": .28, "pi_b": .26,
                "nivel": {"k0": 3, "pa": .31, "pb": .26, "dif": .05, "q": .012,
                          "na": 8123, "nb": 6740},
                "curva": [{"k": k, "pa": round(.4 - .03 * k, 4),
                           "pb": round(.38 - .04 * k, 4),
                           "la": round(.36 - .03 * k, 4), "ha": round(.44 - .03 * k, 4),
                           "lb": round(.33 - .04 * k, 4), "hb": round(.43 - .04 * k, 4),
                           "na": 900, "nb": 800} for k in range(1, 9)],
                "concede": {"acciones": {"a": 6.12, "b": 6.88, "sig": True},
                            "remate": {"a": .092, "b": .107, "sig": False},
                            "cobertura": .91, "soporte": 15}}

    def cadena():
        """Cadena con estados ENTEROS, como los del parquet real.

        La version anterior de este generador usaba nombres de texto
        ("z13|open") y por eso la prueba de humo pasaba mientras el reporte
        real fallaba: el generador no reproducia el esquema. Es exactamente el
        error de proceso #2 del proyecto —`synth.py` prometia "el ESQUEMA REAL
        de StatsBomb" y llevaba versiones sin `player_id`—, cometido otra vez.
        """
        NZ, NF = 5 * 4, 4
        NT = NZ * NF                       # 80 transitorios
        est = list(range(NT + 4))          # 80..83 absorbentes
        zonas = [[e // NF // 4, e // NF % 4] for e in range(NT)] + [None] * 4
        absv = [0] * NT + [1] * 4
        filas = {}
        for i in range(NT):
            dest = rng.sample(range(NT), 6) + [NT, NT + 1, NT + 2, NT + 3]
            ps = [rng.random() for _ in dest[:6]] + [.02, .10, .20, .55]
            tt = sum(ps)
            filas[i] = [[d, round(v / tt, 5)] for d, v in zip(dest, ps)]
        ini = rng.sample(range(NT), 8)
        h = [0] * 31
        for _ in range(4000):
            h[min(30, max(1, int(rng.gammavariate(2, 3))))] += 1
        # zmat/zvis: el agregado por zona que usa el modo Explorar. Sin esto
        # el humo probaria una forma que el reporte real no produce.
        zmat, zvis = {}, {}
        for z in range(20):
            dst = rng.sample(range(20), 5)
            ps = [round(rng.uniform(.03, .25), 4) for _ in dst]
            sig = round(sum(ps), 4)
            zmat[z] = {"n": rng.randrange(300, 1500),
                       "dest": [[d, v] for d, v in zip(dst, ps)],
                       "fin": {str(NT): round((1 - sig) * .02, 4),
                               str(NT + 1): round((1 - sig) * .12, 4),
                               str(NT + 2): round((1 - sig) * .25, 4),
                               str(NT + 3): round((1 - sig) * .61, 4)},
                       "sigue": sig}
            zvis[z] = round(rng.uniform(.01, .09), 5)
        tv = sum(zvis.values())
        zvis = {k: round(v / tv, 5) for k, v in zvis.items()}
        return {"estados": [str(e) for e in est], "zonas": zonas, "abs": absv,
                "zmat": zmat, "zvis": zvis,
                "fases": ["open", "transition", "restart", "set_piece"],
                "lift": {
                    # REMATE con muestra y con DOS zonas suprimidas a proposito
                    "REMATE": {"n": 773, "bloqueado": False, "min_sop": 10,
                               "soporte": {z: (5 if z in (3, 17) else 120)
                                           for z in range(20)},
                               # z=9,10 imitan el centro del area (~4x, deben
                               # SATURAR); z=1,2 las bandas (~1.9x, deben
                               # distinguirse entre si y del techo)
                               "lift": {z: (None if z in (3, 17)
                                            else 3.98 if z == 9
                                            else 4.10 if z == 10
                                            else 1.96 if z == 1
                                            else 1.30 if z == 2
                                            else round(rng.uniform(.6, 1.8), 3))
                                        for z in range(20)}},
                    # GOL bloqueado: es el caso que debe desactivar la pestaña
                    "GOL": {"n": 22, "bloqueado": True, "minimo": 100}},
                "ztipo": {z: {"sigue": {"Pass": .62, "Carry": .38},
                              "fin": {"Pass": .5, "Carry": .3, "Shot": .2}}
                          for z in range(20)},
                # `resto` = el club SIN este entrenador. Sin esto el humo no
                # probaria el tercer modo y volveriamos a validar de menos.
                "resto": {"zmat": zmat, "n_pos": 5000,
                          "zvis": {k: round(v * rng.uniform(.6, 1.4), 5)
                                   for k, v in zvis.items()}},
                # indexado por VALOR de estado (string), como lo emite el
                # reporte. Con enteros clave int el JS no lo encontraria.
                "fin": {str(NT): "GOL", str(NT + 1): "REMATE",
                        str(NT + 2): "BALON FUERA", str(NT + 3): "PERDIDA"},
                "inicial": [[i, round(1 / len(ini), 5)] for i in ini],
                "filas": filas, "hist": h, "n_pos": 8694, "nx": 5, "ny": 4}

    return {"ref_rivales": {"et": 5.81, "rem": 0.081,
                            "np": 17814, "equipos": 17},
            "cadena": {d: cadena() for d in dts},
            "goal_open": {}, "entrenadores": dts,
            "posesiones": {d: rng.randrange(1600, 12000) for d in dts},
            "pares": pares, "huella": huella, "jugadores": jugadores,
            "defensa": {"pares": dpares,
                        "instrumento": {d: {"efecto": .118, "viejo": .07} for d in dts},
                        "cochran": {}}}


datos = {"clubes": {
    "Club América": club("Club América", ["Andre Jardine", "Santiago Solari",
                                          "Fernando Ortiz"]),
    "Cruz Azul": club("Cruz Azul", ["Martin Anselmi", "Juan Reynoso",
                                    "Ricardo Ferretti"])}}

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent if AQUI.name == "scripts" else AQUI

# node y jsdom son OPCIONALES: esta comprobacion es valiosa, no obligatoria
# para poder trabajar. Si faltan, se dice y se sale con exito.
if shutil.which("node") is None:
    print("node no esta instalado: no se puede renderizar la pagina.")
    print("El HTML se genera igual; instala node para la comprobacion completa.")
    NODE = False
else:
    NODE = True

ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "scripts" / "12_reporte_html.py"
if not ruta.exists():
    sys.exit(f"no encuentro {ruta}")
fuente = ruta.read_text()
html = re.search(r'^HTML = r"""(.*?)"""$', fuente, re.S | re.M).group(1)
salida = RAIZ / "reporte_demo.html"
salida.write_text(
    html.replace("__DATOS__", json.dumps(datos, ensure_ascii=False)), encoding="utf-8")
print(f"{salida.name} escrito ({salida.stat().st_size/1024:.0f} KB) — abrelo para verlo")

if not NODE:
    sys.exit(0)

r = subprocess.run(["node", str(AQUI / "humo_reporte.js")],
                   capture_output=True, text=True, cwd=RAIZ)
print(r.stdout, end="")
if "Cannot find module 'jsdom'" in r.stderr:
    print("\njsdom no esta instalado. Para la comprobacion completa:")
    print(f"    cd '{RAIZ}' && npm install jsdom")
    sys.exit(0)
if r.returncode:
    print(r.stderr, file=sys.stderr)
    sys.exit("LA PAGINA NO SE PINTA")
