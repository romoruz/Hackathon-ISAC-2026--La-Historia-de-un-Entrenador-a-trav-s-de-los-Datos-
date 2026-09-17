#!/usr/bin/env python3
"""
34_sonda_cierre.py — lo que hay que saber ANTES de escribir el codigo de cierre.

Solo lectura. No imprime valores licenciados: solo esquemas, tipos, conteos y
estructura. La salida se pega completa en el chat.

Cada bloque va en su propio try: si uno falla, los demas corren igual y el
fallo queda impreso (un fallo tambien es informacion).

Uso:
    python scripts/34_sonda_cierre.py 2>&1 | tee reports/sonda_cierre.txt
"""
from __future__ import annotations

import glob
import importlib
import importlib.util
import inspect
import json
import traceback
from pathlib import Path

import polars as pl

RAIZ = Path(__file__).resolve().parent.parent
EVENTOS = RAIZ / "data/api/eventos_api_ligamx"
INDICE = RAIZ / "data/raw_api/indice_partidos.csv"
PRIOR = RAIZ / "data/prior_liga"


def bloque(titulo):
    def deco(fn):
        def run():
            print("\n" + "=" * 78 + f"\n{titulo}\n" + "=" * 78)
            try:
                fn()
            except Exception:
                print("  !! FALLO EN ESTE BLOQUE:")
                print("  " + traceback.format_exc().replace("\n", "\n  "))
        return run
    return deco


def tipo_de(v, prof=0):
    """Estructura de un valor sin imprimir su contenido."""
    if prof > 3:
        return "..."
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {tipo_de(x, prof+1)}" for k, x in list(v.items())[:12]) + "}"
    if isinstance(v, (list, tuple)):
        return f"list[{len(v)}]<{tipo_de(v[0], prof+1) if v else ''}>"
    if isinstance(v, pl.Series):
        return f"Series[{v.dtype}, {len(v)}]"
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in "[{":
            try:
                return f"str(JSON)->{tipo_de(json.loads(s), prof+1)}"
            except Exception:
                return f"str(len={len(v)}, empieza con {s[:1]!r})"
        return f"str(len={len(v)})"
    return type(v).__name__


def lf_eventos():
    f = sorted(glob.glob(str(EVENTOS / "*.parquet")))
    if not f:
        raise FileNotFoundError(f"sin parquet en {EVENTOS}")
    return pl.scan_parquet(f), f


@bloque("1. EVENTOS DEL API: archivos y esquema")
def b1():
    lf, f = lf_eventos()
    print(f"  {len(f)} archivos · primero: {Path(f[0]).name}")
    sch = lf.collect_schema()
    print(f"  {len(sch)} columnas; filas: {lf.select(pl.len()).collect().item():,}")
    for n, t in sch.items():
        print(f"    {n:<40} {t}")


@bloque("2. EVENTOS: conteos que deciden el diseño")
def b2():
    lf, _ = lf_eventos()
    cols = lf.collect_schema().names()
    for c in ("play_pattern", "type", "pass_type", "shot_type", "shot_outcome",
              "pass_technique", "pass_height", "shot_body_part", "period"):
        if c in cols:
            t = lf.group_by(c).agg(pl.len()).sort("len", descending=True).collect()
            print(f"\n  {c}: {t.height} valores")
            for r in t.head(25).iter_rows():
                print(f"    {str(r[0]):<34} {r[1]:>10,}")
        else:
            print(f"\n  {c}: NO EXISTE")
    for c in ("minute", "second", "timestamp", "duration", "home_team", "away_team",
              "tactics", "substitution_replacement", "substitution_outcome",
              "shot_statsbomb_xg", "obv_total_net", "obv_for_net", "pass_end_location",
              "counterpress", "position", "player_id", "possession", "index"):
        print(f"  ¿{c}? {'sí' if c in cols else 'NO'}")


