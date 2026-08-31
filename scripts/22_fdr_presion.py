#!/usr/bin/env python3
"""
22_fdr_presion.py — los titulares de D1, con FDR sobre la familia correcta.

ADR-47 y ADR-48
---------------
ADR-47 declaro que los contrastes de pi son una familia SEPARADA de los de
estandarizacion por rival: preguntas distintas, objetos distintos,
procedimientos distintos. Los q de aquella quedaron fijados el 2026-08-24.

ADR-48 subdivide el bloque de presion en dos familias:

  D1-CONTRASTES (esta corregida aqui)
    Toda afirmacion de que dos eras DIFIEREN en presion: pi_e(z) por zona,
    nivel en k >= 3, pendiente de decaimiento, L = 1 por fase.
    Nula: permutacion de la etiqueta de era ENTRE PARTIDOS.
    Es la familia de descubrimiento. BH al 5%.

  D1-CALIBRACION (reportada aparte, sin corregir junto con la anterior)
    La asociacion entre presion y desenlace, por era.
    Nula: permutacion de la MARCA DE PRESION dentro de estrato.
    No afirma que dos entrenadores difieran: verifica que el instrumento mida
    algo. Penalizar la potencia de los descubrimientos por comprobar que la
    metrica no es ruido seria un castigo sin sentido.

Declarado ANTES de correr esta correccion.

UN DETALLE DE BH QUE IMPORTA
----------------------------
Se reutiliza `inference.benjamini_hochberg`, la misma funcion de la huella
tactica. Dos implementaciones que difieran en el manejo de empates darian
veredictos distintos para el mismo dato: es el bug #2 (dos rutas para lo
mismo) esperando turno.

Sobre los empates: `np.minimum.accumulate` sobre los q ordenados garantiza que
todos los p iguales reciban el mismo q, asi que no hay enmascaramiento. Lo que
si duele es el SUELO del p: con B permutaciones el minimo alcanzable es
2/(B+1), y un p inflado empuja la curva empirica hacia arriba y hace que BH
rechace MENOS. Es conservador, no distorsionado -- pero por eso las corridas
que entran aqui deben usar --n-perm 5000.

Uso:
  python scripts/22_fdr_presion.py
  python scripts/22_fdr_presion.py --alpha 0.05 --min-n-perm 5000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    from dtdecoder.inference import benjamini_hochberg
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

ETIQUETA = {
    "zona": "pi(z) por zona",
    "nivel": "nivel de presion en k>=k0",
    "pendiente": "decaimiento de pi con k",
    "L1": "posesiones de 1 accion",
}


def cargar(carpeta: Path, min_perm: int) -> tuple[list[dict], list[dict], list[str]]:
    contrastes: list[dict] = []
    calibracion: list[dict] = []
    avisos: list[str] = []

    # ---- 18_campo_presion: pi(z) por zona --------------------------------
    for p in sorted(carpeta.glob("campo_presion_*.json")):
        d = json.loads(p.read_text())
        if d.get("n_perm", 0) < min_perm:
            avisos.append(f"{p.name}: n_perm={d.get('n_perm')} < {min_perm}. "
                          "El p esta acotado por abajo y BH rechazara de menos.")
        for z in d["zonas"]:
            contrastes.append({
                "tipo": "zona", "club": d["club"],
                "a": d["era_a"], "b": d["era_b"],
                "detalle": f"z{z['ix']}{z['iy']} ({z['cx']:.0f},{z['cy']:.0f})",
                "efecto": z["delta"], "p": z["p"], "n": z["n_a"] + z["n_b"],
                "fuente": p.name,
            })

    # ---- 19: pendiente ----------------------------------------------------
    for p in sorted(carpeta.glob("presion_indice_*.json")):
        d = json.loads(p.read_text())
        if "p_permutacion" in d:
            contrastes.append({
                "tipo": "pendiente", "club": d["club"],
                "a": d["era_a"], "b": d["era_b"],
                "detalle": f"desde k={d.get('kmin', 1)}",
                "efecto": d["dif_pendiente"], "p": d["p_permutacion"],
                "n": None, "fuente": p.name,
            })

    # ---- 20: nivel y L=1 --------------------------------------------------
    for p in sorted(carpeta.glob("nivel_calibracion_*.json")):
        d = json.loads(p.read_text())
        if d.get("n_perm", 0) < min_perm:
            avisos.append(f"{p.name}: n_perm={d.get('n_perm')} < {min_perm}.")
        n = d.get("nivel")
        if n:
            contrastes.append({
                "tipo": "nivel", "club": d["club"], "a": d["era_a"], "b": d["era_b"],
                "detalle": f"k>={d.get('k0', 3)}", "efecto": n["diff"], "p": n["p"],
                "n": n["n_a"] + n["n_b"], "fuente": p.name,
            })
        for fase, v in (d.get("L1") or {}).items():
            # El estrato `balon parado` x L=1 tiene pi = 0 en las DOS eras por
            # construccion: una posesion de una sola accion nacida de saque o
            # cornero es un despeje o un remate directo, con el balon parado en
            # el instante inicial y sin presion que anotar. Su p = 1.0 no es un
            # resultado: es un estrato vacio de informacion. Incluirlo inflaria
            # el tamano de la familia y bajaria la potencia de los demas.
            if v["pi_a"] == 0.0 and v["pi_b"] == 0.0:
                avisos.append(f"{p.name}: estrato '{fase}' x L=1 tiene pi=0 en "
                              "las dos eras (definicional). Excluido de la familia.")
                continue
            contrastes.append({
                "tipo": "L1", "club": d["club"], "a": d["era_a"], "b": d["era_b"],
                "detalle": fase, "efecto": v["diff"], "p": v["p"],
                "n": v["n_a"] + v["n_b"], "fuente": p.name,
            })

    # ---- 21: calibracion (familia aparte) ---------------------------------
    for p in sorted(carpeta.glob("calibracion_*.json")):
        d = json.loads(p.read_text())
        for era, v in d.get("eras", {}).items():
            calibracion.append({
                "club": d["club"], "era": era, "efecto": v["efecto_corregido"],
                "p": v["p"], "efecto_def_vieja": v.get("efecto_definicion_vieja"),
                "n_estratos": v.get("n_estratos"), "fuente": p.name,
            })
    return contrastes, calibracion, avisos


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--min-n-perm", type=int, default=5000, dest="min_perm")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    carpeta = Path(args.reports)
    contrastes, calib, avisos = cargar(carpeta, args.min_perm)
    if not contrastes:
        sys.exit(f"No hay JSON de D1 en {carpeta}. Corre los scripts 18-21 primero.")

    print("=" * 96)
    print(" FAMILIA D1-CONTRASTES  (descubrimiento: ¿difieren dos eras?)")
    print("=" * 96)
    por_tipo: dict[str, int] = {}
    for c in contrastes:
        por_tipo[c["tipo"]] = por_tipo.get(c["tipo"], 0) + 1
    for t, n in sorted(por_tipo.items()):
        print(f"  {ETIQUETA.get(t, t):<28} {n:>4}")
    print(f"  {'TOTAL':<28} {len(contrastes):>4}")
    print(f"\n  alpha = {args.alpha}   ·   BH con inference.benjamini_hochberg")

    if avisos:
        print("\n  AVISOS:")
        for a in dict.fromkeys(avisos):
            print(f"    - {a}")

    p = np.array([c["p"] for c in contrastes])
    q, rech = benjamini_hochberg(p, alpha=args.alpha)
    for c, qi, ri in zip(contrastes, q, rech):
        c["q"] = float(qi); c["sobrevive"] = bool(ri)

    n_sin = int((p <= args.alpha).sum())
    print(f"\n  {n_sin} pasaban sin corregir · {int(rech.sum())} sobreviven a BH")
    print(f"  suelo del p observado: {p.min():.5f}  "
          f"(minimo alcanzable con {args.min_perm} permutaciones: "
          f"{2/(args.min_perm+1):.5f})")

    viven = sorted([c for c in contrastes if c["sobrevive"]], key=lambda c: c["q"])
    caen = sorted([c for c in contrastes
                   if not c["sobrevive"] and c["p"] <= args.alpha],
                  key=lambda c: c["p"])

    print("\n" + "=" * 96)
    print(" SOBREVIVEN AL FDR")
    print("=" * 96)
    if not viven:
        print("  Ninguno. La frase correcta es 'no detectamos un efecto mayor a X',")
        print("  nunca 'no hay efecto'.")
    else:
        print(f"  {'club':<11} {'contraste':<34} {'que':<24} {'detalle':<16} "
              f"{'efecto':>9} {'q':>8}")
        print("  " + "-" * 94)
        for c in viven:
            print(f"  {c['club']:<11} {c['a']+' vs '+c['b']:<34.34} "
                  f"{ETIQUETA.get(c['tipo'], c['tipo']):<24} {c['detalle']:<16.16} "
                  f"{c['efecto']:+9.4f} {c['q']:>8.4f}")

    print("\n" + "=" * 96)
    print(" CAEN AL CORREGIR  (p <= alpha pero no sobreviven a BH)")
    print("=" * 96)
    if not caen:
        print("  Ninguno.")
        print("  Que la correccion no elimine nada en una familia de este tamano")
        print("  es sospechoso, no tranquilizador: reviselo antes de celebrarlo.")
    else:
        print("  Son los falsos positivos que la correccion existe para atrapar.")
        print("  NO se reportan como hallazgos.\n")
        for c in caen:
            print(f"  {c['club']:<11} {c['a']+' vs '+c['b']:<34.34} "
                  f"{ETIQUETA.get(c['tipo'], c['tipo']):<24} {c['detalle']:<16.16} "
                  f"p={c['p']:.4f} q={c['q']:.4f}")

    # ------------------------------------------------ familia de calibracion
    print("\n" + "=" * 96)
    print(" FAMILIA D1-CALIBRACION  (verificacion del instrumento, ADR-48)")
    print("=" * 96)
    if not calib:
        print("  Sin JSON de 21_calibracion_presion.py. La familia de contrastes")
        print("  describe DONDE y CUANDO presiona cada DT; sin calibracion no se")
        print("  puede afirmar que esa presion sea eficaz.")
    else:
        print("  Fuera de BH a proposito: no afirma que dos eras difieran, sino")
        print("  que la etiqueta de presion mide algo con consecuencia.\n")
        print(f"  {'club':<11} {'era':<22} {'efecto':>9} {'p':>8} "
              f"{'(def. vieja)':>13} {'estratos':>9}")
        print("  " + "-" * 78)
        for c in sorted(calib, key=lambda c: (c["club"], c["era"])):
            v = c.get("efecto_def_vieja")
            print(f"  {c['club']:<11} {c['era']:<22} {c['efecto']:+9.4f} "
                  f"{c['p']:>8.4f} {('' if v is None else f'{v:+.4f}'):>13} "
                  f"{str(c.get('n_estratos') or ''):>9}")
        efs = [c["efecto"] for c in calib]
        if all(e > 0.01 for e in efs) and all(c["p"] <= 0.05 for c in calib):
            print("\n  >> El instrumento mide algo. Los contrastes de arriba se")
            print("     pueden leer en clave de eficacia, no solo de conducta.")
        else:
            print("\n  >> El instrumento no queda certificado. Los contrastes de")
            print("     arriba describen DONDE y CUANDO se presiona; el verbo de")
            print("     cada frase del reporte debe ser descriptivo.")

    out = Path(args.out or carpeta / "fdr_presion.json")
    out.write_text(json.dumps({
        "adr": "ADR-47 (familia separada de estandarizacion) + ADR-48 (dos "
               "subfamilias dentro de D1)",
        "alpha": args.alpha, "min_n_perm": args.min_perm,
        "n_contrastes": len(contrastes), "n_sobreviven": len(viven),
        "n_caen": len(caen), "avisos": list(dict.fromkeys(avisos)),
        "contrastes": contrastes, "calibracion": calib,
    }, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    print("\nANTES DE PEGAR NADA EN EL REPORTE")
    print("  1. Todo q de aqui es de la familia D1-CONTRASTES. Los de la")
    print("     estandarizacion por rival son de otra familia y quedaron")
    print("     fijados el 2026-08-24 (ADR-47).")
    print("  2. El contraste de nivel CONDICIONA a sobrevivir hasta k0. La")
    print("     calibracion mostro que la atenuacion es despreciable, pero el")
    print("     caveat va en la misma diapositiva.")
    print("  3. Toda era con `params_per_obs` > 0.5 lleva su etiqueta de")
    print("     sobreajuste (ADR-46), y el argumento de credibilidad es")
    print("     DIRECCIONAL: refuerza los nulos, NO los positivos.")
    print("  4. La calibracion es ASOCIACION. StatsBomb anota presion cuando un")
    print("     defensor se acerca, y se acerca mas cuando el rival ya esta en")
    print("     problemas. El diseno no separa esa direccion.")


if __name__ == "__main__":
    main()
