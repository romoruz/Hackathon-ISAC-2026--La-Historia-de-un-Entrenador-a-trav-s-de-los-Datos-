#!/usr/bin/env python3
"""
09_huella_efecto.py — La huella tactica, ordenada por MAGNITUD (ADR-25).

EL PROBLEMA QUE RESUELVE
------------------------
`dtdecoder phase3` rechaza 59 de 80 estados con lambda*=500 y **80 de 80** con
lambda=0. Los p-valores tocan el piso del bootstrap, 1/(B+1). Con 67,492
transiciones, G2_i = 2 n_i D_KL(p_i || q_i) escala con n_i: mide EVIDENCIA, no
MAGNITUD. Un mapa uniformemente significativo no dice donde mirar, que es
exactamente para lo que existe la huella.

LA SOLUCION
-----------
Ordenar por distancia de variacion total por renglon,

    TV_i = 1/2 * sum_j |p_ij - q_ij|

que vive en [0,1] y NO escala con n. La significancia se conserva como filtro
de entrada, no como criterio de orden.

PERO LA TV CRUDA TAMBIEN ENGANA
-------------------------------
TV >= 0 siempre, y con pocos datos sale alta por puro ruido de muestreo: un
renglon con 50 observaciones da TV apreciable aunque p = q exactamente. Ordenar
por TV cruda premia a los renglones ralos.

Es el mismo error que ya se cometio dos veces en este proyecto: el 0.22 de
`detect_regime_changes` y el 0.04 del contraste de contextos, ambos reportados
sin distribucion de referencia.

Aqui se resta la nula: se remuestrean posesiones de la linea base con el MISMO
tamano de muestra que el foco y se calcula la TV que da el puro ruido. Se
reporta

    TV_exceso = TV_observada - mediana(TV_nula)

que es la separacion atribuible al foco, no al tamano de muestra.

MULTIPLICIDAD POR ETAPAS
------------------------
El FDR de `phase3` cubre los 80 renglones. Los IC celda a celda de
`bootstrap_diff` son 80 x 84 = 6,720 y van SIN corregir: dos criterios
distintos en la misma salida.

Aplicar BH sobre las 6,720 seria peor: casi todas son estructuralmente cero
(transiciones imposibles entre zonas lejanas) y diluirian el denominador hasta
matar cualquier hallazgo real.

Se usa un procedimiento POR ETAPAS:
  Etapa 1 - seleccionar renglones por TV_exceso, entre los que pasan el filtro
            de significancia y de tamano minimo de muestra.
  Etapa 2 - dentro de esos renglones UNICAMENTE, aplicar BH sobre sus celdas.

La multiplicidad se controla donde tiene sentido. Se declara como procedimiento
por etapas en el reporte, no como si fuera un unico test.

Uso:
  python scripts/09_huella_efecto.py --unit coach --value "Andre Jardine" \\
      --baseline other_coaches --club "América"
  python scripts/09_huella_efecto.py --unit coach --value "Martin Anselmi" \\
      --baseline other_coaches --club "Cruz Azul" --indir data/processed_cruzazul
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
    from dtdecoder.eras import select_units
    from dtdecoder.estimate import count_matrix
    from dtdecoder.grid import StateSpace
    from dtdecoder.inference import PossessionIndex, benjamini_hochberg, g2_rows
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def _fila_normalizada(C: np.ndarray, ns: int) -> np.ndarray:
    n = C.sum(axis=1, keepdims=True)
    return np.where(n > 0, C / np.maximum(n, _EPS), 1.0 / ns)


def tv_rows(C: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """TV_i = 1/2 sum_j |p_ij - q_ij|, sobre el EMV crudo del foco."""
    P = _fila_normalizada(C, C.shape[1])
    return 0.5 * np.abs(P - Q).sum(axis=1)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach")
    ap.add_argument("--value", required=True)
    ap.add_argument("--baseline", default="other_coaches",
                    choices=["rest", "other_coaches", "opponents"])
    ap.add_argument("--club", default=None)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--top", type=int, default=10, help="renglones del entregable")
    ap.add_argument("--z-min", type=float, default=3.0,
                    help="senal/ruido minima: (TV - med_nula) / DE_nula")
    ap.add_argument("--n-min-top", type=int, default=50,
                    help="observaciones minimas por renglon para entrar al top")
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--out", default="reports/huella_efecto.json")
    ap.add_argument("--out-parquet", default="reports/huella_efecto.parquet")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)
    icfg = cfg["inference"]
    alpha_fdr = float(icfg["fdr_alpha"])
    min_n = int(icfg["min_row_count"])

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)
    focus, base = select_units(trans, args.unit, args.value, args.baseline, args.club)

    C_f = count_matrix(focus, space)
    C_b = count_matrix(base, space)
    Q = _fila_normalizada(C_b, space.n_states)          # referencia = linea base
    n_i = C_f.sum(axis=1)
    testable = n_i >= min_n

    g2_obs = g2_rows(C_f, Q)
    tv_obs = tv_rows(C_f, Q)

    # --- nula por remuestreo de la linea base --------------------------------
    idx_f = PossessionIndex.build(focus, space)
    idx_b = PossessionIndex.build(base, space)
    rng = np.random.default_rng(args.seed)
    m = idx_f.n_poss

    print(f"{args.unit} = {args.value}  vs  {args.baseline}")
    print(f"foco: {m} posesiones, {int(C_f.sum())} transiciones")
    print(f"base: {idx_b.n_poss} posesiones, {int(C_b.sum())} transiciones")
    print(f"calibrando la nula con {args.n_boot} replicas...\n", file=sys.stderr)

    g2_null = np.empty((args.n_boot, space.n_transient))
    tv_null = np.empty((args.n_boot, space.n_transient))
    for b in range(args.n_boot):
        C = idx_b.counts_from(rng.integers(0, idx_b.n_poss, size=m))
        g2_null[b] = g2_rows(C, Q)
        tv_null[b] = tv_rows(C, Q)

    # p-valor con correccion +1 (Davison & Hinkley 1997): piso = 1/(B+1)
    pval = (1.0 + (g2_null >= g2_obs[None, :]).sum(axis=0)) / (1.0 + args.n_boot)
    pval = np.where(testable, pval, 1.0)
    qval, rechazado = benjamini_hochberg(pval, alpha_fdr, mask=testable)

    tv_ruido = np.median(tv_null, axis=0)
    tv_p95 = np.percentile(tv_null, 95, axis=0)
    tv_de = tv_null.std(axis=0)
    tv_exceso = tv_obs - tv_ruido

    # z = senal/ruido. OJO: bajo la nula DE(TV) ~ 1/sqrt(n), asi que
    # z ~ TV_exceso * sqrt(n). ESCALA CON EL TAMANO DE MUESTRA, igual que G2
    # (que escala con n) pero mas suave. Por eso z NO se usa para ordenar:
    # premiaria otra vez a los renglones densos con efectos triviales, que es
    # justo el defecto que ADR-25 corrige.
    #
    # z se usa como FILTRO de fiabilidad; el orden lo dicta TV_exceso, que es
    # interpretable y no escala con n. Filtro por fiabilidad, orden por
    # magnitud: la misma estructura que significancia + TV, un nivel adentro.
    piso_de = max(float(np.median(tv_de)) * 1e-3, 1e-9)
    tv_z = tv_exceso / np.maximum(tv_de, piso_de)

    labels = space.transient_labels()
    tabla = pl.DataFrame({
        "estado": labels,
        "n": n_i,
        "TV": np.round(tv_obs, 4),
        "TV_ruido": np.round(tv_ruido, 4),
        "TV_exceso": np.round(tv_exceso, 4),
        "TV_de_nula": np.round(tv_de, 4),
        "z": np.round(tv_z, 2),
        "TV_supera_p95_nulo": tv_obs > tv_p95,
        "G2": np.round(g2_obs, 2),
        "p_valor": np.round(pval, 5),
        "q_valor": np.round(qval, 5),
        "significativo": rechazado,
        "testeable": testable,
    }).sort("TV_exceso", descending=True)

    # --- Etapa 1: seleccion ---------------------------------------------------
    # Etapa 1: filtrar por fiabilidad y masa; ORDENAR por magnitud.
    sel = (
        tabla.filter(
            pl.col("significativo")
            & (pl.col("z") >= args.z_min)
            & (pl.col("n") >= args.n_min_top)
        )
        .sort("TV_exceso", descending=True)
        .head(args.top)
    )

    print("== HUELLA TACTICA ==")
    print(f"   filtros: significativo (FDR {alpha_fdr}) & z >= {args.z_min} "
          f"& n >= {args.n_min_top}")
    print(f"   orden  : TV_exceso (magnitud, no escala con n)\n")
    print(sel.select(["estado", "n", "TV", "TV_ruido", "TV_exceso", "z", "q_valor"]))

    print(f"\nrenglones testeables      : {int(testable.sum())} de {space.n_transient}")
    print(f"significativos tras FDR   : {int(rechazado.sum())}")
    print(f"con TV sobre el p95 nulo  : {int((tv_obs > tv_p95).sum())}")
    print(f"con z >= {args.z_min:<15.1f}: {int((tv_z >= args.z_min).sum())}")
    print(f"con n >= {args.n_min_top:<15d}: {int((n_i >= args.n_min_top).sum())}")
    print(f"seleccionados (los tres)  : "
          f"{int((rechazado & (tv_z >= args.z_min) & (n_i >= args.n_min_top)).sum())}")
    print(f"\nTV mediana observada      : {np.median(tv_obs):.4f}")
    print(f"TV mediana del RUIDO      : {np.median(tv_ruido):.4f}")
    print(f"  -> el {np.median(tv_ruido)/max(np.median(tv_obs), _EPS):.0%} de la TV "
          "tipica es tamano de muestra, no estilo")

    # --- Etapa 2: celdas dentro de los renglones seleccionados ---------------
    celdas = pl.DataFrame(schema={"desde": pl.Utf8, "hacia": pl.Utf8, "p_foco": pl.Float64,
                                  "q_base": pl.Float64, "delta": pl.Float64,
                                  "q_valor": pl.Float64})
    if sel.height:
        filas_sel = [labels.index(s) for s in sel["estado"].to_list()]
        P_f = _fila_normalizada(C_f, space.n_states)
        etiquetas_to = space.state_labels()

        # p-valor por celda contra la nula ya calculada, restringido a estas filas
        pc, registros = [], []
        for i in filas_sel:
            C_nb = np.empty((args.n_boot, space.n_states))
            # se reutiliza la nula: recalcular por celda requiere las replicas,
            # asi que se aproxima con la desviacion de la nula de TV por fila.
            for j in range(space.n_states):
                if C_f[i].sum() < min_n:
                    continue
                d = P_f[i, j] - Q[i, j]
                if abs(d) < 1e-6:
                    continue
                registros.append({"i": i, "j": j, "delta": d})
        if registros:
            # nula celda a celda: se remuestrea otra vez, guardando P por celda
            necesarias = sorted({r["i"] for r in registros})
            nula_celdas = np.empty((args.n_boot, len(necesarias), space.n_states))
            rng2 = np.random.default_rng(args.seed + 1)
            for b in range(args.n_boot):
                C = idx_b.counts_from(rng2.integers(0, idx_b.n_poss, size=m))
                Pn = _fila_normalizada(C, space.n_states)
                nula_celdas[b] = Pn[necesarias]
            pos = {i: k for k, i in enumerate(necesarias)}
            for r in registros:
                dn = nula_celdas[:, pos[r["i"]], r["j"]] - Q[r["i"], r["j"]]
                pc.append((1.0 + (np.abs(dn) >= abs(r["delta"])).sum()) / (1.0 + args.n_boot))
            qc, rej_c = benjamini_hochberg(np.asarray(pc), alpha_fdr)
            celdas = pl.DataFrame({
                "desde": [labels[r["i"]] for r in registros],
                "hacia": [etiquetas_to[r["j"]] for r in registros],
                "p_foco": [round(float(P_f[r["i"], r["j"]]), 4) for r in registros],
                "q_base": [round(float(Q[r["i"], r["j"]]), 4) for r in registros],
                "delta": [round(float(r["delta"]), 4) for r in registros],
                "q_valor": np.round(qc, 5),
            }).filter(pl.Series(rej_c)).with_columns(
                pl.col("delta").abs().alias("_a")).sort("_a", descending=True).drop("_a")

        print(f"\n== Celdas significativas DENTRO de los {sel.height} renglones "
              f"seleccionados ==")
        print(f"   (BH sobre {len(registros)} celdas, no sobre "
              f"{space.n_transient * space.n_states})")
        print(celdas.head(15))

    tabla.write_parquet(args.out_parquet)
    res = {
        "unidad": f"{args.unit}={args.value}", "baseline": args.baseline,
        "n_boot": args.n_boot, "piso_p_valor": round(1.0 / (1.0 + args.n_boot), 6),
        "testeables": int(testable.sum()),
        "significativos_fdr": int(rechazado.sum()),
        "tv_sobre_p95_nulo": int((tv_obs > tv_p95).sum()),
        "seleccionados": sel.height,
        "tv_mediana_observada": round(float(np.median(tv_obs)), 4),
        "tv_mediana_ruido": round(float(np.median(tv_ruido)), 4),
        "z_min": args.z_min, "n_min_top": args.n_min_top,
        "con_z_suficiente": int((tv_z >= args.z_min).sum()),
        "fdr_celdas": "CONDICIONAL a los renglones seleccionados (dos etapas)",
        "top": sel.to_dicts(),
        "celdas": celdas.to_dicts(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")
    print(f"escrito: {args.out_parquet}  (tabla completa, {tabla.height} renglones)")

    print("\n== LECTURA ==")
    print("  El entregable es el TOP por TV_exceso, no la lista de significativos.")
    print("  z NO ordena: escala con sqrt(n) y volveria a premiar renglones")
    print("  densos con efectos triviales. z filtra, TV_exceso ordena.")
    print("  TV_ruido es lo que da el puro tamano de muestra: si TV ~ TV_ruido,")
    print("  ese renglon no dice nada aunque su p-valor sea diminuto.")
    print("  Los p-valores en el piso (1/(B+1)) significan 'mas alla de la")
    print("  resolucion del bootstrap', no 'infinitamente significativo'.")
    print("\n  DECLARAR EN EL REPORTE: es un procedimiento POR ETAPAS. Los")
    print("  renglones se seleccionan primero; las celdas se testean solo dentro")
    print("  de los seleccionados. No es un unico test con FDR global.")


if __name__ == "__main__":
    main()
