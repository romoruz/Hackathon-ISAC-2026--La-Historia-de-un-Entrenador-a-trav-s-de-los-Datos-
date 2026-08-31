#!/usr/bin/env python3
"""
08_ic_derivados.py — Intervalos de confianza para lo que se reporta de verdad.

EL HUECO QUE CIERRA
-------------------
El resultado principal del proyecto es:

    "Jardine sostiene posesiones un 20% mas largas que Solari"

y es un ESTIMADOR PUNTUAL. `bootstrap_diff` da IC para celdas de P, no para
E[T]. Las cantidades que se reportan -- longitud esperada, probabilidad de gol,
probabilidad de remate -- pasan todas por N = (I-Q)^-1, que es una funcion NO
LINEAL de la matriz completa. No hay forma de derivar su IC de los IC celda a
celda.

QUE CALCULA
-----------
Por unidad (entrenador o equipo), y para la DIFERENCIA entre dos:

  E_T      = alpha' N 1        acciones esperadas antes de absorber
  P_gol    = alpha' B[:,GOAL]  prob. de que la posesion termine en gol
  P_remate = alpha' (B_GOAL + B_SHOT)

alpha es la distribucion inicial EMPIRICA, remuestreada en cada replica junto
con las posesiones: si se fijara, el IC ignoraria la incertidumbre de donde
empiezan las posesiones.

POR QUE SE COMPARAN DOS UNIDADES DE REMUESTREO
-----------------------------------------------
`07_cobertura_ic.py` mostro que para celdas de P el bootstrap por posesion y el
ingenuo por transicion dan el MISMO ancho: por Billingsley (1961) la
verosimilitud se factoriza por renglones y las transiciones de un renglon son
multinomiales iid aunque vengan de la misma posesion.

Es tentador afirmar que para E[T] si importa "porque arrastra covarianza a lo
largo de la posesion". Pero bajo una cadena bien especificada los renglones
siguen siendo independientes, asi que NO es obvio. Puede importar por la
correlacion entre los n_i de distintos renglones dentro de una posesion -- o
puede no importar.

Es una pregunta EMPIRICA. El script mide las dos y deja que los numeros
decidan, en vez de asumir cual gana. Ya fallo una prediccion teorica en este
mismo proyecto; no conviene apoyarse en otra.

Uso:
  python scripts/08_ic_derivados.py --a "Andre Jardine" --b "Santiago Solari" \\
      --club "América"
  python scripts/08_ic_derivados.py --a "Martin Anselmi" --b "Juan Reynoso" \\
      --club "Cruz Azul" --indir data/processed_cruzazul
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.absorbing import AbsorbingChain
    from dtdecoder.config import Config
    from dtdecoder.estimate import count_matrix, shrink
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


# ==========================================================================
# Indice de posesiones con estado inicial
# ==========================================================================
class Indice:
    """CSR de transiciones por posesion, guardando ademas el estado inicial.

    `PossessionIndex` de inference.py no expone alpha, y aqui hace falta
    remuestrearlo: si alpha se fija al valor de la muestra completa, el IC
    ignora la incertidumbre sobre donde empiezan las posesiones y sale
    demasiado estrecho.
    """

    def __init__(self, trans: pl.DataFrame, space: StateSpace):
        orden = ["poss_uid"] + (["event_index"] if "event_index" in trans.columns else [])
        df = trans.sort(orden)
        codes = df["poss_uid"].to_numpy()
        i = df["from_state"].to_numpy().astype(np.int64)
        j = df["to_state"].to_numpy().astype(np.int64)
        self.flat = i * space.n_states + j
        cambio = np.empty(len(codes), dtype=bool)
        cambio[0] = True
        cambio[1:] = codes[1:] != codes[:-1]
        self.starts = np.flatnonzero(cambio)
        self.lens = np.append(self.starts[1:], len(codes)) - self.starts
        self.inicial = i[self.starts]           # estado inicial de cada posesion
        self.nt, self.ns = space.n_transient, space.n_states

    @property
    def n_poss(self) -> int:
        return len(self.starts)

    def _rangos(self, elegidas: np.ndarray) -> np.ndarray:
        s, l = self.starts[elegidas], self.lens[elegidas]
        total = int(l.sum())
        if total == 0:
            return np.empty(0, dtype=np.int64)
        out = np.ones(total, dtype=np.int64)
        fin = np.cumsum(l)
        out[0] = s[0]
        if len(s) > 1:
            out[fin[:-1]] = s[1:] - (s[:-1] + l[:-1]) + 1
        return np.cumsum(out)

    def conteos_y_alpha(self, elegidas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        idx = self._rangos(elegidas)
        bc = np.bincount(self.flat[idx], minlength=self.nt * self.ns)
        C = bc.reshape(self.nt, self.ns).astype(np.float64)
        a = np.bincount(self.inicial[elegidas], minlength=self.nt).astype(float)
        return C, a / max(a.sum(), _EPS)

    def todo(self) -> tuple[np.ndarray, np.ndarray]:
        return self.conteos_y_alpha(np.arange(self.n_poss))


# ==========================================================================
# Cantidades derivadas
# ==========================================================================
def derivadas(C: np.ndarray, alpha: np.ndarray, prior: np.ndarray,
              lam: float, space: StateSpace) -> dict[str, float] | None:
    """E[T], P(gol) y P(remate) desde la distribucion inicial empirica."""
    P = shrink(C, prior, lam)
    ch = AbsorbingChain(P=P, space=space)
    if ch.spectral_radius() >= 1.0 - 1e-10:
        return None
    n = space.n_transient
    A = np.eye(n) - ch.Q
    N1 = np.linalg.solve(A, np.ones(n))
    B = np.linalg.solve(A, ch.R)
    g = space.absorbing.index("GOAL")
    s = space.absorbing.index("SHOT_NOGOAL")
    return {
        "E_T": float(alpha @ N1),
        "P_gol": float(alpha @ B[:, g]),
        "P_remate": float(alpha @ (B[:, g] + B[:, s])),
    }


CANTIDADES = ("E_T", "P_gol", "P_remate")


def ic(replicas: np.ndarray, punto: float, nivel: float, metodo: str) -> tuple[float, float]:
    a = (1.0 - nivel) / 2.0
    lo, hi = np.quantile(replicas, a), np.quantile(replicas, 1.0 - a)
    if metodo == "percentile":
        return float(lo), float(hi)
    return float(2.0 * punto - hi), float(2.0 * punto - lo)   # basic (ADR-10)


def corre(idx_a: Indice, idx_b: Indice, prior, lam, space, n_boot, seed,
          unidad: str, nivel: float, metodo: str) -> dict:
    rng = np.random.default_rng(seed)

    Ca, aa = idx_a.todo()
    Cb, ab = idx_b.todo()
    pa, pb = derivadas(Ca, aa, prior, lam, space), derivadas(Cb, ab, prior, lam, space)
    if pa is None or pb is None:
        sys.exit("rho(Q) >= 1 en la muestra completa: la cadena no absorbe.")

    reps = {k: [] for k in CANTIDADES}
    fallos = 0
    for _ in range(n_boot):
        if unidad == "posesion":
            ea = rng.integers(0, idx_a.n_poss, size=idx_a.n_poss)
            eb = rng.integers(0, idx_b.n_poss, size=idx_b.n_poss)
            Ca_, aa_ = idx_a.conteos_y_alpha(ea)
            Cb_, ab_ = idx_b.conteos_y_alpha(eb)
        else:
            # Ingenuo: remuestrea TRANSICIONES sueltas. alpha se mantiene fijo
            # porque sin posesiones no hay "inicio" que remuestrear -- lo cual
            # es en si mismo parte de por que el ingenuo subestima.
            Ca_ = _remuestrea_transiciones(idx_a, rng)
            Cb_ = _remuestrea_transiciones(idx_b, rng)
            aa_, ab_ = aa, ab
        da = derivadas(Ca_, aa_, prior, lam, space)
        db = derivadas(Cb_, ab_, prior, lam, space)
        if da is None or db is None:
            fallos += 1
            continue
        for k in CANTIDADES:
            reps[k].append(da[k] - db[k])

    out = {"unidad_remuestreo": unidad, "metodo": metodo, "replicas_validas": n_boot - fallos}
    for k in CANTIDADES:
        r = np.asarray(reps[k])
        punto = pa[k] - pb[k]
        lo, hi = ic(r, punto, nivel, metodo)
        rel = punto / pb[k] * 100 if abs(pb[k]) > _EPS else float("nan")
        out[k] = {
            "a": round(pa[k], 5), "b": round(pb[k], 5),
            "diff": round(punto, 5), "lo": round(lo, 5), "hi": round(hi, 5),
            "ancho": round(hi - lo, 5),
            "diff_pct": round(rel, 2),
            "lo_pct": round(lo / pb[k] * 100, 2) if abs(pb[k]) > _EPS else None,
            "hi_pct": round(hi / pb[k] * 100, 2) if abs(pb[k]) > _EPS else None,
            "excluye_cero": bool(lo > 0 or hi < 0),
        }
    return out


def _remuestrea_transiciones(idx: Indice, rng) -> np.ndarray:
    n = len(idx.flat)
    pick = rng.integers(0, n, size=n)
    bc = np.bincount(idx.flat[pick], minlength=idx.nt * idx.ns)
    return bc.reshape(idx.nt, idx.ns).astype(np.float64)


# ==========================================================================
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--club", default=None)
    ap.add_argument("--lam", type=float, default=0.0,
                    help="0 por defecto: las MAGNITUDES van con lambda=0 (ADR-22)")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--nivel", type=float, default=0.95)
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--solo-posesion", action="store_true",
                    help="omite la comparacion con el remuestreo ingenuo")
    ap.add_argument("--out", default="reports/ic_derivados.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)

    if args.unit not in trans.columns:
        sys.exit(f"No existe la columna '{args.unit}' en transitions.parquet")
    A = trans.filter(pl.col(args.unit) == args.a)
    B = trans.filter(pl.col(args.unit) == args.b)
    for nom, df in ((args.a, A), (args.b, B)):
        if df.height == 0:
            disp = trans[args.unit].drop_nulls().unique().to_list()
            sys.exit(f"Sin transiciones para '{nom}'. Disponibles: {disp}")

    # Prior externo a AMBAS unidades (ADR-06): si contuviera a cualquiera, el
    # encogimiento las acercaria y subestimaria la diferencia.
    fuera = trans.filter((pl.col(args.unit) != args.a) & (pl.col(args.unit) != args.b)
                         | pl.col(args.unit).is_null())
    Cf = count_matrix(fuera, space)
    nf = Cf.sum(axis=1, keepdims=True)
    prior = np.where(nf > 0, Cf / np.maximum(nf, _EPS), 1.0 / space.n_states)

    idx_a, idx_b = Indice(A, space), Indice(B, space)
    print(f"{args.a}: {idx_a.n_poss} posesiones, {A.height} transiciones")
    print(f"{args.b}: {idx_b.n_poss} posesiones, {B.height} transiciones")
    print(f"lambda = {args.lam}   |   {args.n_boot} replicas   |   nivel {args.nivel}\n")

    unidades = ["posesion"] if args.solo_posesion else ["posesion", "transicion"]
    resultados = []
    for unidad in unidades:
        for metodo in ("basic", "percentile"):
            resultados.append(
                corre(idx_a, idx_b, prior, args.lam, space, args.n_boot,
                      args.seed, unidad, args.nivel, metodo))

    for k in CANTIDADES:
        print(f"== {k} ==")
        print(f"  {args.a}: {resultados[0][k]['a']:.5f}   "
              f"{args.b}: {resultados[0][k]['b']:.5f}")
        print(f"  {'unidad':<11} {'metodo':<11} {'IC 95%':>26} {'ancho':>9}  excl.0")
        for r in resultados:
            d = r[k]
            rango = f"[{d['lo']:+.5f}, {d['hi']:+.5f}]"
            print(f"  {r['unidad_remuestreo']:<11} {r['metodo']:<11} {rango:>26} "
                  f"{d['ancho']:>9.5f}  {d['excluye_cero']}")
        d0 = resultados[0][k]
        if d0["lo_pct"] is not None:
            print(f"  --> {d0['diff_pct']:+.2f}%  IC 95% [{d0['lo_pct']:+.2f}%, "
                  f"{d0['hi_pct']:+.2f}%]   (posesion, basic)")
        print()

    res = {"a": args.a, "b": args.b, "unit": args.unit, "lambda": args.lam,
           "n_boot": args.n_boot, "nivel": args.nivel,
           "n_poss_a": idx_a.n_poss, "n_poss_b": idx_b.n_poss,
           "resultados": resultados}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"escrito: {out}")

    print("\n== LECTURA ==")
    print("  El IC de la fila 'posesion/basic' es el que va al reporte.")
    print("  Comparar el ancho contra 'transicion': si el ingenuo sale MAS")
    print("  ESTRECHO, ADR-07 si importa aqui aunque no importara en las celdas")
    print("  de P (07_cobertura_ic). Si salen iguales, tambien es un resultado:")
    print("  significa que la dependencia intra-posesion no propaga a N.")
    print("\n  Con lambda>0 estas cantidades quedan ATENUADAS igual que las")
    print("  celdas (ADR-22). El default es lambda=0 por eso.")


if __name__ == "__main__":
    main()
