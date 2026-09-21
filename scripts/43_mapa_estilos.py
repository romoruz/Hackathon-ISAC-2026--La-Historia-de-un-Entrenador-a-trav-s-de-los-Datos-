#!/usr/bin/env python3
"""
43_mapa_estilos.py — ADR-60 §5: el mapa de estilos (3.3) y lo que viaja (3.4).

Recalcula desde los JSON de `reports/` (no desde los CSV del barrido) el PCA de
las eras × 9 métricas, importando las MISMAS funciones de 41_barrido_eras.py
(`perfil_eras`, `pca`): misma estandarización, mismo signo. Todo es nivel C:
puntos, flechas por pareja de F60 y por traslado, y la distancia de cada
traslado con su percentil entre TODAS las parejas de eras (contexto, nunca
criterio). Sin elipses (ADR-60 §5).

Uso:
    python scripts/43_mapa_estilos.py --out reports/estilos_v1.json
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HISTORIAS = ["Andre Jardine", "Nicolas Larcamon", "Ignacio Ambriz", "Miguel Herrera", "Fernando Ortiz"]
EJES = {"PC1": "dominio con balón", "PC2": "rotación"}   # nombres elegidos viendo las cargas (ADR-60 §5)


def _mod(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / archivo)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def percentil(v, todas):
    return sum(d <= v for d in todas) / len(todas)


def construye(rep: Path) -> dict:
    B = _mod("barrido41", "41_barrido_eras.py")
    R = _mod("relevos42", "42_relevos.py")
    J = {k: json.loads((rep / f).read_text(encoding="utf-8")) for k, f in
         (("h4", "did_h4_v1.json"), ("met", "metricas_v1.json"), ("jug", "jugadores_v1.json"))}
    perf, _ = B.perfil_eras(J["h4"], J["met"], J["jug"])
    claves = [m for m, _ in B.MET]
    completas = [k for k, v in perf.items() if all(v[c] is not None for c in claves)]
    filas = [perf[k] for k in completas]
    coords, var, cargas = B.pca(filas, claves)
    pos = {k: (float(coords[i, 0]), float(coords[i, 1])) for i, k in enumerate(completas)}

    def dist(a, b):
        return math.dist(pos[a], pos[b])

    todas = sorted(dist(a, b) for a, b in itertools.combinations(completas, 2))
    fam, _ = R.familia(J["h4"], J["met"])
    relevos = [{"club": c, "a": a, "b": b, "distancia": dist((c, a), (c, b)),
                "percentil": percentil(dist((c, a), (c, b)), todas)}
               for c, a, b in fam if (c, a) in pos and (c, b) in pos]
    traslados = []
    for co in HISTORIAS:
        ks = sorted((k for k in completas if k[1] == co), key=lambda k: perf[k]["club"])
        for ka, kb in itertools.combinations(ks, 2):
            d = dist(ka, kb)
            traslados.append({"coach": co, "club_a": ka[0], "club_b": kb[0], "distancia": d,
                              "percentil": percentil(d, todas)})
    return {
        "adr": "ADR-60 §5", "nivel": "C",
        "ejes": {**EJES, "varianza": [float(var[0]), float(var[1])],
                 "nota": "nombres elegidos viendo las cargas; se declara (ADR-60 §5)"},
        "metricas": claves,
        "cargas": {c: [float(cargas[0, i]), float(cargas[1, i])] for i, c in enumerate(claves)},
        "eras": [{"club": k[0], "coach": k[1], "PC1": pos[k][0], "PC2": pos[k][1],
                  "n_partidos": perf[k]["n_partidos"]} for k in completas],
        "sin_mapa": [list(k) for k in perf if k not in pos],
        "distancias_todas": {"n": len(todas), "mediana": todas[len(todas) // 2],
                             "p10": todas[int(.1 * len(todas))], "p90": todas[int(.9 * len(todas))]},
        "relevos": relevos, "traslados": traslados,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "estilos_v1.json"))
    a = ap.parse_args()
    try:
        out = construye(Path(a.reports))
    except Exception as e:   # noqa: BLE001  (una falla aquí no debe dejar un JSON a medias)
        sys.exit(f"ABORTA: {e}")
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    d = out["distancias_todas"]
    print(f"escrito {a.out} · {len(out['eras'])} eras · PC1 {out['ejes']['varianza'][0]:.0%} "
          f"PC2 {out['ejes']['varianza'][1]:.0%} · mediana entre eras {d['mediana']:.2f} · "
          f"{len(out['relevos'])} relevos · {len(out['traslados'])} traslados")


if __name__ == "__main__":
    main()
