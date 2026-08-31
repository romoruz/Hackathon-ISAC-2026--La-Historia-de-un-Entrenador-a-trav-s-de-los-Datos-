#!/usr/bin/env python3
"""
07_cobertura_ic.py — ¿Los intervalos de confianza cubren lo que dicen cubrir?

LA PREGUNTA
-----------
Un IC al 95% que en realidad cubre el 78% de las veces es peor que no tener
intervalo: da una falsa sensacion de rigor. La UNICA validacion de un IC es la
COBERTURA EMPIRICA: simular desde un proceso con parametro conocido, construir
el intervalo muchas veces, y contar que fraccion contiene el valor verdadero.

Este script contesta cuatro preguntas de una sola corrida:

  Q1. ¿El IC de `bootstrap_diff` alcanza su nivel nominal?
  Q2. ¿El bootstrap POR POSESION produce intervalos mas anchos que el ingenuo
      por transicion? (ADR-07 lo afirma; nunca se comprobo)
  Q3. ¿"basic" cubre mejor que "percentile"? (ADR-10 lo eligio por argumento
      teorico, no empirico)
  Q4. ¿Cuanto se degrada la cobertura cuando el modelo esta MAL ESPECIFICADO
      como sabemos que lo esta? (ADR-21: sobredispersion)

POR QUE NO SE USA `synth.py`
----------------------------
`synth.py` inyecta el sesgo a nivel de GENERADOR DE EVENTOS (`dy ~ Normal(...)`),
asi que la matriz de transicion verdadera NO se conoce en forma cerrada. Es
perfecto para lo que fue disenado -- recuperacion de parametros: ¿detecta la
Fase 3 el sesgo? -- pero sin parametro verdadero no hay cobertura que medir.

Aqui se genera a nivel de CADENA: se fija P, se muestrean posesiones desde P, y
la verdad es exacta. Es el mismo diseno de van Arem et al. (arXiv 2511.09457,
2604.21087), donde cada modelo de verdad describe una cadena de Markov usada
para remuestrear conjuntos de datos de distintos tamanos.

EL ESTIMANDO IMPORTA (y es donde Gemini se equivoco)
-----------------------------------------------------
La cobertura se mide contra el PARAMETRO VERDADERO, no contra el EMV. El EMV es
el estimador; el parametro es el objetivo.

Y con lambda > 0, `_diff_estimate` no estima p_A - p_B sino la version ATENUADA
por n_i/(n_i+lambda) (ADR-22, atenuacion mediana 0.585 con lambda=500). Medir
cobertura del parametro verdadero con lambda=500 dara mala cobertura, y ESO NO
ES UN BUG DEL BOOTSTRAP: es el encogimiento haciendo su trabajo. Por eso el
default es lambda=0, donde el estimador es (casi) insesgado y se aisla la
mecanica del remuestreo.

Con --lam > 0 se reporta ADEMAS la cobertura del estimando atenuado, que es lo
que el intervalo si deberia cubrir.

Uso:
  python scripts/07_cobertura_ic.py                      # markoviano, lam=0
  python scripts/07_cobertura_ic.py --proceso mezcla     # mal especificado
  python scripts/07_cobertura_ic.py --lam 500            # ver la atenuacion
  python scripts/07_cobertura_ic.py --n-poss 200 500 2000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.estimate import count_matrix
    from dtdecoder.grid import StateSpace
    from dtdecoder.inference import bootstrap_diff
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


# ==========================================================================
# Generador a nivel de cadena
# ==========================================================================
def matriz_aleatoria(space: StateSpace, rng: np.random.Generator,
                     p_abs=(0.10, 0.30), concentracion: float = 0.7,
                     p_auto: float = 0.0) -> np.ndarray:
    """Matriz P (n_transient x n_states) estocastica con rho(Q) < 1 garantizado.

    Cada renglon manda entre 10% y 30% de su masa a los absorbentes, lo que
    asegura que la posesion termina casi seguramente. La concentracion baja del
    Dirichlet produce renglones ralos, parecidos a los reales.
    """
    nt, ns = space.n_transient, space.n_states
    na = space.n_absorbing
    P = np.zeros((nt, ns))
    for i in range(nt):
        w_abs = rng.uniform(*p_abs)
        P[i, :nt] = rng.dirichlet(np.full(nt, concentracion)) * (1.0 - w_abs)
        P[i, nt:] = rng.dirichlet(np.full(na, 1.0)) * w_abs
    if p_auto > 0:
        # Masa en la diagonal i->i. En los datos reales frac_auto ~ 0.28
        # (05_auto_transiciones). Sin esto, una posesion casi nunca revisita
        # un estado y cada renglon recibe <1 transicion por posesion: el
        # bootstrap por bloques no tiene agrupamiento que capturar y ADR-07
        # se vuelve indistinguible del remuestreo ingenuo.
        idx = np.arange(nt)
        P[idx, idx] = 0.0
        P = P / P.sum(axis=1, keepdims=True) * (1.0 - p_auto)
        P[idx, idx] = p_auto
    return P


def perturba(P: np.ndarray, rng: np.random.Generator, magnitud: float) -> np.ndarray:
    """P_A a partir de P_B con una diferencia verdadera controlada y conocida."""
    ruido = rng.normal(0.0, magnitud, size=P.shape)
    Q = np.clip(P + ruido, 1e-6, None)
    return Q / Q.sum(axis=1, keepdims=True)


def muestrea(P: np.ndarray, alpha: np.ndarray, n_poss: int, space: StateSpace,
             rng: np.random.Generator, kmax: int = 60,
             prefijo: str = "p") -> pl.DataFrame:
    """Muestrea `n_poss` posesiones desde la cadena P. Devuelve transiciones."""
    nt = space.n_transient
    cum = np.cumsum(P, axis=1)
    uid, frm, to = [], [], []
    for k in range(n_poss):
        s = int(rng.choice(nt, p=alpha))
        for _ in range(kmax):
            u = rng.random()
            nxt = int(np.searchsorted(cum[s], u))
            nxt = min(nxt, P.shape[1] - 1)
            uid.append(f"{prefijo}{k}")
            frm.append(s)
            to.append(nxt)
            if nxt >= nt:
                break
            s = nxt
    return pl.DataFrame({"poss_uid": uid, "from_state": frm, "to_state": to})


def muestrea_mezcla(P1: np.ndarray, P2: np.ndarray, w: float, alpha: np.ndarray,
                    n_poss: int, space: StateSpace, rng: np.random.Generator,
                    prefijo: str = "p") -> pl.DataFrame:
    """Cada posesion viene de P1 con prob w, de P2 con prob 1-w.

    Es la MALA ESPECIFICACION que el contraste de bondad de ajuste detecto en
    los datos reales (ADR-21): sobredispersion por mezcla de dos poblaciones de
    posesion que el estado no distingue. Aqui se inyecta a proposito para medir
    cuanto se degrada la cobertura.
    """
    n1 = int(rng.binomial(n_poss, w))          # equivalente y mucho mas rapido
    a = muestrea(P1, alpha, n1, space, rng, prefijo=f"{prefijo}A")
    b = muestrea(P2, alpha, n_poss - n1, space, rng, prefijo=f"{prefijo}B")
    return pl.concat([a, b])


def verdad_por_montecarlo(gen, space: StateSpace, n_ref: int) -> np.ndarray:
    """P verdadera de un proceso sin forma cerrada, por muestra gigante.

    Para la mezcla, la matriz que el EMV agrupado estima NO es w*P1+(1-w)*P2:
    es el promedio ponderado por VISITAS ESPERADAS a cada estado bajo cada
    componente. En vez de derivarlo, se estima con una muestra de referencia
    grande. El estimando queda definido como "la matriz a la que converge el
    EMV agrupado", que es exactamente lo que el metodo estima.
    """
    C = count_matrix(gen(n_ref), space)
    n = C.sum(axis=1, keepdims=True)
    return np.where(n > 0, C / np.maximum(n, _EPS), 1.0 / space.n_states)


# ==========================================================================
# Un experimento de cobertura
# ==========================================================================
def por_transicion(trans: pl.DataFrame) -> pl.DataFrame:
    """Convierte cada transicion en su propia 'posesion'.

    Truco para reusar `bootstrap_diff` como bootstrap INGENUO: si cada bloque
    tiene tamano 1, el remuestreo por bloques degenera en remuestreo iid de
    transiciones -- justo lo que ADR-07 dice que subestima la varianza.
    """
    return trans.with_columns(
        pl.int_range(pl.len()).cast(pl.Utf8).alias("poss_uid"))


def experimento(space, P_A, P_B, alpha, verdad, n_poss, n_rep, n_boot, lam,
                metodo, unidad, rng, gen_A=None, gen_B=None, mask=None) -> dict:
    prior = np.full((space.n_transient, space.n_states), 1.0 / space.n_states)
    dentro = np.zeros_like(verdad, dtype=float)
    ancho = np.zeros_like(verdad, dtype=float)

    for _ in range(n_rep):
        a = gen_A(n_poss) if gen_A else muestrea(P_A, alpha, n_poss, space, rng, prefijo="a")
        b = gen_B(n_poss) if gen_B else muestrea(P_B, alpha, n_poss, space, rng, prefijo="b")
        if unidad == "transicion":
            a, b = por_transicion(a), por_transicion(b)
        ci = bootstrap_diff(a, b, space, prior, lam, n_boot=n_boot,
                            seed=int(rng.integers(0, 2**31)), method=metodo)
        dentro += ((ci.lo <= verdad) & (verdad <= ci.hi)).astype(float)
        ancho += ci.hi - ci.lo

    cob = dentro / n_rep
    return {
        "cobertura": float(cob[mask].mean()),
        "ancho_medio": float((ancho / n_rep)[mask].mean()),
        "celdas_evaluadas": int(mask.sum()),
        "cobertura_min_celda": float(cob[mask].min()),
    }


# ==========================================================================
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nx", type=int, default=3)
    ap.add_argument("--ny", type=int, default=2)
    ap.add_argument("--n-fases", type=int, default=2)
    ap.add_argument("--n-poss", type=int, nargs="+", default=[300, 1000, 3000])
    ap.add_argument("--n-rep", type=int, default=200)
    ap.add_argument("--n-boot", type=int, default=300)
    ap.add_argument("--lam", type=float, default=0.0)
    ap.add_argument("--magnitud", type=float, default=0.03,
                    help="tamano de la diferencia verdadera inyectada")
    ap.add_argument("--proceso", default="markov", choices=["markov", "mezcla"])
    ap.add_argument("--peso-mezcla", type=float, default=0.6)
    ap.add_argument("--n-ref", type=int, default=40000,
                    help="posesiones para estimar la verdad de la mezcla")
    ap.add_argument("--umbral-celda", type=float, default=0.01,
                    help="solo celdas con p_A verdadera por encima de esto")
    ap.add_argument("--p-auto", type=float, default=0.28,
                    help="masa en la diagonal i->i; 0.28 replica los datos reales")
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--out", default="reports/cobertura_ic.json")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    space = StateSpace(nx=args.nx, ny=args.ny, length=120.0, width=80.0,
                       phases=tuple(f"f{k}" for k in range(args.n_fases)))
    alpha = rng.dirichlet(np.ones(space.n_transient))

    P_B = matriz_aleatoria(space, rng, p_auto=args.p_auto)
    P_A = perturba(P_B, rng, args.magnitud)

    gen_A = gen_B = None
    if args.proceso == "mezcla":
        # A y B son cada uno una mezcla de dos poblaciones de posesion.
        P_A2 = perturba(P_A, rng, 0.08)
        P_B2 = perturba(P_B, rng, 0.08)
        w = args.peso_mezcla
        gen_A = lambda n, _r=rng: muestrea_mezcla(P_A, P_A2, w, alpha, n, space, _r, "a")
        gen_B = lambda n, _r=rng: muestrea_mezcla(P_B, P_B2, w, alpha, n, space, _r, "b")
        print(f"estimando la verdad por Monte Carlo ({args.n_ref} posesiones)...",
              file=sys.stderr)
        V_A = verdad_por_montecarlo(gen_A, space, args.n_ref)
        V_B = verdad_por_montecarlo(gen_B, space, args.n_ref)
    else:
        V_A, V_B = P_A, P_B

    verdad = V_A - V_B
    mask = V_A >= args.umbral_celda   # celdas degeneradas (p=0) cubren trivialmente

    print(f"proceso  : {args.proceso}   p_auto = {args.p_auto}")
    print(f"estados  : {space.n_transient} transitorios, {space.n_states} totales")
    print(f"celdas   : {int(mask.sum())} de {verdad.size} superan p_A >= {args.umbral_celda}")
    print(f"lambda   : {args.lam}")
    print(f"|diff| medio verdadero: {np.abs(verdad[mask]).mean():.5f}\n")

    filas = []
    for n_poss in args.n_poss:
        for unidad in ("posesion", "transicion"):
            for metodo in ("basic", "percentile"):
                r = experimento(space, P_A, P_B, alpha, verdad, n_poss,
                                args.n_rep, args.n_boot, args.lam, metodo,
                                unidad, rng, gen_A, gen_B, mask)
                r.update({"n_poss": n_poss, "unidad": unidad, "metodo": metodo})
                filas.append(r)
                print(f"  n={n_poss:>5}  {unidad:<11} {metodo:<11} "
                      f"cobertura={r['cobertura']:.3f}  ancho={r['ancho_medio']:.4f}")

    # Atenuacion: con lam>0 el estimando no es la diferencia verdadera.
    extra = {}
    if args.lam > 0:
        C_A = count_matrix(muestrea(P_A, alpha, max(args.n_poss), space, rng), space)
        n_i = C_A.sum(axis=1, keepdims=True)
        factor = n_i / np.maximum(n_i + args.lam, _EPS)
        extra["atenuacion_mediana"] = float(np.median(factor))
        extra["estimando_atenuado_mean_abs"] = float(
            np.abs((verdad * factor)[mask]).mean())

    res = {"proceso": args.proceso, "lambda": args.lam, "n_rep": args.n_rep,
           "n_boot": args.n_boot, "nominal": 0.95, "resultados": filas, **extra}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    print(f"\nescrito: {out}")
    print("\n== LECTURA ==")
    print("  Q1 COBERTURA. Nominal 0.95. Por debajo de ~0.90 el IC es")
    print("     enganosamente estrecho y no debe reportarse tal cual.")
    print("  Q2 BLOQUES vs INGENUO. El ancho por POSESION debe ser MAYOR que")
    print("     por TRANSICION. Si son iguales, el bloqueo no esta capturando")
    print("     la dependencia y el argumento de ADR-07 es solo retorico.")
    print("  Q3 basic vs percentile. Decide ADR-10 con evidencia, no con teoria.")
    print("  Q4 Corre con --proceso mezcla y compara: es cuanto se degrada la")
    print("     cobertura bajo la mala especificacion que ADR-21 documenta.")
    if args.lam > 0:
        print("\n  ATENCION: con lambda>0 el IC cubre la diferencia ATENUADA, no la")
        print("  verdadera. Una cobertura baja aqui NO es un fallo del bootstrap.")


if __name__ == "__main__":
    main()
