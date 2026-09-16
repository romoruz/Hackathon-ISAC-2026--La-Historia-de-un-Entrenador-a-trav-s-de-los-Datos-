#!/usr/bin/env python3
"""
27_robustez_h4.py — sensibilidad de H4 a las tendencias paralelas, y el
control negativo por equivalencia.

NO RECALCULA NADA. Lee `pares_h4_v*.json` y `linea_base_contemporanea.json`
y rehace solo Benjamini-Hochberg sobre subconjuntos. Es barato y se puede
correr todas las veces que haga falta.

POR QUE TRES ESTRATOS Y NO UN FILTRO
------------------------------------
`linea_base_contemporanea.json` clasifica cada unidad en tres estados, no en
dos:

    paralelas = True    la pendiente de la razon foco/base no difiere
    paralelas = False   diverge
    evaluable = False   NO SE PUDO MEDIR (pocos torneos)

Al cierre de esta sesion: 53 unidades, 23 evaluables, 14 divergen, 30 no
evaluables. Quitar «las que divergen» y dejar dentro las 30 no evaluables
seria seleccionar por HABER SIDO MEDIBLE, que correlaciona con tener muchos
torneos, o sea con las eras largas. Se estaria podando justo donde hay mas
datos, y las que quedan no es que hayan pasado el filtro: es que nunca se les
aplico.

Por eso se reportan los tres estratos y la comparacion interpretable es la
tercera, donde todas las unidades pasaron por el mismo tamiz.

ADVERTENCIA SOBRE EL PRE-TEST
-----------------------------
`linea_base_contemporanea.json` declara en su regla B4 que el contraste es
DEBIL: no hay periodo pre-tratamiento limpio, la deriva del proveedor es
continua. Una prueba de tendencias paralelas sin pre-periodo no es una prueba
de tendencias paralelas, y podar segun su resultado es un pre-test sobre los
mismos datos del analisis. Rambachan & Roth (2023) argumentan precisamente
CONTRA esa practica: el pre-test induce seleccion y distorsiona la cobertura.
Lo que proponen es acotar la violacion y hacer sensibilidad sobre la cota.

Ademas, tendencias paralelas es supuesto del diseno de DIFERENCIAS EN
DIFERENCIAS, que en este proyecto es H5. El par de H4 compara dos eras DENTRO
del mismo club; la base contemporanea entra solo para construir el prior q
(regla H4-5). La dependencia existe pero es indirecta y debil.

CONCLUSION OPERATIVA: esto se reporta como SENSIBILIDAD DECLARADA, nunca como
purga que sustituye al resultado principal. El resultado principal sigue
siendo la familia completa.

CONTROL NEGATIVO (criterio preinscrito el 2026-09-15)
-----------------------------------------------------
Seleccion EXPLORATORIA sobre los pares no rechazados, declarada como tal: no
es una hipotesis preinscrita, es una busqueda con criterio escrito antes de
mirar los resultados de la corrida v4.

Un par es EQUIVALENTE solo si lo es en los dos estadisticos a la vez:

    |rel_E_T| < 3%   Y   |rel_xT| < 10%
    y ademas el IC95 de n igualado contenido dentro de esos margenes.

Los margenes son sustantivos, no salen de los datos: 3% de E[T] es menos de
un cuarto de accion por posesion, y 10% de xT esta por debajo de la variacion
entre torneos de un mismo club.

Desempate: mayor min(n_poss). Si ningun par cumple, se reporta que NO se
encontro control negativo limpio. Eso tambien es un resultado.

Redaccion obligatoria: «no detectamos diferencia mayor a X», nunca «no hay
diferencia» (ADR-30 y la regla de no afirmar la nula).

Uso:
    python scripts/27_robustez_h4.py \\
        --pares reports/pares_h4_v4.json \\
        --linea-base reports/linea_base_contemporanea.json \\
        --out reports/robustez_h4.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

MARGEN_E_T = 0.03
MARGEN_XT = 0.10


def bh(ps: list[float], alpha: float) -> list[bool]:
    """Benjamini-Hochberg. Identica a la de 25_pares_h4.py a proposito."""
    m = len(ps)
    if m == 0:
        return []
    orden = np.argsort(ps)
    rech = np.zeros(m, dtype=bool)
    kmax = -1
    for i, k in enumerate(orden, start=1):
        if ps[k] <= alpha * i / m:
            kmax = i
    if kmax > 0:
        rech[orden[:kmax]] = True
    return rech.tolist()


def estado_unidades(lb: dict) -> dict[tuple[str, str], str]:
    """(club, coach) -> 'paralela' | 'diverge' | 'no_evaluable'."""
    out = {}
    for u in lb.get("unidades", []):
        tp = u.get("tendencias_paralelas") or {}
        if not tp.get("evaluable"):
            e = "no_evaluable"
        elif tp.get("paralelas") is False:
            e = "diverge"
        else:
            e = "paralela"
        out[(u["club"], u["coach"])] = e
    return out


def estrato(par: dict, est: dict[tuple[str, str], str]) -> tuple[str, str]:
    ea = est.get((par["club"], par["a"]), "no_evaluable")
    eb = est.get((par["club"], par["b"]), "no_evaluable")
    return ea, eb


def familia(pares: list[dict], alpha: float, etiqueta: str) -> dict:
    ps = [x["p_permutacion"] for x in pares]
    rech = bh(ps, alpha)
    return {
        "estrato": etiqueta,
        "n_pares": len(pares),
        "n_rechazados": int(sum(rech)),
        "umbral_bh": (max(p for p, r in zip(ps, rech) if r)
                      if any(rech) else None),
        "rechazados": [
            {"club": x["club"], "a": x["a"], "b": x["b"],
             "rel_E_T": x["magnitud_lambda0"]["rel_E_T"],
             "p": x["p_permutacion"]}
            for x, r in zip(pares, rech) if r
        ],
    }


def control_negativo(pares: list[dict]) -> dict:
    """Criterio de equivalencia. Requiere el paquete 08 corrido."""
    cands, sin_ic = [], 0
    for x in pares:
        if x.get("rechaza_fdr"):
            continue
        m = x["magnitud_lambda0"]
        ig = x.get("sensibilidad_n_igualado") or {}
        fila = {
            "club": x["club"], "a": x["a"], "b": x["b"],
            "rel_E_T": m["rel_E_T"], "rel_xT": m["rel_xT"],
            "p": x["p_permutacion"], "p_xT": x.get("p_permutacion_xT"),
            "min_n_poss": min(x["n_poss_a"], x["n_poss_b"]),
        }
        punto_ok = (abs(m["rel_E_T"]) < MARGEN_E_T
                    and abs(m["rel_xT"]) < MARGEN_XT)
        ic_et = ig.get("rel_E_T_ic95")
        ic_xt = ig.get("rel_xT_ic95")
        if ic_xt is None:
            sin_ic += 1
            fila["ic_disponible"] = False
            fila["equivalente"] = None
            fila["equivalente_por_punto"] = punto_ok
        else:
            ic_ok = (max(abs(v) for v in ic_et) < MARGEN_E_T
                     and max(abs(v) for v in ic_xt) < MARGEN_XT)
            fila["ic_disponible"] = True
            fila["rel_E_T_ic95"] = ic_et
            fila["rel_xT_ic95"] = ic_xt
            fila["equivalente"] = bool(punto_ok and ic_ok)
            fila["equivalente_por_punto"] = punto_ok
        cands.append(fila)

    equis = [c for c in cands if c.get("equivalente")]
    elegido = max(equis, key=lambda c: c["min_n_poss"]) if equis else None
    return {
        "margen_rel_E_T": MARGEN_E_T,
        "margen_rel_xT": MARGEN_XT,
        "criterio": ("equivalencia en los DOS estadisticos, punto e IC95; "
                     "desempate por mayor min(n_poss)"),
        "seleccion": "EXPLORATORIA sobre los no rechazados, declarada",
        "n_no_rechazados": len(cands),
        "pares_sin_ic_de_xT": sin_ic,
        "aviso": ("Faltan los IC de xT: la corrida es anterior al paquete 08. "
                  "Vuelve a correr 25_pares_h4.py."
                  if sin_ic else None),
        "candidatos": sorted(cands, key=lambda c: abs(c["rel_E_T"])),
        "elegido": elegido,
        "redaccion": ("«no detectamos una diferencia mayor a "
                      f"{MARGEN_E_T:.0%} en E[T] ni a {MARGEN_XT:.0%} en xT». "
                      "Nunca «no hay diferencia»."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pares", type=Path, required=True)
    ap.add_argument("--linea-base", type=Path, required=True,
                    dest="linea_base")
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--out", type=Path,
                    default=Path("reports/robustez_h4.json"))
    args = ap.parse_args()

    d = json.loads(args.pares.read_text())
    lb = json.loads(args.linea_base.read_text())
    alpha = args.alpha if args.alpha is not None else d.get("alpha_fdr", 0.05)
    est = estado_unidades(lb)
    pares = d["pares"]

    from collections import Counter
    print(f"pares: {len(pares)}   alpha: {alpha}")
    print(f"unidades en la linea base: {len(est)}   "
          f"{dict(Counter(est.values()))}\n")

    completa = familia(pares, alpha, "familia completa (PRINCIPAL)")

    sin_div = [x for x in pares
               if "diverge" not in estrato(x, est)]
    sin_diverge = familia(sin_div, alpha, "sin unidades que divergen")

    solo_ev = [x for x in pares
               if all(e != "no_evaluable" for e in estrato(x, est))]
    evaluables = familia(solo_ev, alpha, "solo unidades evaluables")

    solo_par = [x for x in pares
                if all(e == "paralela" for e in estrato(x, est))]
    paralelas = familia(solo_par, alpha, "solo unidades paralelas")

    for f in (completa, sin_diverge, evaluables, paralelas):
        u = f["umbral_bh"]
        print(f"  {f['estrato']:<36} {f['n_pares']:>3} pares  "
              f"{f['n_rechazados']:>3} rechazados  "
              f"umbral={u if u is None else f'{u:.4f}'}")

    # que rechazos de la familia principal caen en cada estrato
    clave = lambda r: (r["club"], r["a"], r["b"])
    base = {clave(r) for r in completa["rechazados"]}
    caidos = {
        f["estrato"]: sorted(
            base - {clave(r) for r in f["rechazados"]}
            - {clave(r) for r in f["rechazados"]})
        for f in (sin_diverge, evaluables, paralelas)
    }
    # un par puede desaparecer por no estar en el estrato, no por perder
    # significancia: se distingue explicitamente
    presentes = {
        f["estrato"]: {(x["club"], x["a"], x["b"])
                       for x in sub}
        for f, sub in ((sin_diverge, sin_div), (evaluables, solo_ev),
                       (paralelas, solo_par))
    }
    detalle = {}
    for f in (sin_diverge, evaluables, paralelas):
        e = f["estrato"]
        rech_e = {clave(r) for r in f["rechazados"]}
        fuera_estrato = sorted(k for k in base if k not in presentes[e])
        perdio_sig = sorted(k for k in base
                            if k in presentes[e] and k not in rech_e)
        detalle[e] = {
            "salieron_por_no_estar_en_el_estrato": fuera_estrato,
            "estaban_y_perdieron_significancia": perdio_sig,
        }
        print(f"\n  [{e}]")
        print(f"    fuera del estrato: {len(fuera_estrato)}")
        print(f"    dentro pero ya no significativos: {len(perdio_sig)}")
        for k in perdio_sig:
            print(f"      {k[0]}  {k[1]} vs {k[2]}")

    cn = control_negativo(pares)
    print(f"\n== control negativo ==")
    if cn["aviso"]:
        print(f"  {cn['aviso']}")
    if cn["elegido"]:
        e = cn["elegido"]
        print(f"  {e['club']}  {e['a']} vs {e['b']}  "
              f"E[T]{e['rel_E_T']:+.2%}  xT{e['rel_xT']:+.2%}")
    else:
        pp = [c for c in cn["candidatos"] if c["equivalente_por_punto"]]
        print(f"  ninguno cumple el criterio completo; "
              f"{len(pp)} cumplen solo por el punto")
        for c in pp:
            print(f"    {c['club']}  {c['a']} vs {c['b']}  "
                  f"E[T]{c['rel_E_T']:+.2%}  xT{c['rel_xT']:+.2%}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "fuente_pares": str(args.pares),
        "alpha": alpha,
        "advertencia": (
            "SENSIBILIDAD DECLARADA, no purga. El resultado principal es la "
            "familia completa. El contraste de tendencias paralelas es DEBIL "
            "(regla B4: sin pre-periodo limpio) y podar segun su resultado "
            "seria un pre-test sobre los mismos datos."),
        "estado_unidades": dict(Counter(est.values())),
        "familias": [completa, sin_diverge, evaluables, paralelas],
        "detalle_por_estrato": detalle,
        "control_negativo": cn,
    }, indent=2, ensure_ascii=False, default=list))
    print(f"\nescrito {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
