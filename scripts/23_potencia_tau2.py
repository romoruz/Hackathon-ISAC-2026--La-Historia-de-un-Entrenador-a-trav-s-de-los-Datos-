#!/usr/bin/env python3
"""
23_potencia_tau2.py — ¿puede este diseño detectar variación entre entrenadores?

LA PREGUNTA
-----------
`12_API_STATSBOMB.md` §5.4 la plantea así: *"¿cuánta variación de estilo hay
entre DTs comparada con la variación dentro de un mismo DT? Esa razón dice si
'estilo de entrenador' es siquiera un concepto medible."*

Formalmente es tau^2: la varianza REAL entre unidades, una vez descontado el
ruido de muestreo. El estimador es el de Empirical Bayes normal-normal
(`11_MATEMATICA_APLICADA.md` §3 tiene la misma idea desde el lado del
encogimiento: tau^2/(tau^2+sigma^2) es la confiabilidad, el hermano de lambda).

POR QUÉ ESTE SCRIPT EXISTE ANTES QUE EL ESTIMADOR
-------------------------------------------------
El estimador por momentos está TRUNCADO en cero (`max(..., 0)`). Con muestras
desbalanceadas —y las eras de este proyecto lo son: Jardine tiene 5.5 veces las
posesiones de Ferretti— devuelve exactamente cero con altísima frecuencia AUNQUE
la variación real no sea cero.

Es decir: **`tau^2 = 0` no es evidencia de que no haya diferencias.** Puede ser
el suelo del estimador.

Y la lectura equivocada sería catastrófica para este proyecto: "el estilo de
entrenador no es medible" contradice los seis pilares de validación y el
resultado intra-jugador (9 de 17 cambian, ADR-34). Sería un número plausible y
falso, sin excepción de por medio. El patrón de los doce bugs.

Este script mide el suelo ANTES de reportar nada. Si el umbral mínimo detectable
queda por encima de la variación plausible, el resultado honesto no es "no hay
efecto" sino **"este diseño no tiene potencia para verlo"**.

QUÉ HACE
--------
1. Lee las n reales por era de un artefacto del proyecto.
2. Estima sigma (ruido dentro de era) de los propios datos.
3. Simula la curva de potencia: para cada tau, ¿qué fracción de veces el
   estimador reporta cero?
4. Compara tres estimadores de tau^2 y reporta cuál conviene.

Uso:
    python scripts/23_potencia_tau2.py --demo
    python scripts/23_potencia_tau2.py --parquet data/processed/transitions.parquet
    python scripts/23_potencia_tau2.py --clubes data/processed/transitions.parquet \
                                                data/processed_cruzazul/transitions.parquet

Numerado 23 porque 17 ya lo ocupa `17_fdr_estandarizacion.py`.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
from pathlib import Path

SEED = 20260826


# ======================================================================
# Los tres estimadores de tau^2
# ======================================================================
def tau2_mezclado(m, n, var):
    """El del proyecto de córners (`03_validacion.py::empirical_bayes`).

    MEZCLA PONDERACIONES: promedia las desviaciones ponderando por n —dominado
    por las unidades grandes, que son las menos ruidosas y menos se desvían— y
    resta la media SIN ponderar de se^2 —dominada por las unidades chicas, cuyo
    se^2 es enorme. Las dos mitades empujan hacia abajo.

    Se conserva aquí para poder comparar contra él, no para usarlo.
    """
    mu = np.average(m, weights=n)
    se2 = var / n
    return max(np.average((m - mu) ** 2, weights=n) - se2.mean(), 0.0)


def tau2_dl(m, n, var):
    """DerSimonian–Laird. Pesos consistentes en los dos términos."""
    se2 = var / n
    w = 1.0 / se2
    mu_w = np.sum(w * m) / np.sum(w)
    Q = np.sum(w * (m - mu_w) ** 2)
    k = len(m)
    den = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    return max((Q - (k - 1)) / den, 0.0)


def tau2_mom_simple(m, n, var):
    """Momentos sin ponderar en ninguno de los dos términos.

    Menos eficiente que DL, pero no mezcla escalas. Sirve de control: si los
    tres coinciden, la conclusión no depende del estimador.
    """
    se2 = var / n
    return max(m.var(ddof=1) - se2.mean(), 0.0)


ESTIMADORES = {"mezclado": tau2_mezclado, "DL": tau2_dl, "momentos": tau2_mom_simple}


# ======================================================================
# Curva de potencia
# ======================================================================
def curva_potencia(n, sigma, taus, n_sim=800, rng=None):
    """Para cada tau real, ¿con qué frecuencia cada estimador reporta CERO?

    El modelo generador es el mismo que asume el estimador: theta_j ~ N(0,tau^2)
    y media observada con error sigma/sqrt(n_j). No hay trampa: se le da al
    estimador exactamente el mundo que supone, y aun así falla.
    """
    rng = rng or np.random.default_rng(SEED)
    var = np.full(len(n), sigma ** 2)
    out = {}
    for nombre, f in ESTIMADORES.items():
        ceros, valores = [], []
        for tau in taus:
            z = []
            for _ in range(n_sim):
                theta = rng.normal(0, tau, len(n))
                m = theta + rng.normal(0, sigma / np.sqrt(n))
                z.append(f(m, n, var))
            z = np.array(z)
            ceros.append((z <= 1e-15).mean())
            valores.append(np.median(z))
        out[nombre] = (np.array(ceros), np.array(valores))
    return out


def suelo(taus, ceros, umbral=0.20):
    """Menor tau que el estimador detecta al menos el (1-umbral) de las veces."""
    ok = np.where(ceros <= umbral)[0]
    return taus[ok[0]] if len(ok) else None


# ======================================================================
# Lectura de datos reales
# ======================================================================
def desde_parquet(rutas, grupo, valor, minimo):
    """Une uno o varios parquet de club.

    El hallazgo de la curva de potencia es que lo que manda es el NUMERO DE
    UNIDADES, no su tamano. Con las 4 eras del America el estimador devuelve
    cero un tercio de las veces habiendo variacion real; con las 12 de los dos
    clubes, un 6%. Por eso esta funcion acepta varias rutas.
    """
    import polars as pl

    marcos = []
    for r in rutas:
        t = pl.read_parquet(r)
        if grupo not in t.columns:
            sys.exit(f"no encuentro la columna '{grupo}' en {r}")
        # `poss_uid` es unico por club pero NO necesariamente entre clubes:
        # si dos parquet reusan el mismo id, el group_by los fundiria en una
        # sola posesion. Se prefija con la ruta para garantizar unicidad.
        etiqueta = Path(r).parent.name
        t = t.with_columns(
            (pl.lit(etiqueta + ":") + pl.col("poss_uid").cast(pl.Utf8)).alias("poss_uid"),
            (pl.lit(etiqueta + ":") + pl.col(grupo).cast(pl.Utf8)).alias(grupo),
        )
        # `player_id` es Float64 en un CSV e Int64 en otro (13_CONTEXTO_IA §6):
        # `pl.concat` revienta si no se homogeneiza. Aqui no se usa, asi que se
        # descarta junto con cualquier columna que no haga falta.
        cols = [c for c in (grupo, "poss_uid", valor) if c in t.columns]
        marcos.append(t.select(cols))

    if len({tuple(m.columns) for m in marcos}) != 1:
        sys.exit("los parquet no comparten las mismas columnas necesarias")
    t = pl.concat(marcos, how="vertical")

    if valor == "et":
        # Acciones por posesión: la métrica titular del reporte.
        # La unidad es la POSESIÓN (ADR-07), no el evento.
        g = (t.filter(pl.col(grupo).is_not_null())
              .group_by([grupo, "poss_uid"]).len()
              .rename({"len": "x"}))
    else:
        if valor not in t.columns:
            sys.exit(f"no encuentro la columna '{valor}'")
        g = (t.filter(pl.col(grupo).is_not_null())
              .select([pl.col(grupo), pl.col(valor).alias("x")])
              .drop_nulls())

    agg = (g.group_by(grupo)
            .agg(pl.len().alias("n"), pl.col("x").mean().alias("m"),
                 pl.col("x").var().alias("var"))
            .filter(pl.col("n") >= minimo)
            .sort("n", descending=True))
    return (agg[grupo].to_list(), agg["n"].to_numpy().astype(float),
            agg["m"].to_numpy(), agg["var"].to_numpy())


def demo():
    """Dos escenarios con las n REALES de este proyecto.

    Sirven para ver el contraste: la misma pregunta tiene potencia sobrada sobre
    posesiones y ninguna sobre remates.
    """
    return {
        "posesiones por era (América)":
            (["Jardine", "Solari", "Ortiz", "Herrera"],
             np.array([8694.0, 3680.0, 2400.0, 1500.0])),
        "remates con freeze frame por era (América)":
            (["Jardine", "Solari", "Ortiz", "Herrera"],
             np.array([1240.0, 554.0, 435.0, 225.0])),
        "córners recibidos por equipo (proyecto anterior, 17 equipos)":
            ([f"eq{i}" for i in range(17)],
             np.array([172.0, 173.0] + [30.0] * 15)),
    }


# ======================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet", help="un solo club")
    ap.add_argument("--clubes", nargs="+",
                    help="varios parquet: MAS UNIDADES = mas potencia (ver docstring)")
    ap.add_argument("--grupo", default="coach")
    ap.add_argument("--valor", default="et",
                    help="'et' (acciones por posesión) o una columna numérica")
    ap.add_argument("--min-n", type=int, default=100)
    ap.add_argument("--sigma", type=float,
                    help="ruido dentro de unidad; si se omite, se estima")
    ap.add_argument("--n-sim", type=int, default=800)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    rng = np.random.default_rng(SEED)

    rutas = a.clubes or ([a.parquet] if a.parquet else None)
    if a.demo or not rutas:
        escenarios = demo()
        sigma_defecto = {"posesiones por era (América)": 4.0,
                         "remates con freeze frame por era (América)": 0.30,
                         "córners recibidos por equipo (proyecto anterior, 17 equipos)": 0.02}
        print("MODO DEMO — n reales, sigma supuesto. Corre con --parquet para el real.\n")
        for nombre, (etiquetas, n) in escenarios.items():
            informe(nombre, etiquetas, n, sigma_defecto[nombre], a.n_sim, rng)
        return

    etiquetas, n, m, var = desde_parquet(rutas, a.grupo, a.valor, a.min_n)
    if len(n) < 3:
        sys.exit(f"solo {len(n)} unidades con n>={a.min_n}: tau^2 no es estimable")
    if len(n) < 8:
        print(f"\n  AVISO: {len(n)} unidades. La potencia de tau^2 la manda el NUMERO\n"
              f"  de unidades, no su tamano. Con menos de ~8 el estimador devuelve\n"
              f"  cero con frecuencia alta AUNQUE haya variacion real. Pasa los dos\n"
              f"  clubes con --clubes antes de interpretar el resultado.\n")
    sigma = a.sigma if a.sigma else float(np.sqrt(np.average(var, weights=n)))

    print("=" * 72)
    print(f"UNIDADES OBSERVADAS  ({a.grupo}, valor={a.valor})")
    print("=" * 72)
    print(f"{'unidad':28}{'n':>9}{'media':>10}{'de/sqrt(n)':>13}")
    for e, ni, mi, vi in zip(etiquetas, n, m, var):
        print(f"{e:28}{ni:9,.0f}{mi:10.3f}{np.sqrt(vi/ni):13.4f}")
    print(f"\nsigma dentro de unidad (ponderado): {sigma:.4f}")
    print(f"desbalance n_max/n_min: {n.max()/n.min():.1f}x")

    print("\n" + "=" * 72)
    print("TAU^2 OBSERVADO, CON LOS TRES ESTIMADORES")
    print("=" * 72)
    for nombre, f in ESTIMADORES.items():
        t2 = f(m, n, var)
        conf = t2 / (t2 + sigma ** 2 / np.median(n))
        print(f"  {nombre:10} tau^2 = {t2:.3e}   tau = {np.sqrt(t2):.4f}   "
              f"confiabilidad mediana = {conf:.3f}")

    informe(f"{a.grupo} / {a.valor}", etiquetas, n, sigma, a.n_sim, rng, m=m, var=var)


def informe(nombre, etiquetas, n, sigma, n_sim, rng, m=None, var=None):
    print("\n" + "=" * 72)
    print(f"CURVA DE POTENCIA — {nombre}")
    print("=" * 72)
    print(f"unidades: {len(n)}   n: {n.min():,.0f}–{n.max():,.0f}   "
          f"desbalance {n.max()/n.min():.1f}x   sigma={sigma:.4f}")

    ruido_tipico = sigma / np.sqrt(np.median(n))
    taus = ruido_tipico * np.array([0, .25, .5, 1, 2, 4, 8])
    res = curva_potencia(n, sigma, taus, n_sim=n_sim, rng=rng)

    print(f"\n{'tau real':>11}{'tau/ruido':>11}", end="")
    for k in ESTIMADORES:
        print(f"{'% ceros ' + k:>18}", end="")
    print("\n" + "-" * 72)
    for i, tau in enumerate(taus):
        print(f"{tau:11.5f}{tau/ruido_tipico if ruido_tipico else 0:11.2f}", end="")
        for k in ESTIMADORES:
            print(f"{100*res[k][0][i]:17.0f}%", end="")
        print()

    print("\nSUELO DE DETECCIÓN (menor tau visto en >=80% de las simulaciones):")
    for k in ESTIMADORES:
        s = suelo(taus, res[k][0])
        if s is None:
            print(f"  {k:10} ninguno de los tau probados — sin potencia útil")
        else:
            print(f"  {k:10} tau >= {s:.5f}  ({s/ruido_tipico:.1f}x el ruido de muestreo)")

    print("\nCÓMO LEER ESTO")
    print("  El valor de la fila tau=0 es la tasa de acierto cuando NO hay")
    print("  variación real: ahí un 100% de ceros es lo correcto.")
    print("  En las filas siguientes SÍ hay variación, así que cada '% ceros'")
    print("  es la probabilidad de concluir 'no hay diferencias' cuando las hay.")
    if m is not None:
        print("\n  Si tu tau^2 observado cae por debajo del suelo, el resultado")
        print("  reportable es 'este diseño no tiene potencia para verlo',")
        print("  NUNCA 'el estilo de entrenador no es medible'.")


if __name__ == "__main__":
    main()
