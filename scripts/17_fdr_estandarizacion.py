#!/usr/bin/env python3
"""
17_fdr_estandarizacion.py — los titulares definitivos, con FDR.

EL PROBLEMA QUE RESUELVE
------------------------
`16_estandarizacion_rival.py` produce del orden de 150 contrastes: 28 pares de
eras por 4 metricas por 2 perspectivas por 2 clubes. Marcar con `*` cada
intervalo que excluye el cero, sin corregir, garantiza falsos positivos: al 5%
nominal se esperan 7 u 8 por puro azar.

ADR-30 es explicita: ninguna distancia se reporta sin su nula, y se violo tres
veces con la conclusion equivocada las tres. Esta es la version de
multiplicidad del mismo principio.

QUE HACE
--------
Lee los JSON de `16_...`, junta los p-valores en UNA familia, aplica
Benjamini-Hochberg con `inference.benjamini_hochberg` -- la misma funcion que
usa la huella tactica, no una reimplementacion -- y emite la tabla que va al
reporte.

Que reutilice la funcion del nucleo no es comodidad: dos implementaciones de BH
que difieran en el manejo de empates darian veredictos distintos para el mismo
dato. Es el bug #2 (dos rutas para lo mismo) esperando turno.

LA FAMILIA CONFIRMATORIA
------------------------
No todos los contrastes entran. Los que tienen cobertura del soporte comun por
debajo de `--min-cobertura` estiman OTRA cosa: no el efecto global sino el
efecto sobre el solapamiento. Mezclarlos tendria dos costes:

  1. Interpretativo: la familia dejaria de tener un estimando comun.
  2. De potencia: BH divide alpha entre el tamano de la familia, asi que
     meter 100 contrastes de baja cobertura sube el umbral de todos y puede
     tumbar hallazgos solidos. En Cruz Azul solo 3 pares llegan al 100%.

Se declara por tanto una familia CONFIRMATORIA (cobertura suficiente) y un
conjunto EXPLORATORIO que se reporta sin q-valor y sin afirmar significancia.
Declararlo antes de mirar los resultados es lo que hace legitima la division.

QUE NO HACE
-----------
No decide el alcance del reporte. Un contraste que sobrevive a BH sigue
necesitando su etiqueta de sobreajuste si viene de una era corta
(`reports/manifiesto_unidades.json`), y sigue siendo una cantidad EMPIRICA por
posesion, no E[T] de la cadena.

Uso:
  python scripts/17_fdr_estandarizacion.py
  python scripts/17_fdr_estandarizacion.py --alpha 0.05 --min-cobertura 0.85
  python scripts/17_fdr_estandarizacion.py --familia por_metrica
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
    "acciones_por_posesion": "acciones por posesion",
    "tasa_remate": "tasa de remate",
    "tasa_gol": "tasa de gol",
    "tasa_presion": "tasa de presion",
}

# Como se lee cada metrica en la cadena conjugada. Sin esto, "acciones por
# posesion" en defensa se lee al reves: mas acciones concedidas es peor, no
# mejor, y el titular sale invertido.
SENTIDO = {
    ("acciones_por_posesion", "attack"): "sostiene mas la posesion",
    ("acciones_por_posesion", "defense"): "concede posesiones mas largas",
    ("tasa_remate", "attack"): "genera mas remates",
    ("tasa_remate", "defense"): "concede mas remates",
    ("tasa_gol", "attack"): "convierte mas",
    ("tasa_gol", "defense"): "concede mas goles",
    ("tasa_presion", "attack"): "juega mas presionado",
    ("tasa_presion", "defense"): "presiona mas al rival",
}


def cargar(carpeta: Path) -> list[dict]:
    filas = []
    encontrados = sorted(carpeta.glob("estandarizacion_*.json"))
    if not encontrados:
        sys.exit(f"No hay estandarizacion_*.json en {carpeta}. Corre el 16 primero.")
    for p in encontrados:
        for r in json.loads(p.read_text()):
            for m, d in r["diferencias"].items():
                if "p_valor" not in d:
                    sys.exit(
                        f"{p.name} no trae `p_valor`: lo genero una version anterior\n"
                        "  de 16_estandarizacion_rival.py. Vuelve a correrlo.\n"
                        "  (BH necesita p-valores; un IC no los da.)"
                    )
                filas.append({
                    "club": r["club"], "perspectiva": r["perspective"],
                    "era_a": r["era_a"], "era_b": r["era_b"], "metrica": m,
                    "diff": d["diff"], "ic95": d["ic95"], "p": d["p_valor"],
                    "cobertura": min(r["masa_cubierta_a"], r["masa_cubierta_b"]),
                    "n_soporte": r["n_soporte"],
                    "archivo": p.name,
                })
    return filas


def cargar_manifiesto(p: Path) -> dict[str, str]:
    """era -> flag de sobreajuste, si el manifiesto existe."""
    if not p.exists():
        return {}
    m = json.loads(p.read_text())
    return {v["coach"]: v["flag"] for v in m.values() if v.get("flag") == "sobreajuste"}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--min-cobertura", type=float, default=0.85, dest="min_cob")
    ap.add_argument("--familia", default="global",
                    choices=["global", "por_metrica", "por_club_perspectiva"],
                    help="como se agrupan los contrastes para BH")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    carpeta = Path(args.reports)
    filas = cargar(carpeta)
    sobreajustadas = cargar_manifiesto(carpeta / "manifiesto_unidades.json")

    conf = [f for f in filas if f["cobertura"] >= args.min_cob]
    expl = [f for f in filas if f["cobertura"] < args.min_cob]

    print("=" * 96)
    print(" FAMILIA DE CONTRASTES")
    print("=" * 96)
    print(f"  totales                : {len(filas)}")
    print(f"  confirmatorios (cob >= {args.min_cob:.0%}) : {len(conf)}")
    print(f"  exploratorios          : {len(expl)}  (sin q-valor, no se afirma nada)")
    print(f"  agrupacion para BH     : {args.familia}")
    print(f"  alpha (FDR)            : {args.alpha}")

    if not conf:
        sys.exit("\nLa familia confirmatoria esta vacia. Baja --min-cobertura y"
                 " declara el cambio.")

    # --- claves de agrupacion ---------------------------------------------
    def clave(f: dict) -> str:
        if args.familia == "por_metrica":
            return f["metrica"]
        if args.familia == "por_club_perspectiva":
            return f"{f['club']}|{f['perspectiva']}"
        return "global"

    grupos: dict[str, list[dict]] = {}
    for f in conf:
        grupos.setdefault(clave(f), []).append(f)

    for k, g in grupos.items():
        p = np.array([f["p"] for f in g])
        q, rech = benjamini_hochberg(p, alpha=args.alpha)
        for f, qi, ri in zip(g, q, rech):
            f["q"] = float(qi)
            f["sobrevive_fdr"] = bool(ri)
        print(f"\n  grupo {k!r}: {len(g)} contrastes, "
              f"{int(rech.sum())} sobreviven a BH "
              f"({int((p <= args.alpha).sum())} lo hacian sin corregir)")

    sobreviven = sorted([f for f in conf if f["sobrevive_fdr"]],
                        key=lambda f: f["q"])
    caidos = [f for f in conf
              if not f["sobrevive_fdr"] and f["p"] <= args.alpha]

    # --- tabla final -------------------------------------------------------
    print("\n" + "=" * 96)
    print(" TITULARES QUE SOBREVIVEN AL FDR")
    print("=" * 96)
    if not sobreviven:
        print("  Ninguno. La frase correcta es 'no detectamos un efecto mayor a X',")
        print("  nunca 'no hay efecto'.")
    else:
        print(f"  {'club':<11} {'p':<4} {'contraste':<38} {'metrica':<22} "
              f"{'dif':>8} {'q':>8}")
        print("  " + "-" * 94)
        for f in sobreviven:
            a, b = f["era_a"], f["era_b"]
            marca = ""
            if a in sobreajustadas or b in sobreajustadas:
                marca = " [era corta]"
            signo = "+" if f["diff"] > 0 else ""
            print(f"  {f['club']:<11} {f['perspectiva'][:3]:<4} "
                  f"{a + ' vs ' + b:<38.38} {ETIQUETA[f['metrica']]:<22} "
                  f"{signo}{f['diff']:>7.4f} {f['q']:>8.4f}{marca}")

    if caidos:
        print("\n" + "=" * 96)
        print(" CAEN AL CORREGIR  (su IC excluia el cero, pero no sobreviven a BH)")
        print("=" * 96)
        print("  Estos son los falsos positivos que la correccion existe para atrapar.")
        print("  NO se reportan como hallazgos.\n")
        for f in sorted(caidos, key=lambda f: f["p"]):
            print(f"  {f['club']:<11} {f['perspectiva'][:3]:<4} "
                  f"{f['era_a'] + ' vs ' + f['era_b']:<38.38} "
                  f"{ETIQUETA[f['metrica']]:<22} p={f['p']:.4f} q={f['q']:.4f}")

    # --- frases listas para el reporte -------------------------------------
    print("\n" + "=" * 96)
    print(" FRASES PARA EL REPORTE  (revisar una por una antes de pegarlas)")
    print("=" * 96)
    for f in sobreviven[:12]:
        a, b = (f["era_a"], f["era_b"]) if f["diff"] > 0 else (f["era_b"], f["era_a"])
        verbo = SENTIDO[(f["metrica"], f["perspectiva"])]
        mag = abs(f["diff"])
        lo, hi = sorted(abs(x) for x in f["ic95"])
        unidad = "acciones" if f["metrica"] == "acciones_por_posesion" else "pp"
        val = mag if unidad == "acciones" else mag * 100
        l, h = (lo, hi) if unidad == "acciones" else (lo * 100, hi * 100)
        nota = ""
        if a in sobreajustadas or b in sobreajustadas:
            nota = "  [una de las dos eras es corta: ver etiqueta de sobreajuste]"
        print(f"\n  · {a} {verbo} que {b}: {val:.2f} {unidad} "
              f"(IC 95% [{l:.2f}, {h:.2f}], q={f['q']:.4f}).{nota}")

    if expl:
        print("\n" + "=" * 96)
        print(f" EXPLORATORIOS ({len(expl)}) — cobertura < {args.min_cob:.0%}")
        print("=" * 96)
        print("  Estiman el efecto sobre el SOLAPAMIENTO, no el efecto global.")
        print("  Van al reporte como contexto, sin q-valor y sin afirmar")
        print("  significancia. En Cruz Azul son la mayoria: con once")
        print("  entrenadores en cuatro anos, muchas eras no comparten")
        print("  calendario. Eso no es un defecto del metodo, es un hallazgo")
        print("  sobre la Liga MX y conviene reportarlo como tal.")

    out = Path(args.out or carpeta / "fdr_estandarizacion.json")
    out.write_text(json.dumps({
        "alpha": args.alpha, "min_cobertura": args.min_cob,
        "familia": args.familia,
        "n_total": len(filas), "n_confirmatorios": len(conf),
        "n_exploratorios": len(expl),
        "n_sobreviven": len(sobreviven), "n_caen": len(caidos),
        "confirmatorios": conf, "exploratorios": expl,
    }, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    print("\nANTES DE PEGAR NADA EN EL REPORTE")
    print("  1. Las cifras son EMPIRICAS por posesion, no E[T] de la cadena.")
    print("     Sirven como control de confusion, no sustituyen al modelo.")
    print("  2. `min_actions` es asimetrico (2 ofensiva, 1 defensiva): las dos")
    print("     perspectivas NO son comparables entre si, solo era contra era")
    print("     dentro de la misma.")
    print("  3. Toda era marcada [era corta] va con su etiqueta de sobreajuste.")
    print("  4. Cuando D1 produzca sus contrastes, se vuelve a correr ESTE")
    print("     script sobre la familia ampliada. Los q-valores cambiaran.")


if __name__ == "__main__":
    main()
