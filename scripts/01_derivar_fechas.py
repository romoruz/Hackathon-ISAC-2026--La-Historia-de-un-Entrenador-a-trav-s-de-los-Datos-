#!/usr/bin/env python3
"""
01_derivar_fechas.py — Emite `match_dates.csv` SIN acceso al API.

Reemplaza a 01_derivar_torneos.py. Diferencia clave: en vez de producir un
esquema propio, emite exactamente lo que `eras.load_match_dates` espera, para
que toda la maquinaria de `eras.py` funcione sin tocarse y sea reemplazable por
las fechas reales del API sin cambiar nada aguas abajo.

METODO
------
Los match_id de StatsBomb se asignan por lote. En este dataset se agrupan en
bloques separados por saltos grandes: los de >=25 partidos son torneos
regulares, los chicos son liguillas. Los 8 bloques regulares corresponden, en
orden, a los 8 torneos de la ventana Apertura 2021 - Clausura 2025.

A cada partido se le asigna una fecha SINTETICA: se reparten uniformemente las
fechas del torneo entre los partidos del bloque, ordenados por match_id.

SUPUESTOS (declararlos en el reporte)
-------------------------------------
S1. Los bloques de match_id corresponden a torneos.  [verificable: son 8]
S2. Dentro de un bloque, el orden de match_id ~ orden de jornada.
    NO verificado. Es el supuesto fragil.
S3. Las ventanas de calendario de cada torneo son las de LIGA_MX_CALENDARIO.

CONSECUENCIA DE S2: la unica frontera de DT que cae a media temporada en esta
ventana es Solari -> Ortiz (2022-10-09, dentro de Apertura 2022). Si S2 falla,
esa frontera queda mal y se mezclan dos DT. Por eso el script marca esos
partidos y `--strict` los excluye.

Uso:
  python scripts/01_derivar_fechas.py --events eventos_completos_america.csv \\
      --out data/match_dates.csv
  python scripts/01_derivar_fechas.py --events ... --out ... --strict
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import polars as pl

# Ventanas aproximadas de calendario de Liga MX (fase regular).
# Orden CRONOLOGICO. Clausura (primavera) precede a Apertura (otono) del mismo
# ano, por eso Clausura 2023 va antes que Apertura 2023.
LIGA_MX_CALENDARIO: list[tuple[str, str, str]] = [
    ("Apertura 2021", "2021-07-23", "2021-11-21"),
    ("Clausura 2022", "2022-01-07", "2022-04-24"),
    ("Apertura 2022", "2022-07-01", "2022-10-16"),
    ("Clausura 2023", "2023-01-06", "2023-04-23"),
    ("Apertura 2023", "2023-06-30", "2023-10-22"),
    ("Clausura 2024", "2024-01-12", "2024-04-28"),
    ("Apertura 2024", "2024-07-05", "2024-10-20"),
    ("Clausura 2025", "2025-01-10", "2025-04-27"),
]

# Liguillas: se colocan en las 4 semanas siguientes al cierre de su torneo.
DIAS_LIGUILLA = 28

SALTO_MIN = 2000
MIN_PARTIDOS_TORNEO = 25

# Fronteras de DT que caen a media temporada, POR CLUB.
#
# Esto era una lista global con las fronteras del America. Al correr el script
# sobre Cruz Azul, el aviso reporto "Apertura 2022: Solari -> Ortiz" -- dos
# entrenadores que nunca dirigieron a ese club -- y omitio los CUATRO torneos
# realmente ambiguos de Cruz Azul. Misma clase de error que la heuristica del
# umbral: suposiciones de un club coladas en codigo presentado como general.
#
# Sin --club no se marca nada, en vez de marcar mal.
FRONTERAS_RIESGOSAS: dict[str, list[tuple[str, str, str]]] = {
    "América": [
        ("Apertura 2022", "2022-10-09", "Solari -> Ortiz"),
    ],
    "Cruz Azul": [
        ("Apertura 2022", "2022-08-20", "Aguirre -> Gutierrez"),
        ("Clausura 2023", "2023-02-13", "Gutierrez -> Moreno -> Ferretti"),
        ("Apertura 2023", "2023-08-07", "Ferretti -> Moreno"),
        ("Clausura 2025", "2025-01-22", "Anselmi -> Sanchez"),
    ],
}


def _bloques(ids: list[int], salto_min: int) -> list[int]:
    out, bid = [], 0
    for i, mid in enumerate(ids):
        if i > 0 and (mid - ids[i - 1]) > salto_min:
            bid += 1
        out.append(bid)
    return out


def _reparte(n: int, ini: date, fin: date) -> list[date]:
    """n fechas uniformemente espaciadas en [ini, fin]."""
    if n == 1:
        return [ini]
    span = (fin - ini).days
    return [ini + timedelta(days=round(span * k / (n - 1))) for k in range(n)]


def _umbral_auto(tams: list[int], n_objetivo: int) -> int | None:
    """Umbral que separa torneos de liguillas.

    NO busca "el mayor salto": esa heuristica se calibro sobre el America y
    fallo con Cruz Azul, cuyos tamanos eran

        [21, 18, 17, 17, 17, 17, 17, 17, 6, 4, 3, 3, 1]

    El salto 3 -> 1 en la cola (razon 3.0) supera al salto 17 -> 6 (razon 2.83)
    que es el que separa torneos de liguillas. Eligio la cola.

    Este metodo usa lo que SI se sabe: la ventana tiene exactamente
    `n_objetivo` torneos regulares. Se prueba cada tamano observado como
    umbral y se toma el que produce esa cuenta. Es mas robusto porque no
    depende de la forma de la cola, solo de que los torneos sean los bloques
    mas grandes -- que es la premisa del metodo, no una heuristica adicional.

    Devuelve None si ningun umbral da la cuenta esperada.
    """
    for c in sorted(set(tams)):          # del mas permisivo al mas estricto
        if sum(1 for t in tams if t >= c) == n_objetivo:
            return c
    return None


def derivar(ids: list[int], salto_min: int, min_torneo: int | None,
            club: str | None = None) -> pl.DataFrame:
    bloque = _bloques(ids, salto_min)
    base = pl.DataFrame({"match_id": ids, "bloque": bloque})
    tam = base.group_by("bloque").len().rename({"len": "n"})
    base = base.join(tam, on="bloque").sort("match_id")

    tams = tam["n"].to_list()
    if min_torneo is None:
        min_torneo = _umbral_auto(tams, len(LIGA_MX_CALENDARIO))
        if min_torneo is None:
            sys.exit(
                "ERROR: ningun umbral produce exactamente "
                f"{len(LIGA_MX_CALENDARIO)} bloques regulares.\n"
                f"  tamanos de bloque: {sorted(tams, reverse=True)}\n"
                "  Pasa --min-torneo a mano tras inspeccionar esos tamanos, o\n"
                "  ajusta --salto-min si los bloques mismos estan mal cortados.\n"
                "  NO se escribe archivo."
            )
        n_reg = sum(1 for t in tams if t >= min_torneo)
        menores = [t for t in tams if t < min_torneo]
        margen = min_torneo / max(max(menores), 1) if menores else float("inf")
        print(f"[info] umbral de torneo: {min_torneo} partidos -> {n_reg} torneos "
              f"(separacion {margen:.2f}x respecto al bloque menor siguiente)",
              file=sys.stderr)
        if margen < 1.5:
            print("[AVISO] separacion pequena entre torneos y liguillas: "
                  "verifica los tamanos antes de confiar en la asignacion.",
                  file=sys.stderr)

    regulares = sorted(
        base.filter(pl.col("n") >= min_torneo)["bloque"].unique().to_list()
    )
    if len(regulares) != len(LIGA_MX_CALENDARIO):
        sys.exit(
            f"ERROR: {len(regulares)} bloques regulares detectados, "
            f"{len(LIGA_MX_CALENDARIO)} esperados.\n"
            f"  tamanos de bloque: {sorted(tams, reverse=True)}\n"
            f"  umbral usado: {min_torneo}\n"
            "Ajusta --salto-min / --min-torneo. NO se escribe archivo: unas "
            "fechas mal derivadas producen una tabla de cobertura plausible "
            "pero falsa aguas abajo."
        )

    # bloque -> (torneo, ini, fin)
    ventana: dict[int, tuple[str, date, date]] = {}
    for i, b in enumerate(regulares):
        if i >= len(LIGA_MX_CALENDARIO):
            break
        nom, a, z = LIGA_MX_CALENDARIO[i]
        ventana[b] = (nom, date.fromisoformat(a), date.fromisoformat(z))

    # Liguillas: heredan del torneo regular anterior, desplazadas.
    ultimo: tuple[str, date, date] | None = None
    for b in sorted(base["bloque"].unique().to_list()):
        if b in ventana:
            ultimo = ventana[b]
        elif ultimo is not None:
            nom, _, fin = ultimo
            ventana[b] = (f"{nom} (liguilla)", fin + timedelta(days=7),
                          fin + timedelta(days=DIAS_LIGUILLA))
        else:
            sys.exit(
                f"ERROR: el bloque {b} no pudo mapearse a un torneo. "
                "Revisa --salto-min."
            )

    filas = []
    for b, sub in base.group_by("bloque", maintain_order=True):
        b = b[0] if isinstance(b, tuple) else b
        nom, ini, fin = ventana[b]
        mids = sub.sort("match_id")["match_id"].to_list()
        for mid, f in zip(mids, _reparte(len(mids), ini, fin)):
            filas.append({"match_id": mid, "match_date": f.isoformat(),
                          "torneo": nom, "bloque": b, "fuente": "derivada"})

    res = pl.DataFrame(filas).sort("match_date")

    # Marcar partidos en torneos con cambio de DT a media temporada.
    fronteras = FRONTERAS_RIESGOSAS.get(club or "", [])
    if club and club not in FRONTERAS_RIESGOSAS:
        print(f"[AVISO] no hay fronteras registradas para club='{club}'. "
              "Ningun torneo se marca como ambiguo; eso NO significa que no "
              "los haya. Anade el club a FRONTERAS_RIESGOSAS.", file=sys.stderr)
    riesgo = pl.lit(False)
    for torneo, _corte, _etiq in fronteras:
        riesgo = riesgo | (pl.col("torneo") == torneo)
    return res.with_columns(riesgo.alias("frontera_riesgosa"))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True)
    ap.add_argument("--out", default="data/match_dates.csv")
    ap.add_argument("--salto-min", type=int, default=SALTO_MIN)
    ap.add_argument("--min-torneo", type=int, default=None,
                    help="partidos minimos para considerar un bloque torneo "
                         "(default: deteccion automatica)")
    ap.add_argument("--club", default=None,
                    help="club, para marcar sus torneos con cambio de DT a "
                         "media temporada (ver FRONTERAS_RIESGOSAS)")
    ap.add_argument("--strict", action="store_true",
                    help="excluye partidos en torneos con cambio de DT a media temporada")
    args = ap.parse_args()

    src = Path(args.events)
    if not src.exists():
        sys.exit(f"ERROR: no existe {src}")

    # infer_schema_length=None: la trampa de 04_DATA_CONTRACT §3.6
    ids = (
        pl.read_csv(src, infer_schema_length=None, columns=["match_id"])
        .select("match_id").unique().sort("match_id").to_series().to_list()
    )
    res = derivar(ids, args.salto_min, args.min_torneo, args.club)

    n_riesgo = int(res["frontera_riesgosa"].sum())
    if args.strict and n_riesgo:
        res = res.filter(~pl.col("frontera_riesgosa"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # eras.load_match_dates solo necesita match_id y match_date; el resto es
    # trazabilidad y no estorba.
    res.write_csv(out)

    print(f"escrito: {out}  ({res.height} partidos)")
    print(res.group_by(["bloque", "torneo"]).agg(
        pl.len().alias("n"),
        pl.col("match_date").min().alias("desde"),
        pl.col("match_date").max().alias("hasta"),
    ).sort("bloque"))

    if n_riesgo:
        estado = "EXCLUIDOS" if args.strict else "incluidos y marcados"
        print(f"\n[AVISO] {n_riesgo} partidos en torneo con cambio de DT a media "
              f"temporada ({estado}).")
        for t, c, e in FRONTERAS_RIESGOSAS.get(args.club or "", []):
            print(f"  {t}: {e} el {c}")
    print("\nFECHAS SINTETICAS. Validar con `dtdecoder regimes` antes de reportar.")


if __name__ == "__main__":
    main()
