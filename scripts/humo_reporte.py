#!/usr/bin/env python3
"""Prueba de humo del informe (H7, ADR-59).

1. Genera los siete JSON de `reports/` con datos SINTÉTICOS y la misma forma que
   los reales (15_REPORTE_HTML §9), con los casos límite: torneo parcial con
   percentil nulo, intervalos que cruzan el cero, predicciones que fallan, sin
   parquet de transiciones.
2. Corre `12_reporte_html.py` sobre ellos.
3. Renderiza la página en un DOM real (jsdom) con `humo_reporte.js`.
4. Repite sin `contexto_v1.json`: la sección 05 debe mostrar el comando que lo
   genera, y el resto de la página debe pintarse igual.

No valida números: valida que la página se pinta y cumple el contrato.

Uso:  python scripts/humo_reporte.py [--deja reporte_demo.html]
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
rng = random.Random(20260917)
TORNEOS = ["A2021", "C2022", "A2022", "C2023", "A2023", "C2024", "A2024", "C2025", "A2025", "C2026"]
ERAS = {  # (club, coach): torneos
    ("América", "Andre Jardine"): TORNEOS[4:],
    ("América", "Fernando Ortiz"): TORNEOS[1:4],
    ("América", "Santiago Solari"): TORNEOS[:2],
    ("Atlético San Luis", "Andre Jardine"): TORNEOS[1:4],
    ("Monterrey", "Fernando Ortiz"): TORNEOS[4:7],
    ("Atlas", "Diego Cocca I"): TORNEOS[:3],
    ("Atlas", "Diego Cocca II"): TORNEOS[5:8],
}
VARIOS = ["Andre Jardine", "Fernando Ortiz", "Benat San Jose", "Benjamin Mora",
          "Domenec Torrent", "Nicolas Larcamon", "Veljko Paunovic",
          "Victor Manuel Vucetich", "Eduardo Fentanes", "Ignacio Ambriz", "Miguel Herrera"]


def ic(c, w):
    return [c - w, c + w]


def U(club, coach, **kw):
    return {"club": club, "coach": coach, **kw}


# ---------------------------------------------------------------- did_h4 ----
def h4():
    uni = []
    for (club, coach), ts in ERAS.items():
        c = {"Andre Jardine": .25 if club == "América" else -.10,
             "Fernando Ortiz": .20 if club == "América" else .16}.get(coach, .05)
        uni.append(U(club, coach, rel_E_T_vs_liga=c, rel_E_T_vs_liga_ic95=ic(c, .02),
                     torneos=ts, serie_por_torneo={
                         t: {"n_poss": rng.randrange(900, 1800),
                             # un torneo POR DEBAJO de la liga: la frase cambia sola
                             "rel_E_T": -0.02 if (coach == "Andre Jardine" and t == ts[1]) else c + rng.uniform(-.08, .08)}
                         for t in ts}))

    def et(rel, w, q, r):
        return {"rel": rel, "ic95": ic(rel, w), "p": q / 2, "q": q, "rechaza_fdr": r}

    pares = [
        {"club": "América", "a": "Andre Jardine", "b": "Fernando Ortiz",
         "did": {"E_T": et(.035, .034, .056, False)}, "crudo": {"E_T": et(.05, .03, .02, True)}},
        {"club": "América", "a": "Andre Jardine", "b": "Santiago Solari",
         "did": {"E_T": et(.176, .05, .001, True)}, "crudo": {"E_T": et(.31, .05, .001, True)}},
        {"club": "América", "a": "Fernando Ortiz", "b": "Santiago Solari",
         "did": {"E_T": et(.136, .05, .001, True)}, "crudo": {"E_T": et(.2, .05, .001, True)}},
        {"club": "Atlas", "a": "Diego Cocca I", "b": "Diego Cocca II",
         "did": {"E_T": et(.049, .045, .039, True)}, "crudo": {"E_T": et(-.07, .04, .002, True)}},
    ]
    return {"parametros": {"torneos_orden": TORNEOS},
            "firma_temporal": {"did": {"posterior_mas_largo": 23, "de": 44},
                               "crudo": {"posterior_mas_largo": 37, "de": 47}},
            "n_pares": 60, "n_rechazados_did": 44, "n_rechazados_crudo": 47,
            "n_cambian_signo_por_correccion": 15,
            "control_negativo": {"n_equivalentes": 0}, "unidades": uni, "pares": pares}


# ------------------------------------------------------------ did_presion ---
def pres():
    def c(t, w, q, r):
        return {"did": {"theta": t, "ic95": ic(t, w), "p": q / 3, "q": q, "rechaza": r}}
    pares = [
        {"club": "América", "a": "Andre Jardine", "b": "Fernando Ortiz",
         "contrastes": {"E2": c(-.02, .022, .38, False), "E4": c(.06, .07, .33, False)}},
        {"club": "América", "a": "Andre Jardine", "b": "Santiago Solari",
         "contrastes": {"E2": c(.033, .029, .30, False), "E4": c(.10, .07, .2, False)}},
        # orden invertido a propósito: el generador debe voltear el signo
        {"club": "América", "a": "Santiago Solari", "b": "Fernando Ortiz",
         "contrastes": {"E2": c(-.052, .032, .041, True), "E4": c(-.04, .08, .5, False)}},
    ]
    return {"n_rechaza_crudo": 24, "n_rechaza_did": 6, "n_cambian_veredicto": 20,
            "m_etapa1": 135, "pares": pares,
            "predicciones": [{"n": i, "texto": f"predicción sintética {i}", "cumple": i % 2 == 0}
                             for i in (1, 2, 3, 4)]}


# ------------------------------------------------------------ balon_parado --
def bp():
    zon = lambda: {k: {"n": rng.randrange(0, 130), "xg": rng.uniform(0, 11)}  # noqa: E731
                   for k in ("area_chica", "area_central", "area_lateral", "fuera_del_area")}
    uni = [U("América", "Andre Jardine",
             C1_of={"did": .003, "ic95": [-.041, .046], "rechaza": False, "rechaza_casos": False},
             C1_def={"did": -.026, "ic95": [-.068, .018], "rechaza": False, "rechaza_casos": False},
             descriptivos={"mapa_remates_of": zon(),
                           "mapa_remates_def": {**zon(), "area_chica": {"n": 0, "xg": 0.0}}})]
    return {"liga": {"P_S_secuencia": {"corner": .396, "tiro_libre": .209, "banda": .14},
                     "P_G_secuencia": {"corner": .033, "tiro_libre": .02, "banda": .011},
                     "goal_open_medio": {"corner": .66, "juego_abierto": .78}},
            "modelo": {"delta_auc": .026, "delta_auc_ic95_percentil": [.015, .038],
                       "beta_base_estandarizado": {"dist_meta": -.58, "angulo": .54, "cabeza": -.44},
                       "beta_base_ic95": {"dist_meta": [-.7, -.46], "angulo": [.42, .66],
                                          "cabeza": [-.5, .02]}},
            "unidades": uni,
            "predicciones": [{"n": i, "texto": f"bp {i}", "cumple": i != 2} for i in range(1, 8)]}


# --------------------------------------------------------------- contexto ---
CTX = {"localia": ("local", "visitante"), "marcador": ("perdiendo", "ganando"),
       "momento": ("min>=60", "min<60"), "rival": ("fuerte", "debil")}


def ctx():
    liga = {c: {m: {a: rng.uniform(5, 6) if m == "M1" else rng.uniform(.1, .23),
                    b: rng.uniform(5, 6) if m == "M1" else rng.uniform(.1, .23), "otro": 0.0}
                for m in ("M1", "M2", "M3", "M4")} for c, (a, b) in CTX.items()}
    uni = []
    for coach in ("Andre Jardine", "Fernando Ortiz", "Santiago Solari"):
        con = {}
        for c in CTX:
            for m in ("M1", "M2", "M3", "M4"):
                t = rng.uniform(-.03, .03) if m != "M1" else rng.uniform(-.4, .4)
                w = abs(t) * (0.6 if (c, m) == ("marcador", "M4") else 1.4) + .005
                con[f"{c}|{m}"] = {"theta": t, "ic95": ic(t, w), "p": .3,
                                   "q_casos": .5, "rechaza_casos": False}
        uni.append(U("América", coach, contrastes=con))
    viaja = {c: (i % 3 == 0) for i, c in enumerate(VARIOS)}
    k = sum(v for c, v in viaja.items())
    return {"liga": liga, "unidades": uni, "viaja_marcador_M1": viaja,
            "predicciones": [{"adr": 56, "n": i, "texto": f"ctx {i}", "valor": [1, 2],
                              "cumple": i != 6} for i in range(1, 7)] +
                            [{"adr": 57, "n": 1, "texto": "al menos 6 de 9", "valor": [k, len(viaja)],
                              "cumple": False}]}


# -------------------------------------------------------------- jugadores ---
def jug():
    uni = []
    for (club, coach), ts in ERAS.items():
        A = {}
        for i, t in enumerate(ts):
            parcial = (coach == "Fernando Ortiz" and club == "América" and i == 0)
            A[t] = {"n80": rng.randrange(13, 17), "continuidad": rng.uniform(.5, .8),
                    "jugadores_distintos": rng.randrange(24, 33), "partidos": 17,
                    "parcial": parcial,
                    "percentil_continuidad": None if parcial else (
                        rng.uniform(0, .15) if (club, coach) == ("América", "Andre Jardine")
                        else rng.uniform(.3, 1)),
                    "percentil_n80": None if parcial else rng.uniform(0, 1)}
        B = [{"player_id": 1000 + k, "minutos": rng.uniform(450, 8000),
              "posicion_modal": rng.choice(["Goalkeeper", "Right Back", "Center Forward"]),
              "acciones": rng.randrange(300, 7000),
              "zonas": [round(v, 4) for v in
                        (lambda xs: [x / sum(xs) for x in xs])([rng.random() ** 3 for _ in range(20)])]}
             for k in range(7)]
        C = {m: {"theta": .02, "ic95": [-.07, .1], "rechaza_casos": False} for m in ("M2", "FT")}
        uni.append(U(club, coach, A=A, B=B, C=C))
    return {"liga": {"Tactical": {"M2": {"perdiendo": [.0215, 448]},
                                  "FT": {"perdiendo": [.0868, 449]}}},
            "unidades": uni,
            "predicciones": [{"n": i, "texto": f"jug {i}", "cumple": True} for i in range(1, 5)]}


# --------------------------------------------------------------- metricas ---
def met():
    uni = []
    for (club, coach), ts in ERAS.items():
        s = 1 if club == "América" else -1
        g = {k: {"dif": s * d, "ic95": [s * d - w, s * d + w]} for k, d, w in
             (("npxg_favor", .3, .17), ("npxg_contra", -.32, .1), ("prog_pases", 3.7, 1.8),
              ("obv_favor", .43, .25), ("field_tilt", .11, .03))}
        if club == "Monterrey":
            g["npxg_favor"] = {"dif": -.04, "ic95": [-.22, .15]}
            g["field_tilt"] = {"dif": .038, "ic95": [-.008, .082]}
            g["prog_pases"] = {"dif": 6.6, "ic95": [3.2, 10]}
        if club == "Monterrey" or (club == "América" and coach == "Fernando Ortiz"):
            h = g["npxg_contra"]
            g["npxg_contra"] = {"dif": -abs(h["dif"]), "ic95": sorted([-abs(x) for x in h["ic95"]])}
        pt = {t: {"parcial": (t == ts[-1] and coach == "Andre Jardine" and club == "América"),
                  "field_tilt": {"percentil": rng.uniform(.8, 1)},
                  "npxg_favor": {"percentil": rng.uniform(0, 1)}} for t in ts}
        # el último torneo de Jardine, PARCIAL: sin percentil
        for t, v in pt.items():
            if v["parcial"]:
                v["field_tilt"]["percentil"] = None
                v["npxg_favor"]["percentil"] = None
        uni.append(U(club, coach, **{"global": g, "por_torneo": pt}))
    return {"liga": {"media": {"npxg_favor": 1.149}}, "unidades": uni}


def der():
    return {"por_torneo": [{"torneo": t, "torneo_orden": 4043 + i, "clubes": 18,
                            "acc_por_posesion_cruda_media": 7 + i * .15,
                            "acc_por_posesion_cruda_sd_clubes": .7} for i, t in enumerate(TORNEOS)]}


SINTETICOS = {"did_h4_v1.json": h4, "did_presion_v1.json": pres,
              "balon_parado_v2.json": bp, "contexto_v1.json": ctx,
              "jugadores_v1.json": jug, "metricas_v1.json": met,
              "deriva_proveedor.json": der}


def escribe_sinteticos(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for nombre, fn in SINTETICOS.items():
        (d / nombre).write_text(json.dumps(fn(), ensure_ascii=False), encoding="utf-8")


def corre(gen: Path, rep: Path, out: Path) -> None:
    r = subprocess.run([sys.executable, str(gen), "--reports", str(rep),
                        "--parquet", str(rep / "no_existe.parquet"), "--out", str(out)],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        print(r.stderr)
        sys.exit("el generador falló sobre los datos sintéticos")


def dom(html: Path, modo: str) -> bool:
    if shutil.which("node") is None:
        print("node no está instalado: me salto el DOM")
        return True
    r = subprocess.run(["node", str(AQUI / "humo_reporte.js"), str(html), modo],
                       capture_output=True, text=True, cwd=RAIZ)
    print(r.stdout.strip())
    if "Cannot find module 'jsdom'" in r.stderr:
        print("jsdom no está instalado (npm install jsdom): me salto el DOM")
        return True
    if r.returncode:
        print(r.stderr[-2000:])
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gen", nargs="?", default=str(AQUI / "12_reporte_html.py"))
    ap.add_argument("--deja", default="reporte_demo.html")
    a = ap.parse_args()
    gen = Path(a.gen)
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        rep = Path(tmp) / "reports"
        escribe_sinteticos(rep)
        out = Path(tmp) / "completo.html"
        print("== completo")
        corre(gen, rep, out)
        ok &= dom(out, "completo")
        shutil.copy(out, a.deja)

        print("== sin contexto_v1.json")
        (rep / "contexto_v1.json").unlink()
        out2 = Path(tmp) / "sin_ctx.html"
        corre(gen, rep, out2)
        ok &= dom(out2, "sin_contexto")
    print(f"\ndemo: {Path(a.deja).resolve()}")
    sys.exit(0 if ok else "HUMO EN ROJO")


if __name__ == "__main__":
    main()
