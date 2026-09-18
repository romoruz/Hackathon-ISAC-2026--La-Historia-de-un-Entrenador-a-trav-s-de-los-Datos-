#!/usr/bin/env python3
"""
41_barrido_eras.py — barrido de TODAS las eras, TODOS los relevos y TODOS los
traslados de club, para elegir el elenco del informe con datos y no a ojo.

No decide nada ni escribe en el informe: solo lee `reports/*.json` y deja tres
CSV y un resumen en pantalla.

  reports/barrido/eras.csv       una fila por era (club, entrenador)
  reports/barrido/relevos.csv    una fila por par intra-club, era_a = saliente, era_b = entrante
                                 (todo delta es entrante menos saliente)
  reports/barrido/traslados.csv  una fila por par del mismo técnico en clubes distintos

Qué mide, y qué NO mide
-----------------------
Mide DIRECCIÓN y TAMAÑO del cambio en cantidades medidas contra la liga del
mismo torneo: duración de posesión, field tilt, npxG a favor y en contra,
pases progresivos, OBV, rotación y juego por banda. "Sube" o "baja" es
descriptivo; este script NO dice "mejoró" ni mide rendimiento (ADR-59 §3).

Con --puntos intenta además calcular puntos por partido de cada era desde
`data/raw_api/matches/*.json.gz`. Eso es SOLO contexto para elegir el elenco;
no entra al informe. Si el esquema no trae marcador, lo dice y sigue.

Uso:
    source .venv/bin/activate
    python scripts/41_barrido_eras.py
    python scripts/41_barrido_eras.py --puntos      # añade puntos por partido
    python scripts/41_barrido_eras.py --top 25      # cuántas filas imprime
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPORTS = RAIZ / "reports"
SALIDA = REPORTS / "barrido"
NX, NY = 5, 4

# métricas del vector de perfil: (clave, etiqueta, de dónde sale)
MET = [
    ("posesion", "duración de posesión vs liga"),
    ("field_tilt", "field tilt vs liga"),
    ("npxg_favor", "npxG a favor vs liga"),
    ("npxg_contra", "npxG concedido vs liga"),
    ("prog_pases", "pases progresivos vs liga"),
    ("obv_favor", "OBV a favor vs liga"),
    ("continuidad", "percentil de continuidad del once"),
    ("n80", "percentil de N80"),
    ("banda", "fracción de acciones por banda en campo medio y rival"),
]


def carga(nombre):
    p = REPORTS / nombre
    if not p.exists():
        raise SystemExit(f"falta {p}. Corre antes el script que lo genera.")
    return json.loads(p.read_text(encoding="utf-8"))


def banda_era(u_jug) -> float | None:
    """Acciones en los pasillos exteriores (iy 0 y 3) del campo medio y rival
    (ix >= 2), ponderadas por acciones de cada jugador. Descriptivo."""
    num = den = 0.0
    for p in u_jug.get("B", []):
        z = [p["zonas"][i * NY:(i + 1) * NY] for i in range(NX)]
        tot = sum(sum(f) for f in z)
        if not tot:
            continue
        w = p["acciones"]
        num += w * sum(z[ix][iy] for ix in range(2, NX) for iy in (0, NY - 1)) / tot
        den += w
    return num / den if den else None


def percentiles_medios(u_jug):
    A = [v for v in u_jug.get("A", {}).values() if not v.get("parcial")]
    if not A:
        return None, None, 0
    cont = [a["percentil_continuidad"] for a in A if a["percentil_continuidad"] is not None]
    n80 = [a["percentil_n80"] for a in A if a["percentil_n80"] is not None]
    return (st.mean(cont) if cont else None, st.mean(n80) if n80 else None, len(A))


def perfil_eras(h4, met, jug):
    """Vector de perfil por era. Devuelve {(club, coach): dict}."""
    H = {(u["club"], u["coach"]): u for u in h4["unidades"]}
    M = {(u["club"], u["coach"]): u for u in met["unidades"]}
    J = {(u["club"], u["coach"]): u for u in jug["unidades"]}
    out, saltadas = {}, []
    for k in sorted(set(H) | set(M) | set(J)):
        if k not in H or k not in M or k not in J:
            saltadas.append((k, [n for n, d in (("did_h4", H), ("metricas", M), ("jugadores", J))
                                 if k not in d]))
            continue
        g = M[k]["global"]
        cont, n80, n_tor = percentiles_medios(J[k])
        out[k] = {
            "club": k[0], "coach": k[1],
            "n_partidos": J[k].get("n_partidos"),
            "torneos": len(H[k].get("torneos", [])),
            "torneos_completos": n_tor,
            "posesion": H[k]["rel_E_T_vs_liga"],
            "posesion_ic_lo": H[k]["rel_E_T_vs_liga_ic95"][0],
            "posesion_ic_hi": H[k]["rel_E_T_vs_liga_ic95"][1],
            **{m: g[m]["dif"] for m in ("field_tilt", "npxg_favor", "npxg_contra",
                                        "prog_pases", "obv_favor")},
            **{f"{m}_ic_lo": g[m]["ic95"][0] for m in ("field_tilt", "npxg_favor",
                                                       "npxg_contra", "prog_pases", "obv_favor")},
            **{f"{m}_ic_hi": g[m]["ic95"][1] for m in ("field_tilt", "npxg_favor",
                                                       "npxg_contra", "prog_pases", "obv_favor")},
            "continuidad": cont, "n80": n80, "banda": banda_era(J[k]),
        }
    return out, saltadas


def pca(filas, claves):
    """PCA sin dependencias: estandariza y hace SVD a mano con numpy si está,
    y si no, con eigen de la covarianza por el método de Jacobi de numpy.
    Devuelve (coords, varianza explicada, cargas)."""
    import numpy as np
    X = np.array([[f[c] for c in claves] for f in filas], dtype=float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    U, S, Vt = np.linalg.svd(Z - Z.mean(0), full_matrices=False)
    var = (S ** 2) / float((S ** 2).sum())
    # signo fijo: PC1 con carga negativa en field tilt => "izquierda = más dominio"
    for i in range(min(2, len(S))):
        if Vt[i, claves.index("field_tilt")] > 0:
            Vt[i] *= -1
            U[:, i] *= -1
    return U[:, :2] * S[:2], var, Vt


def jugadores_compartidos(jug):
    por = defaultdict(dict)
    for u in jug["unidades"]:
        for p in u.get("B", []):
            por[p["player_id"]][(u["club"], u["coach"])] = p
    def comp(a, b):
        return sum(1 for d in por.values() if a in d and b in d)
    return comp


def puntos_por_era(asignacion_csv, matches_dir):
    """Puntos por partido de cada era, si el esquema lo permite. SOLO contexto
    para elegir el elenco; no entra al informe."""
    asig = Path(asignacion_csv)
    if not asig.exists():
        return None, f"no existe {asig}"
    filas = list(csv.DictReader(asig.open(encoding="utf-8")))
    if not filas:
        return None, "asignacion_partidos.csv vacío"
    cols = set(filas[0])
    need = {"match_id"}
    if not need <= cols:
        return None, f"asignacion_partidos.csv sin match_id (trae {sorted(cols)[:8]}…)"
    club_col = next((c for c in ("club", "team", "equipo") if c in cols), None)
    coach_col = next((c for c in ("coach", "entrenador", "manager") if c in cols), None)
    if not club_col or not coach_col:
        return None, f"asignacion_partidos.csv sin club/entrenador (trae {sorted(cols)[:8]}…)"
    marcador = {}
    arch = sorted(glob.glob(str(Path(matches_dir) / "*.json.gz")))
    if not arch:
        return None, f"sin partidos en {matches_dir}"
    for a in arch:
        with gzip.open(a, "rt", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except Exception:
                continue
        for p in data if isinstance(data, list) else [data]:
            try:
                marcador[str(p["match_id"])] = (
                    p["home_team"]["home_team_name"], p["home_score"],
                    p["away_team"]["away_team_name"], p["away_score"])
            except Exception:
                continue
    if not marcador:
        return None, "los matches no traen home_score/away_score con el esquema esperado"
    acc = defaultdict(lambda: [0, 0])  # (club, coach) -> [puntos, partidos]
    for f in filas:
        mid = str(f["match_id"])
        if mid not in marcador:
            continue
        loc, gl, vis, gv = marcador[mid]
        club = f[club_col]
        if club == loc:
            gf, gc = gl, gv
        elif club == vis:
            gf, gc = gv, gl
        else:
            continue
        pts = 3 if gf > gc else (1 if gf == gc else 0)
        k = (club, f[coach_col])
        acc[k][0] += pts
        acc[k][1] += 1
    return ({k: v[0] / v[1] for k, v in acc.items() if v[1]}, None) if acc else (None, "sin cruces")


def escribe_csv(ruta: Path, filas: list[dict]):
    if not filas:
        return
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def f3(x):
    return "" if x is None else round(float(x), 5)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=20, help="filas por tabla en pantalla")
    ap.add_argument("--min-partidos", type=int, default=0,
                    help="filtra en PANTALLA las eras con menos partidos (los CSV traen todo)")
    ap.add_argument("--puntos", action="store_true", help="intenta puntos por partido")
    a = ap.parse_args()

    h4, met, jug, pres = (carga("did_h4_v1.json"), carga("metricas_v1.json"),
                          carga("jugadores_v1.json"), carga("did_presion_v1.json"))
    # orden cronológico de cada era: el índice de su primer torneo. Sirve para
    # que en `relevos.csv` era_a sea SIEMPRE el saliente y era_b el entrante.
    orden_t = {t: i for i, t in enumerate(h4["parametros"]["torneos_orden"])}
    primer_torneo = {(u["club"], u["coach"]): min((orden_t.get(t, 99) for t in u.get("torneos", [])),
                                                  default=99)
                     for u in h4["unidades"]}
    perf, saltadas = perfil_eras(h4, met, jug)
    for k, falta in saltadas:
        print(f"[salto] {k[0]} · {k[1]}: sin datos en {', '.join(falta)}")

    claves = [m for m, _ in MET]
    completas = [k for k, v in perf.items() if all(v[c] is not None for c in claves)]
    faltantes = [k for k in perf if k not in completas]
    for k in faltantes:
        print(f"[sin PCA] {k[0]} · {k[1]}: le falta alguna métrica del vector")
    filas = [perf[k] for k in completas]
    coords, var, cargas = pca(filas, claves)
    for i, k in enumerate(completas):
        perf[k]["PC1"], perf[k]["PC2"] = float(coords[i, 0]), float(coords[i, 1])

    puntos = {}
    if a.puntos:
        puntos, err = puntos_por_era(RAIZ / "data/eras_api/asignacion_partidos.csv",
                                     RAIZ / "data/raw_api/matches")
        puntos = puntos or {}
        if err:
            print(f"[puntos] no se pudieron calcular: {err}")

    # ---------------- eras.csv ----------------
    eras_csv = []
    for k in sorted(perf, key=lambda k: (k[0], k[1])):
        v = dict(perf[k])
        v["puntos_por_partido"] = f3(puntos.get(k))
        eras_csv.append({kk: (f3(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()})
    escribe_csv(SALIDA / "eras.csv", eras_csv)

    comp = jugadores_compartidos(jug)
    dist = lambda x, y: (math.dist((perf[x]["PC1"], perf[x]["PC2"]),
                                   (perf[y]["PC1"], perf[y]["PC2"]))
                         if "PC1" in perf[x] and "PC1" in perf[y] else None)

    # presión E2 por par (signo orientado de a -> b)
    presion = {}
    for p in pres["pares"]:
        d = p["contrastes"].get("E2", {}).get("did")
        if d:
            presion[(p["club"], p["a"], p["b"])] = (d["theta"], d["q"], d["rechaza"])

    # ---------------- relevos.csv ----------------
    relevos = []
    for p in h4["pares"]:
        club, a_, b_ = p["club"], p["a"], p["b"]
        # cronológico: el saliente primero. Si hay que voltear, se voltean los signos.
        volteado = primer_torneo.get((club, a_), 99) > primer_torneo.get((club, b_), 99)
        if volteado:
            a_, b_ = b_, a_
        sg = -1.0 if volteado else 1.0
        ka, kb = (club, a_), (club, b_)
        if ka not in perf or kb not in perf:
            continue
        e = p["did"]["E_T"]
        pr = presion.get((club, a_, b_))
        if pr is None and (club, b_, a_) in presion:
            t, q, r = presion[(club, b_, a_)]
            pr = (-t, q, r)
        fila = {
            "club": club, "era_a": a_, "era_b": b_,
            "n_a": perf[ka]["n_partidos"], "n_b": perf[kb]["n_partidos"],
            "jugadores_compartidos": comp(ka, kb),
            "empieza_a": primer_torneo.get(ka), "empieza_b": primer_torneo.get(kb),
            "delta_posesion_did": f3(sg * e["rel"]),
            "ic_lo": f3(min(sg * e["ic95"][0], sg * e["ic95"][1])),
            "ic_hi": f3(max(sg * e["ic95"][0], sg * e["ic95"][1])),
            "q": f3(e["q"]), "rechaza_bh": e["rechaza_fdr"],
            "delta_posesion_crudo": f3(sg * p["crudo"]["E_T"]["rel"]),
            "cambia_signo_al_corregir": p.get("cambia_signo_por_correccion"),
            "distancia_perfil": f3(dist(ka, kb)),
            "delta_presion_E2": f3(sg * pr[0]) if pr else "",
            "q_presion": f3(pr[1]) if pr else "",
        }
        for m in ("field_tilt", "npxg_favor", "npxg_contra", "prog_pases", "obv_favor",
                  "continuidad", "n80", "banda"):
            va, vb = perf[ka][m], perf[kb][m]
            fila[f"delta_{m}"] = f3(None if va is None or vb is None else vb - va)
        if puntos:
            fila["delta_puntos_por_partido"] = f3(
                None if ka not in puntos or kb not in puntos else puntos[kb] - puntos[ka])
        relevos.append(fila)
    relevos.sort(key=lambda r: -(r["distancia_perfil"] or 0))
    escribe_csv(SALIDA / "relevos.csv", relevos)

    # ---------------- traslados.csv ----------------
    por_coach = defaultdict(list)
    for k in perf:
        por_coach[k[1]].append(k)
    traslados = []
    for co, ks in por_coach.items():
        clubes = sorted({k[0] for k in ks})
        if len(clubes) < 2:
            continue
        for i, ka in enumerate(sorted(ks)):
            for kb in sorted(ks)[i + 1:]:
                if ka[0] == kb[0]:
                    continue
                fila = {
                    "coach": co, "club_a": ka[0], "club_b": kb[0],
                    "n_a": perf[ka]["n_partidos"], "n_b": perf[kb]["n_partidos"],
                    "clubes_del_tecnico": len(clubes),
                    "jugadores_compartidos": comp(ka, kb),
                    "distancia_perfil": f3(dist(ka, kb)),
                    "posesion_a": f3(perf[ka]["posesion"]), "posesion_b": f3(perf[kb]["posesion"]),
                    "cambia_signo_posesion": (perf[ka]["posesion"] > 0) != (perf[kb]["posesion"] > 0),
                }
                for m in ("field_tilt", "npxg_favor", "npxg_contra", "prog_pases",
                          "obv_favor", "continuidad", "n80", "banda"):
                    va, vb = perf[ka][m], perf[kb][m]
                    fila[f"delta_{m}"] = f3(None if va is None or vb is None else vb - va)
                if puntos:
                    fila["puntos_a"] = f3(puntos.get(ka))
                    fila["puntos_b"] = f3(puntos.get(kb))
                traslados.append(fila)
    traslados.sort(key=lambda r: (r["distancia_perfil"] or 0))
    escribe_csv(SALIDA / "traslados.csv", traslados)

    # ---------------- resumen ----------------
    ds = [r["distancia_perfil"] for r in relevos if r["distancia_perfil"]]
    todas = [dist(x, y) for i, x in enumerate(completas) for y in completas[i + 1:]]
    todas = [d for d in todas if d]
    print(f"\n=== PCA: {len(completas)} eras · PC1 {var[0]*100:.0f}% · PC2 {var[1]*100:.0f}% "
          f"· PC1+PC2 {(var[0]+var[1])*100:.0f}%")
    print("cargas PC1:", ", ".join(f"{c}{cargas[0][i]:+.2f}" for i, c in enumerate(claves)))
    print("cargas PC2:", ", ".join(f"{c}{cargas[1][i]:+.2f}" for i, c in enumerate(claves)))
    print(f"distancia entre dos eras cualesquiera: mediana {st.median(todas):.2f} · "
          f"p90 {sorted(todas)[int(.9*len(todas))]:.2f}")
    print(f"distancia de los {len(ds)} relevos: mediana {st.median(ds):.2f}")

    def tabla(titulo, filas, cols, n):
        print(f"\n=== {titulo}")
        print(" · ".join(cols))
        for r in filas[:n]:
            print(" · ".join(str(r.get(c, "")) for c in cols))

    vis = [r for r in relevos if (r["n_a"] or 0) >= a.min_partidos and (r["n_b"] or 0) >= a.min_partidos]
    tabla("RELEVOS que más movieron al club (distancia de perfil)", vis,
          ["club", "era_a", "era_b", "n_a", "n_b", "jugadores_compartidos",
           "distancia_perfil", "delta_posesion_did", "q", "rechaza_bh"], a.top)
    tabla("RELEVOS que menos movieron al club", list(reversed(vis)),
          ["club", "era_a", "era_b", "n_a", "n_b", "jugadores_compartidos",
           "distancia_perfil", "delta_posesion_did", "q", "rechaza_bh"], a.top)
    tabla("TRASLADOS: el técnico se lleva su idea (distancia chica)", traslados,
          ["coach", "club_a", "club_b", "n_a", "n_b", "clubes_del_tecnico",
           "distancia_perfil", "posesion_a", "posesion_b", "cambia_signo_posesion"], a.top)
    tabla("TRASLADOS: el técnico cambia de idea (distancia grande)", list(reversed(traslados)),
          ["coach", "club_a", "club_b", "n_a", "n_b", "clubes_del_tecnico",
           "distancia_perfil", "posesion_a", "posesion_b", "cambia_signo_posesion"], a.top)

    print(f"\nCSV en {SALIDA}:  eras.csv ({len(eras_csv)}) · relevos.csv ({len(relevos)}) "
          f"· traslados.csv ({len(traslados)})")
    print("Nada de esto entra al informe sin preinscribirse: es exploratorio (se ve antes de fijar reglas).")


if __name__ == "__main__":
    main()