@bloque("3. EVENTOS: estructura de location / freeze frame / tactics (sin valores)")
def b3():
    lf, _ = lf_eventos()
    cols = lf.collect_schema().names()
    tiros = lf.filter(pl.col("type") == "Shot")
    for c in ("location", "shot_end_location", "shot_freeze_frame", "pass_end_location"):
        if c not in cols:
            print(f"  {c}: NO EXISTE"); continue
        src = tiros if c.startswith("shot") else lf
        v = src.select(pl.col(c)).drop_nulls().head(1).collect()
        if v.height:
            print(f"  {c}: dtype {v.schema[c]} · estructura {tipo_de(v[c][0])}")
    if "shot_freeze_frame" in cols:
        r = tiros.select(
            pl.len().alias("tiros"),
            pl.col("shot_freeze_frame").is_not_null().sum().alias("con_freeze"),
            (pl.col("shot_outcome") == "Goal").sum().alias("goles") if "shot_outcome" in cols else pl.lit(None),
        ).collect()
        print(f"  {r.to_dicts()[0]}")
        if "play_pattern" in cols:
            t = (tiros.group_by("play_pattern")
                 .agg(pl.len().alias("tiros"),
                      pl.col("shot_freeze_frame").is_not_null().sum().alias("con_freeze"),
                      (pl.col("shot_outcome") == "Goal").sum().alias("goles"))
                 .sort("tiros", descending=True).collect())
            print("  tiros por play_pattern:")
            for x in t.iter_rows(named=True):
                print(f"    {x}")
    if "tactics" in cols:
        v = lf.filter(pl.col("tactics").is_not_null()).select("type", "tactics").head(1).collect()
        if v.height:
            print(f"  tactics ({v['type'][0]}): {tipo_de(v['tactics'][0])}")


@bloque("4. BALON PARADO: tamaños de muestra por equipo")
def b4():
    lf, _ = lf_eventos()
    cols = lf.collect_schema().names()
    if "pass_type" in cols:
        t = (lf.filter(pl.col("pass_type") == "Corner").group_by("team")
             .agg(pl.len().alias("corners")).sort("corners").collect())
        print(f"  corners: total {t['corners'].sum():,}; por equipo min {t['corners'].min()} "
              f"max {t['corners'].max()} ({t.height} equipos)")
    if "play_pattern" in cols and "possession" in cols:
        p = (lf.filter(pl.col("play_pattern").is_in(["From Corner", "From Free Kick", "From Throw In"]))
             .group_by("play_pattern")
             .agg(pl.struct("match_id", "possession").n_unique().alias("posesiones"))
             .collect())
        print("  posesiones por patron:", p.to_dicts())


@bloque("5. SUSTITUCIONES Y ALINEACIONES")
def b5():
    lf, _ = lf_eventos()
    cols = lf.collect_schema().names()
    t = (lf.filter(pl.col("type").is_in(["Substitution", "Starting XI", "Tactical Shift"]))
         .group_by("type").agg(pl.len()).collect())
    print("  ", t.to_dicts())
    sub = [c for c in cols if c.startswith("substitution")]
    print("  columnas substitution*:", sub)
    for d in ("lineups", "raw_api/lineups"):
        fs = sorted(glob.glob(str(RAIZ / "data" / d / "*")))
        print(f"  data/{d}: {len(fs)} archivos" + (f" · ej. {Path(fs[0]).name}" if fs else ""))
        if fs:
            p = Path(fs[0])
            try:
                import gzip
                txt = gzip.open(p, "rt").read() if p.suffix == ".gz" else p.read_text()
                print(f"    estructura: {tipo_de(json.loads(txt))}")
            except Exception as e:
                print(f"    no se pudo leer: {e}")


@bloque("6. INDICE DE PARTIDOS")
def b6():
    if not INDICE.exists():
        print(f"  NO EXISTE {INDICE}"); return
    d = pl.read_csv(INDICE, infer_schema_length=None)
    print(f"  {d.height} filas")
    for n, t in d.schema.items():
        print(f"    {n:<30} {t}  ej. {tipo_de(d[n][0])}")
    for c in d.columns:
        if d[c].dtype == pl.Utf8 and d[c].n_unique() < 30:
            print(f"  {c}: {sorted(map(str, d[c].unique().to_list()))}")


