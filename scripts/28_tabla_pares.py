#!/usr/bin/env python3
"""
28_tabla_pares.py — la tabla de los 60 pares, lista para el reporte.

Convierte `pares_h4_v5.json` y `robustez_h4_final.json` en un JSON plano y
pequeno que el HTML puede incrustar sin calcular nada. Es el «overview» del
reporte: todos los contrastes visibles de un vistazo, ordenables, con la
seccion profunda reservada a los clubes preinscritos.

POR QUE ESTO Y NO GENERAR ARTEFACTOS PARA LOS 18 CLUBES
-------------------------------------------------------
Los 60 pares ya estan calculados. Mostrarlos cuesta cero computo y evita la
unica alternativa honesta que quedaria si no se mostraran: elegir cuales
ensenar, que es seleccionar sobre el resultado.

QUE NO LLEVA, A PROPOSITO
-------------------------
- `p_xT` NO se muestra como contraste. La familia del FDR se declaro sobre
  `dif_E_T` (H4-7) y el q-valor solo aplica a ese. Mostrar dos p-valores lado
  a lado invita a leer el segundo como si estuviera corregido, y no lo esta.
  `rel_xT` si se muestra, como MAGNITUD sin contraste.
- Ningun par se oculta por no ser significativo. La tabla completa es lo que
  impide el cherry-picking.

Uso:
    python scripts/28_tabla_pares.py \\
        --pares reports/pares_h4_v5.json \\
        --robustez reports/robustez_h4_final.json \\
        --out reports/tabla_pares_h4.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Clubes con seccion profunda en el reporte. El criterio esta preinscrito en
# la bitacora: ROL EN EL ARGUMENTO, nunca magnitud del efecto.
CLUBES_PROFUNDOS = {
    "América": "foco del reto",
    "León": "control negativo (equivalencia preinscrita)",
    "Atlas": "limite del metodo: un tecnico difiere de si mismo",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pares", type=Path,
                    default=Path("reports/pares_h4_v5.json"))
    ap.add_argument("--robustez", type=Path,
                    default=Path("reports/robustez_h4_final.json"))
    ap.add_argument("--out", type=Path,
                    default=Path("reports/tabla_pares_h4.json"))
    args = ap.parse_args()

    d = json.loads(args.pares.read_text())
    rb = (json.loads(args.robustez.read_text())
          if args.robustez.exists() else {})

    filas = []
    for x in d["pares"]:
        m = x["magnitud_lambda0"]
        ig = x.get("sensibilidad_n_igualado") or {}
        filas.append({
            "club": x["club"],
            "a": x["a"],
            "b": x["b"],
            "rel_E_T": round(m["rel_E_T"], 5),
            "rel_xT": round(m["rel_xT"], 5),
            "p": round(x["p_permutacion"], 4),
            "sig": bool(x.get("rechaza_fdr")),
            "n_poss_a": x["n_poss_a"],
            "n_poss_b": x["n_poss_b"],
            "torneos": x.get("torneos", []),
            "n_igualado_ok": (None if not ig.get("aplicado")
                              else bool(ig.get("mismo_signo_que_completo"))),
            "rel_E_T_ic95": ([round(v, 5) for v in ig["rel_E_T_ic95"]]
                             if ig.get("rel_E_T_ic95") else None),
            "rel_xT_ic95": ([round(v, 5) for v in ig["rel_xT_ic95"]]
                            if ig.get("rel_xT_ic95") else None),
            "profundo": x["club"] in CLUBES_PROFUNDOS,
        })
    filas.sort(key=lambda r: -abs(r["rel_E_T"]))

    aplicadas = [r for r in filas if r["n_igualado_ok"] is not None
                 and r["sig"]]
    estables = [r for r in aplicadas if r["n_igualado_ok"]]

    salida = {
        "fuente": str(args.pares),
        "n_pares": len(filas),
        "n_significativos": sum(1 for r in filas if r["sig"]),
        "alpha_fdr": d.get("alpha_fdr"),
        "estabilidad_n_igualado": {
            "rechazos_con_sensibilidad": len(aplicadas),
            "conservan_el_signo": len(estables),
        },
        "clubes_profundos": CLUBES_PROFUNDOS,
        "nota_familia": (
            "El q-valor de Benjamini-Hochberg corresponde a la familia "
            "declarada de antemano sobre rel_E_T (regla H4-7). rel_xT se "
            "muestra como magnitud, SIN contraste corregido."),
        "nota_seleccion": (
            "Los 60 pares se muestran completos. Los tres clubes con seccion "
            "profunda se eligieron por su rol en el argumento, no por la "
            "magnitud de su efecto."),
        "control_negativo": (rb.get("control_negativo") or {}).get("elegido"),
        "robustez": [
            {k: f[k] for k in ("estrato", "n_pares", "n_rechazados")}
            for f in rb.get("familias", [])
        ],
        "filas": filas,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, indent=1, ensure_ascii=False))

    print(f"{salida['n_pares']} pares, {salida['n_significativos']} "
          f"significativos")
    print(f"estabilidad: {len(estables)}/{len(aplicadas)} conservan el signo")
    cn = salida["control_negativo"]
    if cn:
        print(f"control negativo: {cn['club']} {cn['a']} vs {cn['b']}")
    else:
        print("control negativo: NO disponible (falta robustez_h4_final.json)")
    faltan = sorted({r["club"] for r in filas} & set(CLUBES_PROFUNDOS)
                    ^ set(CLUBES_PROFUNDOS))
    if faltan:
        print(f"AVISO: clubes profundos sin pares en la tabla: {faltan}")
    print(f"escrito {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
