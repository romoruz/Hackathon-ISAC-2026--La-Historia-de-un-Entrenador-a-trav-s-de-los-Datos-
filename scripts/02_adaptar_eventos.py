#!/usr/bin/env python3
"""
02_adaptar_eventos.py — JSON crudo del API -> el MISMO esquema del volcado.

Objetivo de diseno: que `src/dtdecoder/` no se entere de nada. El archivo
que sale de aqui es intercambiable con `eventos_completos_<club>.csv`, asi
que `phase0` corre sin tocar una linea.

Uso:
    # el club de la prueba de regresion, en CSV para comparar 1:1
    python scripts/02_adaptar_eventos.py --club "América" --formato csv

    # el resto de la liga, en parquet (mucho mas chico y rapido)
    python scripts/02_adaptar_eventos.py --todos --formato parquet

    # solo comparar esquemas contra el volcado viejo, sin escribir nada
    python scripts/02_adaptar_eventos.py --club "América" --solo-esquema \
        --referencia eventos_completos_america.csv
"""
from __future__ import annotations

import argparse
import csv as _csv
import gzip
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _alcance import avisar_desconocidas, es_regular  # noqa: E402

# columnas que el contrato de datos declara REQUERIDAS (04_DATA_CONTRACT §2)
REQUERIDAS = ["id", "index", "match_id", "period", "minute", "second",
              "type", "team", "possession", "possession_team",
              "play_pattern", "location"]


def sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def aplanar(obj: dict, prefijo: str = "") -> dict:
    """Replica el aplanado de statsbombpy.

    Un dict {id, name} colapsa a  <campo> = name  y  <campo>_id = id.
    Un dict con mas llaves se recurre con prefijo.
    Las listas se dejan tal cual (location) o como JSON (freeze_frame).
    """
    out: dict = {}
    for k, v in obj.items():
        clave = f"{prefijo}{k}"
        if isinstance(v, dict):
            llaves = set(v.keys())
            if llaves <= {"id", "name"} and "name" in llaves:
                out[clave] = v.get("name")
                if "id" in v:
                    out[f"{clave}_id"] = v.get("id")
            else:
                out.update(aplanar(v, f"{clave}_"))
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                out[clave] = json.dumps(v, ensure_ascii=False)
            else:
                out[clave] = v
        else:
            out[clave] = v
    return out