@bloque("7. TRANSICIONES DE LA LIGA: poss_uid y fases")
def b7():
    t = pl.scan_parquet(sorted(glob.glob(str(PRIOR / "*.parquet"))))
    muestra = t.select("poss_uid").head(3).collect()["poss_uid"].to_list()
    print(f"  poss_uid dtype {t.collect_schema()['poss_uid']} · forma {[tipo_de(x) for x in muestra]}")
    print(f"  ¿contiene '_'? {['_' in str(x) for x in muestra]}")
    ph = t.group_by("phase").agg(pl.len()).sort("len", descending=True).collect()
    print("  phase:", ph.to_dicts())
    # fase de la PRIMERA transicion contra play_pattern del evento
    lf, _ = lf_eventos()
    if "_" in str(muestra[0]):
        prim = (t.sort(["poss_uid", "event_index"]).group_by("poss_uid")
                .agg(pl.col("phase").first(), pl.col("match_id").first())
                .with_columns(pl.col("poss_uid").cast(pl.Utf8).str.split("_").list.last()
                              .cast(pl.Int64, strict=False).alias("possession")))
        pp = (lf.group_by(["match_id", "possession"]).agg(pl.col("play_pattern").first())
              .with_columns(pl.col("match_id").cast(pl.Int64), pl.col("possession").cast(pl.Int64)))
        j = (prim.with_columns(pl.col("match_id").cast(pl.Int64))
             .join(pp, on=["match_id", "possession"], how="left").collect())
        print(f"  unidas: {j['play_pattern'].is_not_null().sum():,} de {j.height:,}")
        x = j.group_by(["phase", "play_pattern"]).agg(pl.len()).sort(["phase", "len"], descending=[False, True])
        for r in x.iter_rows():
            print(f"    {str(r[0]):<12} {str(r[1]):<20} {r[2]:>9,}")


@bloque("8. CONFIG")
def b8():
    print((RAIZ / "config/default.yaml").read_text())


@bloque("9. API DE dtdecoder QUE USARIA EL CIERRE")
def b9():
    for mod in ("dtdecoder.xg_remate", "dtdecoder.geometria_remate", "dtdecoder.grid",
                "dtdecoder.absorbing", "dtdecoder.eras", "dtdecoder.inference",
                "dtdecoder.estimate", "dtdecoder.ingest"):
        try:
            m = importlib.import_module(mod)
        except Exception as e:
            print(f"  {mod}: NO IMPORTA ({e})"); continue
        print(f"\n  {mod}")
        for n, o in inspect.getmembers(m):
            if n.startswith("_"):
                continue
            propio = (inspect.isfunction(o) or inspect.isclass(o)) and \
                getattr(o, "__module__", None) == mod
            try:
                if propio:
                    doc = (inspect.getdoc(o) or "").split("\n")[0][:70]
                    print(f"    {n}{inspect.signature(o)}  # {doc}")
                elif n.isupper():
                    print(f"    {n} = {o!r}"[:160])
            except (TypeError, ValueError):
                print(f"    {n}")
    from dtdecoder.config import Config
    s = importlib.util.spec_from_file_location("m08", RAIZ / "scripts/08_ic_derivados.py")
    m08 = importlib.util.module_from_spec(s); s.loader.exec_module(m08)
    sp = m08._space(Config.load(str(RAIZ / "config/default.yaml")))
    print(f"\n  StateSpace: nx={sp.nx} ny={sp.ny} fases={sp.phases} "
          f"n_transient={sp.n_transient} n_states={sp.n_states} absorbentes={sp.absorbing}")


@bloque("10. INVENTARIO")
def b10():
    print("  scripts:", sorted(p.name for p in (RAIZ / "scripts").glob("[0-9]*.py")))
    print("  src/dtdecoder:", sorted(p.name for p in (RAIZ / "src/dtdecoder").glob("*.py")))
    print("  reports (sin pares):", sorted(p.name for p in (RAIZ / "reports").glob("*.json")
                                           if not p.name.startswith(("ic_", "plantel_", "calibracion_",
                                           "campo_", "presion_", "nivel_", "huella_"))))
    print("  reports/_pre_api:", len(list((RAIZ / "reports/_pre_api").glob("*"))), "archivos")
    print("  ¿sklearn?", importlib.util.find_spec("sklearn") is not None,
          "· ¿matplotlib?", importlib.util.find_spec("matplotlib") is not None,
          "· ¿scipy?", importlib.util.find_spec("scipy") is not None)


if __name__ == "__main__":
    for b in (b1, b2, b3, b4, b5, b6, b7, b8, b9, b10):
        b()
