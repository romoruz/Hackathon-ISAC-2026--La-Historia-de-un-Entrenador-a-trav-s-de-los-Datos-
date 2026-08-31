#!/usr/bin/env python3
"""
18_campo_presion.py — D1: el campo de presion como ADELGAZAMIENTO.

LA IDEA
-------
La presion no es un proceso propio: es una MODIFICACION del proceso del rival.
Las acciones rivales forman un proceso puntual sobre la cancha, y la presion es
un marcaje binario sobre ese proceso -- que StatsBomb ya anota en
`under_pressure`. Para la era e y la zona z:

    pi_e(z) = P(under_pressure = 1 | accion rival en z, era e)

Por el teorema de adelgazamiento (Procesos Estocasticos §3.4), si las acciones
rivales en z son Poisson de intensidad lambda_riv(z), las presionadas son
Poisson de intensidad pi_e(z)*lambda_riv(z). El punto clave: **pi esta libre de
la exposicion**. Es la TASA de presion, no el conteo.

POR QUE ESO IMPORTA
-------------------
Contar acciones defensivas por zona sin denominador mide donde JUEGA el rival,
no donde PRESIONAS tu. Un equipo que cede campo tiene mas acciones defensivas
abajo por construccion. Es el mismo error de longitud del bug #11, con otro
disfraz.

LA PREGUNTA CONCRETA
--------------------
La tasa AGREGADA de presion es practicamente identica entre clubes (0.2104
America, 0.2125 Cruz Azul). Eso sugiere que la intensidad total es una constante
del formato y que la senal tactica es ESPACIAL.

Y hay una tension que resolver: Jardine presiona MAS que Solari y Herrera
(+1.6 y +2.1 pp, con FDR) pero concede posesiones MAS LARGAS (+0.73 y +0.52
acciones). Presionar mas deberia acortar la tenencia rival. Que ocurran las dos
cosas significa que presion y duracion estan desacopladas, y la explicacion
natural es geografica. Este script la contrasta.

QUE HACE
--------
1. pi_e(z) con encogimiento hacia el pool de las OTRAS eras (prior sin fuga).
   lambda por validacion cruzada por bloques de posesion.
2. LRT binomial por zona entre dos eras.
3. Nula por PERMUTACION de la etiqueta de era DENTRO de (rival), preservando la
   composicion de calendario. La era es propiedad del partido, asi que se
   permutan partidos, no acciones.
4. FDR de Benjamini-Hochberg sobre las 20 zonas, con `inference.benjamini_hochberg`.
5. Diagnostico de sobredispersion de Cochran phi_z: la presion esta AGRUPADA
   dentro de la posesion, asi que el IC binomial ingenuo es demasiado angosto.
   Se compara contra el bootstrap por bloques, que la absorbe sin modelarla.
6. Todo se presenta en el marco del CLUB via StateSpace.mirror_zone (ADR-40).

Uso:
  python scripts/18_campo_presion.py --club "América" \
      --a "Andre Jardine" --b "Santiago Solari"
  python scripts/18_campo_presion.py --club "Cruz Azul" \
      --a "Martin Anselmi" --b "Juan Reynoso" --figura
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
    from dtdecoder.grid import StateSpace
    from dtdecoder.inference import benjamini_hochberg
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=tuple(cfg["phase_order"]))


# --------------------------------------------------------------------------
# Acciones rivales con su zona (en marco del club) y su marca
# --------------------------------------------------------------------------
def acciones_rivales(trans: pl.DataFrame, sp: StateSpace, club: str) -> pl.DataFrame:
    """Una fila por accion rival: zona en NUESTRO marco, marca, era, rival.

    Se excluyen las filas TERMINAL: son transiciones artificiales sin evento y
    por tanto sin marca de presion. Incluirlas diluiria pi, y mas en las eras
    con mas absorciones terminales -- sesgo diferencial (ADR-42).
    """
    if "coach_faced" not in trans.columns:
        sys.exit("Falta `coach_faced`. Corre phase0 con --club.")
    if "under_pressure" not in trans.columns:
        sys.exit("Falta `under_pressure`. Corre phase0 tras el parche D0.")

    sub = trans.filter(
        (pl.col("team") != club)
        & (pl.col("action_type") != "TERMINAL")
        & pl.col("coach_faced").is_not_null()
    )
    if sub.height == 0:
        sys.exit(f"Sin acciones rivales para club={club!r}.")

    n_ph = len(sp.phases)
    z_nativo = (sub["from_state"].to_numpy().astype(int) // n_ph)
    # ADR-40: la cadena se estima en marco nativo; el espejo se aplica al
    # PRESENTAR. Aqui ya presentamos, asi que se aplica.
    z_club = sp.mirror_zone(z_nativo)

    return sub.select(
        pl.col("poss_uid"), pl.col("match_id"),
        pl.col("coach_faced").alias("era"),
        pl.col("team").alias("rival"),
        pl.col("under_pressure").fill_null(False).cast(pl.Int8).alias("presion"),
    ).with_columns(pl.Series("zona", z_club, dtype=pl.Int32))


def conteos(acc: pl.DataFrame, era: str, n_zonas: int) -> tuple[np.ndarray, np.ndarray]:
    """(D_z, A_z): presionadas y totales por zona."""
    g = (acc.filter(pl.col("era") == era).group_by("zona")
            .agg(pl.col("presion").sum().alias("D"), pl.len().alias("A")))
    D = np.zeros(n_zonas); A = np.zeros(n_zonas)
    for r in g.to_dicts():
        D[r["zona"]] = r["D"]; A[r["zona"]] = r["A"]
    return D, A


# --------------------------------------------------------------------------
# Encogimiento y su lambda
# --------------------------------------------------------------------------
def shrink_pi(D: np.ndarray, A: np.ndarray, q: np.ndarray, lam: float) -> np.ndarray:
    """pi*(lam) = (D + lam*q) / (A + lam). Mismo estimador que estimate.shrink
    con dos columnas: es un renglon binomial."""
    return (D + lam * q) / np.maximum(A + lam, _EPS)


def cv_lambda_pi(acc: pl.DataFrame, era: str, q: np.ndarray, n_zonas: int,
                 grid: list[float], k: int, seed: int) -> tuple[float, np.ndarray]:
    """lambda por CV POR POSESION, no por accion.

    Dos acciones de la misma posesion estan fuertemente correlacionadas: si una
    esta presionada la siguiente lo esta con probabilidad mucho mayor que la
    marginal, porque es el mismo episodio. Partir por accion filtraria
    informacion entre train y test y el lambda saldria artificialmente bajo.
    Es el mismo argumento de `estimate.possession_folds`.
    """
    sub = acc.filter(pl.col("era") == era)
    uids = sub["poss_uid"].unique().sort().to_numpy()   # ordenar ANTES de barajar
    rng = np.random.default_rng(seed)
    rng.shuffle(uids)
    folds = np.array_split(uids, k)

    scores = np.zeros(len(grid)); total = 0.0
    for f in folds:
        test = sub.filter(pl.col("poss_uid").is_in(f.tolist()))
        train = sub.filter(~pl.col("poss_uid").is_in(f.tolist()))
        if test.height == 0 or train.height == 0:
            continue
        Dtr, Atr = conteos(train.with_columns(pl.lit(era).alias("era")), era, n_zonas)
        Dte, Ate = conteos(test.with_columns(pl.lit(era).alias("era")), era, n_zonas)
        total += Ate.sum()
        for i, lam in enumerate(grid):
            p = np.clip(shrink_pi(Dtr, Atr, q, lam), 1e-9, 1 - 1e-9)
            scores[i] += float((Dte * np.log(p) + (Ate - Dte) * np.log(1 - p)).sum())
    scores = scores / max(total, 1.0)
    return float(grid[int(np.argmax(scores))]), scores


# --------------------------------------------------------------------------
# LRT binomial de dos muestras
# --------------------------------------------------------------------------
def g2_zonas(Da, Aa, Db, Ab) -> np.ndarray:
    """G2_z para H0: pi_a(z) = pi_b(z). Contraste simple vs compuesta."""
    out = np.zeros(len(Da))
    for z in range(len(Da)):
        na, nb = Aa[z], Ab[z]
        if na < 1 or nb < 1:
            continue
        p0 = (Da[z] + Db[z]) / max(na + nb, _EPS)
        if p0 <= 0 or p0 >= 1:
            continue
        g = 0.0
        for D, A in ((Da[z], na), (Db[z], nb)):
            for O, E in ((D, A * p0), (A - D, A * (1 - p0))):
                if O > 0:
                    g += O * np.log(O / max(E, _EPS))
        out[z] = 2.0 * g
    return out


def nula_permutacion(acc: pl.DataFrame, a: str, b: str, n_zonas: int,
                     n_perm: int, seed: int) -> np.ndarray:
    """Nula por permutacion de la etiqueta de era DENTRO de cada rival.

    Dos decisiones que importan:

    1. Se permutan PARTIDOS, no acciones. `coach_faced` es una propiedad del
       partido; permutar acciones destruiria la correlacion intra-partido y
       daria una nula demasiado angosta -- se "detectaria" estilo donde solo
       hay agrupamiento.

    2. Se permuta DENTRO de cada rival. Permutar libremente rompe la
       composicion de calendario, que es justo lo que la estandarizacion se
       encarga de fijar. Estratificar preserva que cada era enfrente a los
       mismos rivales en la nula que en los datos.

    ADR-30: ninguna distancia se reporta sin su nula.
    """
    sub = acc.filter(pl.col("era").is_in([a, b]))
    partidos = (sub.group_by("match_id")
                   .agg(pl.col("era").first(), pl.col("rival").first()))
    rng = np.random.default_rng(seed)

    # (match_id -> fila) para reasignar rapido
    mid = partidos["match_id"].to_numpy()
    era0 = partidos["era"].to_numpy()
    riv = partidos["rival"].to_numpy()
    grupos = {r: np.flatnonzero(riv == r) for r in np.unique(riv)}

    acc_m = sub["match_id"].to_numpy()
    acc_z = sub["zona"].to_numpy()
    acc_p = sub["presion"].to_numpy()
    pos = {m: i for i, m in enumerate(mid)}
    idx_acc = np.array([pos[m] for m in acc_m])

    null = np.empty((n_perm, n_zonas))
    for t in range(n_perm):
        etq = era0.copy()
        for _, ix in grupos.items():
            etq[ix] = rng.permutation(etq[ix])
        es_a = (etq[idx_acc] == a)
        Da = np.bincount(acc_z[es_a], weights=acc_p[es_a], minlength=n_zonas)
        Aa = np.bincount(acc_z[es_a], minlength=n_zonas).astype(float)
        Db = np.bincount(acc_z[~es_a], weights=acc_p[~es_a], minlength=n_zonas)
        Ab = np.bincount(acc_z[~es_a], minlength=n_zonas).astype(float)
        null[t] = g2_zonas(Da, Aa, Db, Ab)
    return null


# --------------------------------------------------------------------------
# Sobredispersion de Cochran
# --------------------------------------------------------------------------
def cochran_phi(acc: pl.DataFrame, era: str, n_zonas: int) -> np.ndarray:
    """phi_z sobre PARTIDOS. phi >> 1 indica agrupamiento.

    La presion no es un ensayo Bernoulli independiente por accion: viene en
    EPISODIOS. Si una accion esta presionada, la siguiente de la misma posesion
    lo esta con probabilidad mucho mayor que la marginal. Eso infla la varianza
    por encima de la binomial y hace que el IC ingenuo sea demasiado angosto.

    NO se corrige modelando la correlacion: el bootstrap por bloques de posesion
    ya la absorbe. phi solo la MIDE, para poder declarar el factor de inflacion.
    """
    sub = acc.filter(pl.col("era") == era)
    D, A = conteos(sub, era, n_zonas)
    pi = np.divide(D, np.maximum(A, _EPS))
    g = (sub.group_by(["match_id", "zona"])
            .agg(pl.col("presion").sum().alias("D"), pl.len().alias("A")))
    acumul = np.zeros(n_zonas); cuenta = np.zeros(n_zonas)
    for r in g.to_dicts():
        z, Dm, Am = r["zona"], r["D"], r["A"]
        v = Am * pi[z] * (1 - pi[z])
        if v <= _EPS or Am < 5:
            continue
        acumul[z] += (Dm - Am * pi[z]) ** 2 / v
        cuenta[z] += 1
    return np.divide(acumul, np.maximum(cuenta - 1, 1.0))


def boot_ic_pi(acc: pl.DataFrame, era: str, n_zonas: int, n_boot: int,
               seed: int) -> tuple[np.ndarray, np.ndarray]:
    """IC de pi_z por bootstrap de POSESIONES (absorbe el agrupamiento)."""
    sub = acc.filter(pl.col("era") == era)
    uids = sub["poss_uid"].unique().sort().to_numpy()
    idx = {u: i for i, u in enumerate(uids)}
    au = np.array([idx[u] for u in sub["poss_uid"].to_numpy()])
    az = sub["zona"].to_numpy(); ap = sub["presion"].to_numpy()
    orden = np.argsort(au, kind="stable")
    au, az, ap = au[orden], az[orden], ap[orden]
    inicio = np.searchsorted(au, np.arange(len(uids)))
    fin = np.append(inicio[1:], len(au))

    rng = np.random.default_rng(seed)
    reps = np.empty((n_boot, n_zonas))
    for t in range(n_boot):
        elegidas = rng.integers(0, len(uids), len(uids))
        trozos = [np.arange(inicio[c], fin[c]) for c in elegidas]
        ii = np.concatenate(trozos) if trozos else np.empty(0, int)
        D = np.bincount(az[ii], weights=ap[ii], minlength=n_zonas)
        A = np.bincount(az[ii], minlength=n_zonas).astype(float)
        reps[t] = np.divide(D, np.maximum(A, _EPS))
    return np.quantile(reps, 0.025, axis=0), np.quantile(reps, 0.975, axis=0)


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--indir", default=None)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--n-perm", type=int, default=2000, dest="n_perm")
    ap.add_argument("--n-boot", type=int, default=1000, dest="n_boot")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--figura", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config.load(args.config)
    sp = _space(cfg)
    nz = sp.n_zones

    indir = args.indir or ("data/processed" if args.club == "América"
                           else "data/processed_cruzazul")
    trans = pl.read_parquet(Path(indir) / "transitions.parquet")
    acc = acciones_rivales(trans, sp, args.club)

    for e in (args.a, args.b):
        if acc.filter(pl.col("era") == e).height == 0:
            sys.exit(f"Era desconocida: {e!r}. "
                     f"Disponibles: {sorted(acc['era'].unique().to_list())}")

    print(f"club {args.club!r} · malla {sp.nx}x{sp.ny} · "
          f"{acc.height:,} acciones rivales\n")
    print("=" * 92)
    print(f" pi(z): {args.a}  vs  {args.b}")
    print("=" * 92)

    Da, Aa = conteos(acc, args.a, nz)
    Db, Ab = conteos(acc, args.b, nz)
    print(f"  {args.a:<22} {int(Aa.sum()):>8,} acciones, pi marginal = "
          f"{Da.sum()/max(Aa.sum(),1):.4f}")
    print(f"  {args.b:<22} {int(Ab.sum()):>8,} acciones, pi marginal = "
          f"{Db.sum()/max(Ab.sum(),1):.4f}")

    # --- prior SIN FUGA: el pool de las OTRAS eras ------------------------
    # ADR-06: si q contiene al foco, lambda* se infla y las diferencias se
    # atenuan por construccion.
    grid = [float(x) for x in cfg["estimation"]["lambda_grid"]]
    k = int(cfg["estimation"]["cv_folds"]); seed = int(cfg["estimation"]["cv_seed"])
    lam, q_dict = {}, {}
    for foco in (args.a, args.b):
        otras = acc.filter(~pl.col("era").is_in([foco]))
        Do, Ao = conteos(otras.with_columns(pl.lit("_").alias("era")), "_", nz)
        q = np.divide(Do, np.maximum(Ao, _EPS))
        q[Ao == 0] = Do.sum() / max(Ao.sum(), _EPS)
        q_dict[foco] = q
        lam[foco], _ = cv_lambda_pi(acc, foco, q, nz, grid, k, seed)
    print(f"\n  lambda* por CV por posesion: {args.a} = {lam[args.a]:g} · "
          f"{args.b} = {lam[args.b]:g}")

    pi_a = shrink_pi(Da, Aa, q_dict[args.a], lam[args.a])
    pi_b = shrink_pi(Db, Ab, q_dict[args.b], lam[args.b])

    # --- LRT + nula por permutacion + FDR ---------------------------------
    g2 = g2_zonas(Da, Aa, Db, Ab)
    null = nula_permutacion(acc, args.a, args.b, nz, args.n_perm, seed)
    pval = (1.0 + (null >= g2[None, :]).sum(axis=0)) / (1.0 + args.n_perm)
    testable = (Aa >= 30) & (Ab >= 30)
    pval = np.where(testable, pval, 1.0)
    qval, rech = benjamini_hochberg(pval, args.alpha, mask=testable)

    # --- sobredispersion ---------------------------------------------------
    phi_a = cochran_phi(acc, args.a, nz)
    phi_b = cochran_phi(acc, args.b, nz)
    lo_a, hi_a = boot_ic_pi(acc, args.a, nz, args.n_boot, seed)

    print(f"\n  zonas testeables (>=30 acciones en ambas): "
          f"{int(testable.sum())} de {nz}")
    print(f"  sobredispersion de Cochran, mediana: phi_a = "
          f"{np.median(phi_a[testable]):.2f} · phi_b = {np.median(phi_b[testable]):.2f}")
    ancho_bin = 2 * 1.96 * np.sqrt(np.maximum(pi_a * (1 - pi_a), 0) /
                                   np.maximum(Aa, 1))
    ancho_boot = hi_a - lo_a
    infl = np.median(ancho_boot[testable] / np.maximum(ancho_bin[testable], _EPS))
    print(f"  factor de inflacion del IC (bootstrap / binomial ingenuo): {infl:.2f}x")
    if infl > 1.15:
        print("    >> El IC binomial es demasiado angosto. El bootstrap por")
        print("       bloques lo absorbe sin modelar la correlacion.")

    # --- tabla, ordenada por TAMANO DE EFECTO (ADR-28) ---------------------
    print(f"\n  Ordenado por |delta pi|, NO por G2 ni z: ambos escalan con n.\n")
    print(f"  {'zona':<8} {'x':>5} {'y':>5} {'pi_a':>7} {'pi_b':>7} {'delta':>8} "
          f"{'n_a':>7} {'n_b':>7} {'q':>7}")
    print("  " + "-" * 76)
    orden = np.argsort(-np.abs(pi_a - pi_b))
    filas = []
    for z in orden:
        if not testable[z]:
            continue
        cx, cy = sp.zone_centroid(int(z))
        ix, iy = divmod(int(z), sp.ny)
        marca = " *" if rech[z] else ""
        print(f"  z{ix}{iy:<6} {cx:5.0f} {cy:5.0f} {pi_a[z]:7.4f} {pi_b[z]:7.4f} "
              f"{pi_a[z]-pi_b[z]:+8.4f} {int(Aa[z]):>7,} {int(Ab[z]):>7,} "
              f"{qval[z]:7.4f}{marca}")
        filas.append({"zona": int(z), "ix": ix, "iy": iy, "cx": cx, "cy": cy,
                      "pi_a": float(pi_a[z]), "pi_b": float(pi_b[z]),
                      "delta": float(pi_a[z] - pi_b[z]),
                      "n_a": int(Aa[z]), "n_b": int(Ab[z]),
                      "G2": float(g2[z]), "p": float(pval[z]),
                      "q": float(qval[z]), "rechaza": bool(rech[z]),
                      "phi_a": float(phi_a[z]), "phi_b": float(phi_b[z]),
                      "ic_a": [float(lo_a[z]), float(hi_a[z])]})

    # --- lectura por tercio: la resolucion de la paradoja ------------------
    print("\n" + "=" * 92)
    print(" POR TERCIO (marco del club: tercio 0 = nuestra area)")
    print("=" * 92)
    tercio = np.minimum((np.arange(nz) // sp.ny) * 3 // sp.nx, 2)
    nombres = ["propio", "medio", "rival"]
    tercios = []
    for t in range(3):
        m = (tercio == t) & testable
        if not m.any():
            continue
        pa = float((pi_a[m] * Aa[m]).sum() / max(Aa[m].sum(), _EPS))
        pb = float((pi_b[m] * Ab[m]).sum() / max(Ab[m].sum(), _EPS))
        print(f"  tercio {nombres[t]:<7} pi_a={pa:.4f}  pi_b={pb:.4f}  "
              f"delta={pa-pb:+.4f}   ({int(Aa[m].sum()):,} vs {int(Ab[m].sum()):,})")
        tercios.append({"tercio": nombres[t], "pi_a": pa, "pi_b": pb,
                        "delta": pa - pb})

    print("\n  COMO LEER ESTO")
    print("  Si delta > 0 en el tercio RIVAL, la presion extra es alta y deberia")
    print("  acortar las posesiones del rival. Si delta > 0 en el tercio PROPIO,")
    print("  la presion extra ocurre donde el rival ya llego: es reactiva, no")
    print("  roba, y es compatible con conceder posesiones MAS LARGAS.")
    print("  Esa es la tension que este script existe para resolver, y la")
    print("  respuesta esta en el signo por tercio, no en la tasa agregada.")

    res = {
        "club": args.club, "era_a": args.a, "era_b": args.b,
        "malla": f"{sp.nx}x{sp.ny}", "marco": "club (mirror_zone aplicado)",
        "lambda_a": lam[args.a], "lambda_b": lam[args.b],
        "pi_marginal_a": float(Da.sum() / max(Aa.sum(), 1)),
        "pi_marginal_b": float(Db.sum() / max(Ab.sum(), 1)),
        "n_zonas_testeables": int(testable.sum()),
        "n_rechazos_fdr": int(rech.sum()),
        "cochran_phi_mediana_a": float(np.median(phi_a[testable])),
        "cochran_phi_mediana_b": float(np.median(phi_b[testable])),
        "factor_inflacion_ic": float(infl),
        "n_perm": args.n_perm, "n_boot": args.n_boot, "alpha": args.alpha,
        "zonas": filas, "tercios": tercios,
        "familia_fdr": "pi_e(z) — separada de la estandarizacion (ADR-47)",
    }
    out = Path(args.out or f"reports/campo_presion_"
               f"{args.a.lower().replace(' ','')}_{args.b.lower().replace(' ','')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    if args.figura:
        from dtdecoder.plots import zone_heatmap
        d = (pi_a - pi_b).reshape(sp.nx, sp.ny)
        p = zone_heatmap(d, sp, f"delta pi(z): {args.a} - {args.b}",
                         out.with_suffix(".png"), cmap="RdBu_r", fmt="{:+.3f}")
        print(f"figura: {p}")
        print("  (marco del club: el sentido de ataque del CLUB es hacia x=120,")
        print("   asi que el tercio rival queda a la derecha)")


if __name__ == "__main__":
    main()