def leer_indice(raw: Path) -> dict:
    """match_id -> (home, away, fecha, jornada, etapa, season_id)"""
    idx = {}
    with (raw / "indice_partidos.csv").open(encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            idx[int(r["match_id"])] = r
    return idx


def eventos_de(raw: Path, mid: int) -> list[dict]:
    p = raw / "events" / f"{mid}.json.gz"
    if not p.exists():
        return []
    crudo = json.loads(gzip.decompress(p.read_bytes()))
    return list(crudo.values()) if isinstance(crudo, dict) else crudo


def unificar_partes(partes, requeridas) -> tuple[bool, list[str], int, int]:
    """Deja todas las partes con EL MISMO esquema Arrow. Devuelve
    (ok, columnas_vacias, n_partes_reescritas, n_columnas).

    POR QUE NO SE HACE CON PANDAS
    -----------------------------
    La primera version anadia la columna que faltaba como
    `pd.Series([None]*n, dtype="object")` y la casteaba al dtype de pandas
    visto en otra parte. Funcionaba con pandas 3.0 --donde las columnas de
    texto van respaldadas por Arrow y una `object` vacia sale a parquet como
    `string`-- y NO con pandas 2.x, donde esa misma columna sale tipada
    `null`. Mismo codigo, mismo pyarrow, resultado distinto segun la version
    de pandas. Es el hermano exacto del cambio de default de
    `infer_schema_length` (08_REPRODUCIBILITY §2), y se detecto porque el
    banco de pruebas corrio en las dos versiones.

    El formato de destino es Arrow y Arrow tiene tipos explicitos: la
    unificacion se hace ahi y pandas no participa.

    Casos que cubre:
      * columna ausente en una parte  -> se anade con `pa.nulls(n, type=T)`
        del tipo que tiene donde SI existe;
      * columna tipada `null` en una parte y `string` en otra -> promocion;
      * `player_id` entero en una parte y `double` en otra porque ahi tenia
        nulos -> promocion a double. La version anterior ni lo veia;
      * columna vacia en TODAS las partes -> se tipa `string`, y se devuelve
        en la lista para poder avisar.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    esquemas = [pq.ParquetFile(p).schema_arrow for p in partes]
    try:
        unificado = pa.unify_schemas(esquemas, promote_options="permissive")
    except TypeError:                      # pyarrow < 14
        unificado = pa.unify_schemas(esquemas)
    except pa.ArrowInvalid as exc:
        print(f"\nERROR: las partes tienen tipos incompatibles: {exc}")
        return False, [], 0, 0

    campos = {c.name: (pa.string() if pa.types.is_null(c.type) else c.type)
              for c in unificado}
    vacias = [c.name for c in unificado if pa.types.is_null(c.type)]
    faltan_req = [c for c in requeridas if c not in campos]
    if faltan_req:
        print(f"\nERROR: faltan columnas requeridas tras unificar: {faltan_req}")
        return False, vacias, 0, len(campos)

    orden = list(requeridas) + sorted(c for c in campos if c not in requeridas)
    esquema_final = pa.schema([(c, campos[c]) for c in orden])

    n_reparadas = 0
    for p in partes:
        tabla = pq.read_table(p)
        if tabla.schema.equals(esquema_final):
            continue
        cols = []
        for campo in esquema_final:
            if campo.name in tabla.column_names:
                col = tabla.column(campo.name)
                if not col.type.equals(campo.type):
                    col = col.cast(campo.type)
            else:
                col = pa.chunked_array([pa.nulls(tabla.num_rows, type=campo.type)])
            cols.append(col)
        pq.write_table(pa.Table.from_arrays(cols, schema=esquema_final), p)
        n_reparadas += 1
        del tabla

    # Comprobacion final: un solo esquema y ninguna columna `null`.
    import pyarrow.dataset as pads

    esq = pads.dataset(str(Path(partes[0]).parent), format="parquet").schema
    if len(esq.names) != len(orden):
        print(f"\nERROR: el dataset expone {len(esq.names)} columnas y se "
              f"esperaban {len(orden)}.")
        return False, vacias, n_reparadas, len(orden)
    nulas = [n for n, t in zip(esq.names, esq.types) if str(t) == "null"]
    if nulas:
        # Una columna `null` en el dataset es exactamente el fallo que esta
        # funcion existe para evitar: los filtros sobre ella devuelven vacio
        # sin lanzar un error.
        print(f"\nERROR: {len(nulas)} columnas quedaron tipadas `null`: "
              f"{nulas[:10]}")
        print("  Un filtro sobre ellas devolveria vacio EN SILENCIO.")
        return False, vacias, n_reparadas, len(orden)
    return True, vacias, n_reparadas, len(orden)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw_api"))
    ap.add_argument("--out", type=Path, default=Path("data/api"))
    ap.add_argument("--club", default=None)
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--formato", choices=["csv", "parquet"], default="parquet")
    ap.add_argument("--solo-esquema", action="store_true")
    ap.add_argument("--referencia", type=Path, default=None,
                    help="volcado viejo contra el que comparar columnas")
    ap.add_argument("--excluir-liguilla", action="store_true",
                    help="deja fuera etapas que no son fase regular")
    ap.add_argument("--excluir-temporadas", type=int, nargs="*", default=[],
                    help="p.ej. 351 (temporada en curso)")
    ap.add_argument("--ids-de", type=Path, default=None,
                    help="usa EXACTAMENTE los match_id de este CSV. "
                         "Obligatorio para la prueba de regresion: si no, "
                         "comparas 230 partidos contra 175.")
    ap.add_argument("--muestra-esquema", type=int, default=30,
                    help="partidos a leer para comparar esquemas. Con 1 las "
                         "banderas de eventos raros salen como ausentes")
    ap.add_argument("--filas-por-parte", type=int, default=400_000,
                    dest="filas_por_parte",
                    help="tamano de cada parte en filas. Con parquet, cada "
                         "parte se escribe y se libera: la memoria no crece "
                         "con el numero de partidos")
    args = ap.parse_args()

    if not args.club and not args.todos:
        print("Falta --club o --todos"); return 1

    # pyarrow se comprueba AQUI y no dos horas despues, al escribir.
    # `pandas.to_parquet` no trae motor propio: sin pyarrow revienta con un
    # ImportError al final del proceso, con todo el trabajo hecho y perdido.
    if args.formato == "parquet" and not args.solo_esquema:
        try:
            import pyarrow  # noqa: F401
            import pyarrow.dataset  # noqa: F401
        except ImportError:
            print("Falta `pyarrow`, que es el motor que pandas usa para "
                  "escribir parquet.\n"
                  "  En el entorno del API:\n"
                  "      source .venv-sb/bin/activate\n"
                  "      uv pip install pyarrow\n"
                  "  (o --formato csv, mucho mas pesado en disco)")
            return 1

    idx = leer_indice(args.raw)
    if args.excluir_liguilla:
        avisar_desconocidas((r["stage"] for r in idx.values()),
                            "indice_partidos.csv")

    def quiero(r) -> bool:
        if int(r["season_id"]) in args.excluir_temporadas:
            return False
        # La regla vive en scripts/_alcance.py y la comparte
        # 01_construir_eras.py. NO reimplementarla aqui: si las dos divergen,
        # las eras reclaman partidos que no estan en los eventos.
        if args.excluir_liguilla and not es_regular(r["stage"]):
            return False
        if args.club:
            return args.club in (r["home_team"], r["away_team"])
        return True

    mids = sorted(int(m) for m, r in idx.items() if quiero(r))
    if args.ids_de:
        ref = set(pd.read_csv(args.ids_de, usecols=["match_id"]).match_id.astype(int))
        antes = len(mids)
        mids = sorted(set(mids) & ref)
        print(f"--ids-de: {antes} -> {len(mids)} partidos "
              f"({len(ref - set(mids))} de la referencia no quedaron)")
    print(f"partidos seleccionados: {len(mids)}")
    disponibles = [m for m in mids if (args.raw / "events" / f"{m}.json.gz").exists()]
    print(f"con eventos descargados: {len(disponibles)}")
    if not disponibles:
        print("Nada que hacer. ¿Ya termino la descarga?"); return 1

    # ---- esquema con una muestra, antes de procesar millones de filas
    ev_muestra = []
    for m in disponibles[: max(1, args.muestra_esquema)]:
        ev_muestra.extend(aplanar(e) for e in eventos_de(args.raw, m))
    muestra = pd.DataFrame(ev_muestra)
    print(f"esquema leido de {min(len(disponibles), args.muestra_esquema)} "
          f"partidos ({len(muestra):,} eventos)")
    faltan = [c for c in REQUERIDAS if c not in muestra.columns]
    if faltan:
        print(f"\nFALTAN COLUMNAS REQUERIDAS: {faltan}")
        print("El contrato de datos no se cumple. NO sigas."); return 1
    print(f"columnas en la muestra: {len(muestra.columns)}  (requeridas: OK)")

    if args.referencia and args.referencia.exists():
        viejas = set(pd.read_csv(args.referencia, nrows=5).columns)
        nuevas = set(muestra.columns)
        print(f"\n  referencia: {len(viejas)} columnas | nuevo: {len(nuevas)}")
        solo_v = sorted(viejas - nuevas)
        solo_n = sorted(nuevas - viejas)
        if solo_v:
            print(f"  SOLO en el volcado viejo ({len(solo_v)}): {solo_v[:25]}")
            criticas = [c for c in solo_v if c in REQUERIDAS
                        or c.startswith(("obv", "shot_statsbomb"))]
            if criticas:
                print(f"  >>> CRITICAS: {criticas}")
        if solo_n:
            print(f"  SOLO en el nuevo ({len(solo_n)}): {solo_n[:25]}")
        if not solo_v:
            print("  el nuevo cubre todas las columnas del viejo.")

    if args.solo_esquema:
        print("\n--solo-esquema: termino aqui."); return 0

    # ---- proceso por lotes ------------------------------------------------
    args.out.mkdir(parents=True, exist_ok=True)
    etiqueta = (sin_acentos(args.club).lower().replace(" ", "_")
                if args.club else "ligamx")

    def textualizar(df):
        """Listas y dicts a texto: parquet no traga columnas mixtas."""
        for c in df.columns:
            if df[c].map(lambda x: isinstance(x, (list, dict))).any():
                df[c] = df[c].map(
                    lambda x: str(x) if isinstance(x, (list, dict)) else x
                )
        return df

    if args.formato == "csv":
        # Un solo archivo. Se conserva para la prueba de regresion contra el
        # volcado viejo, que compara 1:1 y necesita un CSV equivalente.
        lotes, buf, n_ev = [], [], 0
        for i, mid in enumerate(disponibles, 1):
            buf.extend(aplanar(e) for e in eventos_de(args.raw, mid))
            if len(buf) >= args.filas_por_parte or i == len(disponibles):
                lotes.append(pd.DataFrame(buf))
                n_ev += len(lotes[-1])
                print(f"  {i}/{len(disponibles)} partidos, {n_ev:,} eventos")
                buf = []
        df = pd.concat(lotes, ignore_index=True) if len(lotes) > 1 else lotes[0]
        del lotes
        df = df.sort_values(["match_id", "index"], kind="stable").reset_index(drop=True)
        dst = args.out / f"eventos_api_{etiqueta}.csv"
        df.to_csv(dst, index=False)
        n_total, n_equipos, n_partidos = len(df), df["team"].nunique(), df["match_id"].nunique()
        mids_escritos = sorted(int(m) for m in df["match_id"].unique())
        del df
        print(f"\nescrito {dst}  ({n_total:,} eventos, "
              f"{dst.stat().st_size / 1e6:.0f} MB)")
    else:
        # PARQUET POR PARTES.
        #
        # POR QUE NO UN SOLO ARCHIVO
        # --------------------------
        # El America son 566,083 eventos en 170 partidos. La liga sin liguilla
        # ni temporada 351 son 1,530 partidos: ~5.1 millones de eventos con 178
        # columnas casi todas `object` en pandas. El `pd.concat` final de la
        # version anterior los materializaba TODOS a la vez. No lanza una
        # excepcion: el kernel mata el proceso.
        #
        # EL PROBLEMA QUE LAS PARTES CREAN Y HAY QUE CERRAR
        # -------------------------------------------------
        # Cada parte sale de un `pd.DataFrame(buf)`, asi que sus columnas son
        # las que aparecieron EN SUS PARTIDOS. Una bandera de evento raro
        # (`goalkeeper_punched_out`, `bad_behaviour_card`) sale en la parte 3 y
        # no en la 7. Al leer el directorio:
        #   - o polars choca por esquemas distintos,
        #   - o unifica y la columna queda tipada `Null`, y entonces cualquier
        #     filtro sobre ella devuelve VACIO sin lanzar un error.
        # Lo segundo es el bug de `infer_schema_length` de 04_DATA_CONTRACT
        # §3.6 por otra puerta. Por eso las partes se UNIFICAN al final y se
        # verifica que el directorio tiene un esquema unico.
        dst = args.out / f"eventos_api_{etiqueta}"
        if dst.exists():
            for viejo in sorted(dst.glob("parte_*.parquet")):
                viejo.unlink()
        dst.mkdir(parents=True, exist_ok=True)

        columnas: set[str] = set()      # solo para el aviso de progreso
        partes, buf, n_total, mids_escritos, equipos = [], [], 0, [], set()
        for i, mid in enumerate(disponibles, 1):
            buf.extend(aplanar(e) for e in eventos_de(args.raw, mid))
            if len(buf) >= args.filas_por_parte or i == len(disponibles):
                df = pd.DataFrame(buf)
                buf = []
                df = df.sort_values(["match_id", "index"],
                                    kind="stable").reset_index(drop=True)
                df = textualizar(df)
                columnas |= set(df.columns)
                p = dst / f"parte_{len(partes):03d}.parquet"
                df.to_parquet(p, index=False)
                partes.append(p)
                n_total += len(df)
                mids_escritos.extend(int(m) for m in df["match_id"].unique())
                equipos |= set(df["team"].dropna().unique())
                print(f"  {i}/{len(disponibles)} partidos, {n_total:,} eventos "
                      f"-> {p.name}")
                del df

        # --- unificacion de esquema entre partes --------------------------
        ok, vacias, n_reparadas, n_cols = unificar_partes(partes, REQUERIDAS)
        if not ok:
            return 1
        print(f"\nesquema unificado: {n_cols} columnas, "
              f"{n_reparadas}/{len(partes)} partes reescritas")
        if vacias:
            print(f"  {len(vacias)} columna(s) vacias en TODO el volcado, "
                  f"tipadas string: {vacias[:8]}"
                  + (" ..." if len(vacias) > 8 else ""))

        n_equipos, n_partidos = len(equipos), len(set(mids_escritos))
        mids_escritos = sorted(set(mids_escritos))
        mb = sum(p.stat().st_size for p in partes) / 1e6
        print(f"\nescrito {dst}/  ({len(partes)} partes, {n_total:,} eventos, "
              f"{mb:.0f} MB)")
        print(f"  --src para el pipeline: {dst}")

    print(f"equipos: {n_equipos}  partidos: {n_partidos}")

    # ---- fechas, EN LA MISMA CORRIDA -------------------------------------
    # El volcado de eventos no trae fecha (04_DATA_CONTRACT §3.7) y
    # `build_transitions` construye su salida con una lista EXPLICITA de
    # columnas, asi que inyectar `match_date` en el evento no llegaria a
    # `transitions.parquet`; y si llegara, chocaria con la `match_date` que ya
    # aporta `eras.attach_coach` y polars la renombraria `match_date_right` en
    # silencio. Por eso la fecha viaja aparte.
    #
    # Lo que si se arregla aqui: que el archivo de fechas lo escriba el MISMO
    # proceso que escribio los eventos, con EXACTAMENTE los match_id que
    # sobrevivieron al alcance. Un CSV generado a mano en otra corrida puede
    # quedar desincronizado sin que nada avise.
    mids_escritos = sorted(set(mids_escritos))
    fdst = args.out / f"match_dates_{etiqueta}.csv"
    faltan_fecha = []
    with fdst.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["match_id", "match_date"])
        for m in mids_escritos:
            fecha = (idx.get(m) or {}).get("match_date", "")
            if not fecha or fecha == "None":
                faltan_fecha.append(m)
                continue
            w.writerow([m, fecha[:10]])
    print(f"escrito {fdst}  ({len(mids_escritos) - len(faltan_fecha):,} fechas)")

    if faltan_fecha:
        # No se escribe un archivo incompleto y se sigue: `phase0` uniria por
        # la izquierda y esos partidos saldrian con `coach` nulo, que es
        # indistinguible de un hueco de era real.
        fdst.unlink(missing_ok=True)
        print(f"\nERROR: {len(faltan_fecha)} partidos SIN fecha en el indice: "
              f"{faltan_fecha[:10]}")
        print("  El archivo de fechas se borro: incompleto es peor que ausente.")
        print("  Revisa data/raw_api/indice_partidos.csv antes de correr phase0.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
