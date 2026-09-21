#!/usr/bin/env python3
"""Prueba de humo del informe (H7, ADR-59 y su adenda 2).

1. Genera los siete JSON de `reports/` con datos SINTÉTICOS y la misma forma que
   los reales (15_REPORTE_HTML §9), para las cinco historias, con los casos
   límite: torneo parcial con percentil nulo, intervalos que cruzan el cero,
   contrastes que sí sobreviven en historias sin lectura preinscrita,
   historias sin presión (fuera de los seis clubes de ADR-54), un técnico
   homónimo que NO debe entrar a una historia, predicciones que fallan y
   ningún parquet de transiciones.
2. Corre `12_reporte_html.py` sobre ellos.
3. Renderiza la página en un DOM real (jsdom) con `humo_reporte.js`, recorre
   las cinco historias y los dos modos.
4. Repite sin `contexto_v1.json`: 2.6, 3.4 y el cierre deben mostrar el comando
   que lo genera, y el resto de la página debe pintarse igual.

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
rng = random.Random(20260918)
T = ["A2021", "C2022", "A2022", "C2023", "A2023", "C2024", "A2024", "C2025", "A2025", "C2026"]
ERAS = {  # (club, coach): torneos
    ("América", "Santiago Solari"): T[0:2],
    ("América", "Fernando Ortiz"): T[2:4],
    ("América", "Andre Jardine"): T[4:10],
    ("Atlético San Luis", "Andre Jardine"): T[1:4],
    ("Atlético San Luis", "Gustavo Leal"): T[4:6],
    ("Monterrey", "Fernando Ortiz"): T[4:7],
    ("Monterrey", "Domenec Torrent"): T[7:9],
    ("Atlas", "Diego Cocca I"): T[0:3],
    ("Atlas", "Diego Cocca II"): T[5:8],
    ("Puebla", "Nicolas Larcamon"): T[0:3],
    ("León", "Ariel Holan"): T[2:4],
    ("León", "Nicolas Larcamon"): T[4:6],
    ("León", "Eduardo Berizzo"): T[6:8],
    ("Cruz Azul", "Martin Anselmi"): T[6:8],
    ("Cruz Azul", "Nicolas Larcamon"): T[8:10],
    ("Toluca", "Ignacio Ambriz"): T[1:5],
    ("Toluca", "Renato Paiva"): T[5:8],
    ("Santos Laguna", "Eduardo Fentanes"): T[4:6],
    ("Santos Laguna", "Ignacio Ambriz"): T[6:8],
    ("Tigres UANL", "Miguel Herrera"): T[0:3],
    ("Tigres UANL", "Veljko Paunovic"): T[3:5],
    ("Tijuana", "Miguel Herrera"): T[3:6],
    ("Tijuana", "Juan Carlos Osorio"): T[6:8],
    # homónimo: NO debe entrar a la historia de Herrera (igualdad exacta)
    ("Necaxa", "Hector Herrera"): T[2:4],
}
SLUG = {"América": "america", "Atlético San Luis": "atletico_san_luis", "Monterrey": "monterrey",
        "Atlas": "atlas", "Puebla": "puebla", "León": "leon", "Cruz Azul": "cruz_azul",
        "Toluca": "toluca", "Santos Laguna": "santos_laguna", "Tigres UANL": "tigres_uanl",
        "Tijuana": "tijuana", "Necaxa": "necaxa"}
PRES_CLUBES = ["america", "leon", "atlas", "atletico_san_luis", "monterrey", "cruz_azul"]
VARIOS = ["Andre Jardine", "Fernando Ortiz", "Benat San Jose", "Benjamin Mora",
          "Domenec Torrent", "Nicolas Larcamon", "Veljko Paunovic",
          "Victor Manuel Vucetich", "Eduardo Fentanes", "Ignacio Ambriz", "Miguel Herrera"]
CASOS = {"Andre Jardine": ["América", "Atlético San Luis"], "Fernando Ortiz": ["América", "Monterrey"],
         "Santiago Solari": ["América"], "Nicolas Larcamon": ["Cruz Azul", "León", "Puebla"],
         "Ignacio Ambriz": ["Santos Laguna", "Toluca"], "Miguel Herrera": ["Tigres UANL", "Tijuana"],
         "Veljko Paunovic": ["Tigres UANL"], "Domenec Torrent": ["Monterrey"]}


def ic(c, w):
    return [c - w, c + w]


def U(club, coach, **kw):
    return {"club": club, "coach": coach, "slug": SLUG[club],
            "n_partidos": 17 * len(ERAS[(club, coach)]), **kw}


def signo(club, coach):
    """Perfil sintético: el de ADR-59 para las cuatro eras de §8; variado para el resto."""
    return {("América", "Andre Jardine"): 1, ("Atlético San Luis", "Andre Jardine"): -1,
            ("América", "Fernando Ortiz"): 1, ("Monterrey", "Fernando Ortiz"): 1,
            ("Puebla", "Nicolas Larcamon"): -1, ("Tijuana", "Miguel Herrera"): -1,
            ("Santos Laguna", "Ignacio Ambriz"): 0}.get((club, coach), 1)


# ---------------------------------------------------------------- did_h4 ----
def h4():
    uni = []
    for (club, coach), ts in ERAS.items():
        s = signo(club, coach)
        c = {1: .2, -1: -.1, 0: .01}[s]
        w = .02 if s else .03   # s = 0: el intervalo cruza el cero
        uni.append({"club": club, "coach": coach, "indir": f"data/processed_api_{SLUG[club]}",
                    "E_T": 5.6 * (1 + c), "E_T_base": 5.6, "replicas_validas": 4000,
                    "rel_E_T_vs_liga": c, "rel_E_T_vs_liga_ic95": ic(c, w), "torneos": ts,
                    "serie_por_torneo": {
                        t: {"n_poss": rng.randrange(900, 1800),
                            # un torneo POR DEBAJO de la liga: la frase cambia sola
                            "rel_E_T": -0.02 if (coach == "Andre Jardine" and t == ts[1]) else c + rng.uniform(-.08, .08)}
                        for t in ts}})

    def et(rel, w, q, r):
        return {"rel": rel, "ic95": ic(rel, w), "p": q / 2, "q": q, "rechaza_fdr": r}

    def P(club, a, b, did, cru):
        return {"club": club, "a": a, "b": b, "did": {"E_T": did}, "crudo": {"E_T": cru},
                "cambia_signo_por_correccion": (did["rel"] > 0) != (cru["rel"] > 0)}

    pares = [
        P("América", "Andre Jardine", "Fernando Ortiz", et(.035, .034, .056, False), et(.05, .03, .02, True)),
        P("América", "Andre Jardine", "Santiago Solari", et(.176, .05, .001, True), et(.31, .05, .001, True)),
        P("América", "Fernando Ortiz", "Santiago Solari", et(.136, .05, .001, True), et(.2, .05, .001, True)),
        P("Atlas", "Diego Cocca I", "Diego Cocca II", et(.049, .045, .039, True), et(-.07, .04, .002, True)),
        P("Atlético San Luis", "Andre Jardine", "Gustavo Leal", et(-.25, .04, .001, True), et(-.2, .04, .001, True)),
        P("Monterrey", "Fernando Ortiz", "Domenec Torrent", et(.01, .03, .7, False), et(.05, .03, .1, False)),
        P("León", "Ariel Holan", "Nicolas Larcamon", et(.109, .046, .001, True), et(.041, .04, .05, False)),
        P("León", "Eduardo Berizzo", "Nicolas Larcamon", et(-.07, .038, .001, True), et(-.02, .04, .4, False)),
        P("Cruz Azul", "Martin Anselmi", "Nicolas Larcamon", et(.218, .045, .001, True), et(.1, .04, .01, True)),
        P("Toluca", "Ignacio Ambriz", "Renato Paiva", et(.02, .03, .5, False), et(.06, .03, .05, True)),
        P("Santos Laguna", "Eduardo Fentanes", "Ignacio Ambriz", et(-.2, .04, .001, True), et(-.15, .04, .001, True)),
        P("Tigres UANL", "Miguel Herrera", "Veljko Paunovic", et(.171, .045, .001, True), et(.1, .04, .01, True)),
        P("Tijuana", "Juan Carlos Osorio", "Miguel Herrera", et(.369, .053, .001, True), et(.3, .05, .001, True)),
    ]
    return {"parametros": {"torneos_orden": T},
            "reglas_preinscritas": {"D53-1": "familia nueva: theta(E_T) de todos los pares intra-club, BH 5%",
                                    "D53-3": "el crudo (mismo estimando, sin normalizar) es comparacion, no hallazgo",
                                    "D53-7": "serie por torneo descriptiva"},
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
        {"club": "América", "a": "Fernando Ortiz", "b": "Santiago Solari",
         "contrastes": {"E2": c(.052, .032, .041, True), "E4": c(-.04, .08, .5, False)}},
        {"club": "Atlético San Luis", "a": "Andre Jardine", "b": "Gustavo Leal",
         "contrastes": {"E2": c(.005, .025, .8, False), "E4": c(-.02, .03, .6, False)}},
        {"club": "León", "a": "Ariel Holan", "b": "Nicolas Larcamon",
         "contrastes": {"E2": c(-.015, .041, .7, False), "E4": c(.01, .03, .7, False)}},
        # sobrevive en una historia sin lectura preinscrita: la plantilla dice "difiere"
        {"club": "Cruz Azul", "a": "Martin Anselmi", "b": "Nicolas Larcamon",
         "contrastes": {"E2": c(-.077, .03, .011, True), "E4": c(.02, .02, .3, False)}},
        {"club": "Monterrey", "a": "Fernando Ortiz", "b": "Domenec Torrent",
         "contrastes": {"E2": c(.01, .03, .7, False), "E4": c(.01, .03, .7, False)}},
    ]
    return {"parametros": {"clubes": PRES_CLUBES},
            "reglas_preinscritas": {"D54-1": "familia nueva: E1-E5 de las parejas de ADR-52, BH 5%",
                                    "D54-3": "magnitudes en pp con pi crudo; logit como sensibilidad"},
            "n_rechaza_crudo": 24, "n_rechaza_did": 6, "n_cambian_veredicto": 20,
            "m_etapa1": 135, "pares": pares,
            "unidades": [{"club": c_, "coach": co} for (c_, co) in ERAS if SLUG[c_] in PRES_CLUBES],
            "predicciones": [{"n": i, "texto": f"predicción sintética {i}", "cumple": i % 2 == 0}
                             for i in (1, 2, 3, 4)]}


# ------------------------------------------------------------ balon_parado --
def bp():
    zon = lambda: {k: {"n": rng.randrange(0, 130), "xg": rng.uniform(0, 11)}  # noqa: E731
                   for k in ("area_chica", "area_central", "area_lateral", "fuera_del_area")}
    uni = []
    for (club, coach) in ERAS:
        rech = (club, coach) == ("Toluca", "Ignacio Ambriz")
        uni.append(U(club, coach,
                     corners_por_partido_of=rng.uniform(4, 6), corners_por_partido_def=rng.uniform(4, 6),
                     remates_of=rng.randrange(80, 250), remates_def=rng.randrange(80, 250),
                     C1_of={"did": .07 if rech else .003, "ic95": [.03, .11] if rech else [-.041, .046],
                            "q_casos": .01 if rech else .6, "rechaza_casos": rech,
                            **({"q": .8, "rechaza": False} if club == "América" else {})},
                     C1_def={"did": -.026, "ic95": [-.068, .018], "q_casos": .5, "rechaza_casos": False,
                             **({"q": .8, "rechaza": False} if club == "América" else {})},
                     descriptivos={"mapa_remates_of": zon(),
                                   "mapa_remates_def": {**zon(), "area_chica": {"n": 0, "xg": 0.0}}}))
    return {"liga": {"P_S_secuencia": {"corner": .396, "tiro_libre": .209, "banda": .14},
                     "P_G_secuencia": {"corner": .033, "tiro_libre": .02, "banda": .011},
                     "goal_open_medio": {"corner": .66, "juego_abierto": .78}},
            "modelo": {"delta_auc": .026, "delta_auc_ic95_percentil": [.015, .038],
                       "beta_base_estandarizado": {"dist_meta": -.58, "angulo": .54, "cabeza": -.44},
                       "beta_base_ic95": {"dist_meta": [-.7, -.46], "angulo": [.42, .66],
                                          "cabeza": [-.5, .02]}},
            "reglas": {"D55-1": "C1 = P(S|secuencia), empirica", "D55-6": "comparacion contra la liga sin el club"},
            "familia_casos": {"m": 96, "casos": CASOS},
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
    for (club, coach) in ERAS:
        con, tasas = {}, {}
        for c in CTX:
            for m in ("M1", "M2", "M3", "M4"):
                t = rng.uniform(-.03, .03) if m != "M1" else rng.uniform(-.4, .4)
                w = abs(t) * (0.6 if (c, m) == ("marcador", "M4") else 1.4) + .005
                # un contraste que sobrevive en una historia sin lectura preinscrita
                r = (club, coach, c, m) == ("Tigres UANL", "Veljko Paunovic", "rival", "M2")
                con[f"{c}|{m}"] = {"theta": t, "ic95": ic(t, w), "p": .3,
                                   "q_casos": .01 if r else .5, "rechaza_casos": r}
        tasas["marcador|M1|perdiendo"], tasas["marcador|M1|ganando"] = rng.uniform(5, 7), rng.uniform(4, 6)
        uni.append(U(club, coach, contrastes=con, tasas=tasas))
    viaja = {c: (i % 3 == 0) for i, c in enumerate(VARIOS)}
    k = sum(viaja.values())
    return {"liga": liga, "unidades": uni, "viaja_marcador_M1": viaja, "casos": CASOS,
            "reglas": {"D56": "theta = ajuste de la unidad menos ajuste de la liga",
                       "D56-bootstrap": "por partido", "D57-1": "casos", "D57-2": "familia casos separada, BH 5%"},
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
        rech = (club, coach) == ("Puebla", "Nicolas Larcamon")
        C = {"M2": {"theta": .02, "ic95": [-.07, .1], "q_casos": .6, "rechaza_casos": False},
             "FT": {"theta": .12 if rech else .02, "ic95": [.05, .19] if rech else [-.07, .1],
                    "q_casos": .02 if rech else .6, "rechaza_casos": rech}}
        uni.append(U(club, coach, A=A, B=B, C=C))
    return {"liga": {"Tactical": {"M2": {"perdiendo": [.0215, 448]},
                                  "FT": {"perdiendo": [.0868, 449]}}},
            "reglas": {"D58-A": "nucleo y rotacion descriptivos", "D58-B": "roles descriptivos",
                       "D58-C": "primer cambio tactico", "D58-familias": "casos, BH 5%"},
            "unidades": uni,
            "predicciones": [{"n": i, "texto": f"jug {i}", "cumple": True} for i in range(1, 5)]}


# --------------------------------------------------------------- metricas ---
def met():
    uni = []
    for (club, coach), ts in ERAS.items():
        s = signo(club, coach)

        def M_(d, w, liga=1.15):
            return {"era": liga + d, "liga": liga, "dif": d, "ic95": [d - w, d + w]}
        g = {k: M_(s * d if s else d / 10, w) for k, d, w in
             (("npxg_favor", .3, .17), ("prog_pases", 3.7, 1.8), ("obv_favor", .43, .25))}
        g["npxg_contra"] = M_(-.32 if s >= 0 else .1, .1)
        g["field_tilt"] = M_(s * .11 if s else .004, .03, liga=.5)
        if club == "Monterrey":
            g["npxg_favor"] = M_(-.04, .185)
            g["field_tilt"] = M_(.038, .045, liga=.5)
        pt = {t: {"parcial": (t == ts[-1] and coach == "Andre Jardine" and club == "América"),
                  "field_tilt": {"percentil": rng.uniform(.8, 1)},
                  "npxg_favor": {"percentil": rng.uniform(0, 1)}} for t in ts}
        for v in pt.values():   # el último torneo de Jardine, PARCIAL: sin percentil
            if v["parcial"]:
                v["field_tilt"]["percentil"] = None
                v["npxg_favor"]["percentil"] = None
        uni.append(U(club, coach, **{"global": g, "por_torneo": pt}))
    return {"liga": {"media": {"npxg_favor": 1.149}}, "parametros": {"torneos": T},
            "reglas": {"D59P-1": "xG sin penales", "D59P-3": "pase progresivo", "D59P-5": "field tilt",
                       "D59P-comparacion": "liga sin partidos del club", "D59P-incertidumbre": "bootstrap"},
            "casos": {k: v for k, v in CASOS.items()}, "unidades": uni}


def der():
    return {"por_torneo": [{"torneo": t, "torneo_orden": 4043 + i, "clubes": 18,
                            "acc_por_posesion_cruda_media": 7 + i * .15,
                            "acc_por_posesion_cruda_sd_clubes": .7} for i, t in enumerate(T)]}


# --------------------------------------------------------------- relevos ---
def rel():
    """relevos_v1 (ADR-60) con la forma de 42_relevos.py y sus casos límite:
    una pareja que rechaza, una sin uso estimable, una inestable al umbral y
    una predicción no evaluable."""
    ordenes = {k: min(T.index(t) for t in ts) for k, ts in ERAS.items()}
    pares = []
    for p in h4()["pares"]:
        c, a, b = p["club"], p["a"], p["b"]
        if ordenes[(c, a)] > ordenes[(c, b)]:
            a, b = b, a
        k = len(pares)
        Tv = .02 + .03 * (k % 4)
        estimable = (c, a, b) != ("Santos Laguna", "Eduardo Fentanes", "Ignacio Ambriz")
        phi = .3 + .1 * (k % 5)
        estable = (c, b) != ("Tijuana", "Juan Carlos Osorio")
        um = {str(u): {"compartidos": (0 if not estimable else 6 + k % 5), "U": Tv * phi, "C": Tv * (1 - phi),
                       "phi_U": (None if not estimable else
                                 min(1, phi + (0 if u == 200 or estable else (.2 if u == 100 else -.2))))}
              for u in (100, 200, 400)}
        d = [rng.uniform(-.02, .02) for _ in range(20)]
        u_ = [x * phi for x in d]
        pares.append({"club": c, "a": a, "b": b, "T": Tv, "p": .001 if k % 3 == 0 else .4,
                      "q": .01 if k % 3 == 0 else .6, "rechaza": k % 3 == 0, "T_nula_p95": .03,
                      "ic95": {"T": [Tv * .7, Tv * 1.4], "U": [0, Tv], "C": [0, Tv],
                               "phi_U": [max(0, phi - .15), min(1, phi + .15)] if estimable else None},
                      "umbrales": um, "estimable": estimable, "estable": estimable and estable,
                      "mapas": {"delta": d, "U": u_, "C": [x - y for x, y in zip(d, u_)]},
                      "n_partidos_a": 34, "n_partidos_b": 34, "js_Q_crudo": .05})
    return {"adr": "ADR-60", "parametros": {"umbral": 200, "umbrales_sensibilidad": [100, 400],
                                            "estable_si_dif_menor_a": .1},
            "reglas": {"D60-1": "T = ½‖Δ‖₁ en exceso de la liga del mismo torneo",
                       "D60-2": "nula por permutación de partidos", "D60-3": "punto medio",
                       "D60-4": "compartido = al menos 200 acciones", "D60-5": "familia F60, BH 5%"},
            "pares": pares, "control_negativo": {"p": .5},
            "predicciones": [{"n": i, "texto": f"rel {i}", "cumple": (None if i == 5 else i != 2)}
                             for i in range(1, 7)]}


# --------------------------------------------------------------- estilos ---
def est():
    eras = [{"club": c, "coach": co, "PC1": rng.uniform(-3, 3), "PC2": rng.uniform(-2, 2),
             "n_partidos": 17 * len(ts)} for (c, co), ts in ERAS.items()]
    pos = {(e["club"], e["coach"]): e for e in eras}
    rel_ = [{"club": p["club"], "a": p["a"], "b": p["b"], "distancia": 1.5, "percentil": .3}
            for p in h4()["pares"]]
    tras = []
    for co in ("Andre Jardine", "Nicolas Larcamon", "Ignacio Ambriz", "Miguel Herrera", "Fernando Ortiz"):
        cl = sorted(c for (c, x) in ERAS if x == co)
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                tras.append({"coach": co, "club_a": cl[i], "club_b": cl[j], "distancia": 2.2, "percentil": .45})
    del pos
    return {"ejes": {"PC1": "dominio con balón", "PC2": "rotación", "varianza": [.47, .2]},
            "metricas": ["posesion", "field_tilt"], "cargas": {}, "eras": eras,
            "distancias_todas": {"n": 1378, "mediana": 2.88, "p10": 1.08, "p90": 5.39},
            "relevos": rel_, "traslados": tras}


SINTETICOS = {"did_h4_v1.json": h4, "did_presion_v1.json": pres,
              "balon_parado_v2.json": bp, "contexto_v1.json": ctx,
              "jugadores_v1.json": jug, "metricas_v1.json": met,
              "deriva_proveedor.json": der, "relevos_v1.json": rel, "estilos_v1.json": est}


def escribe_sinteticos(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for nombre, fn in SINTETICOS.items():
        (d / nombre).write_text(json.dumps(fn(), ensure_ascii=False), encoding="utf-8")


def corre(gen: Path, rep: Path, out: Path) -> None:
    r = subprocess.run([sys.executable, str(gen), "--reports", str(rep),
                        "--datos", str(rep / "sin_datos"), "--out", str(out)],
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

        print("== sin relevos_v1.json")
        (rep / "relevos_v1.json").rename(rep / "relevos_v1.aparte")
        out3 = Path(tmp) / "sin_rel.html"
        corre(gen, rep, out3)
        ok &= dom(out3, "sin_relevos")
        (rep / "relevos_v1.aparte").rename(rep / "relevos_v1.json")

        print("== sin contexto_v1.json")
        (rep / "contexto_v1.json").unlink()
        out2 = Path(tmp) / "sin_ctx.html"
        corre(gen, rep, out2)
        ok &= dom(out2, "sin_contexto")
    print(f"\ndemo: {Path(a.deja).resolve()}")
    sys.exit(0 if ok else "HUMO EN ROJO")


if __name__ == "__main__":
    main()
