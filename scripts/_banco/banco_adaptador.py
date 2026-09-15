"""Banco de pruebas del adaptador por partes.

Genera un `data/raw_api` falso con la trampa que importa: una columna que SOLO
aparece en los partidos del final, de modo que la primera parte no la tiene.
Si la unificacion de esquema no funciona, el dataset queda con esquemas
distintos entre partes o con una columna `null`, y el script debe detectarlo.
"""
import csv
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

def _verifica_polars(d: Path) -> None:
    """La lectura del directorio de partes con el motor del pipeline."""
    import polars as pl

    esquema = pl.scan_parquet(str(d / "*.parquet")).collect_schema()
    assert esquema["goalkeeper_type"] != pl.Null, (
        "polars ve `goalkeeper_type` como Null: un filtro sobre ella devolveria "
        "vacio en silencio"
    )
    n = pl.scan_parquet(str(d / "*.parquet")).select(pl.len()).collect().item()
    print(f"polars: {len(esquema.names())} columnas, {n:,} filas, "
          f"goalkeeper_type={esquema['goalkeeper_type']}")


def _prueba_adversaria(ruta_adaptador: Path) -> None:
    """El caso que rompio la version anterior, sin depender de pandas.

    Se fabrican tres parquets a mano con pyarrow:
      parte_000  la columna rara TIPADA `null`  (lo que produce pandas 2.x al
                 escribir una columna `object` con todo a None)
      parte_001  la misma columna como `string` con datos
      parte_002  sin la columna, y con `player_id` entero donde las otras lo
                 tienen `double`
    Tras unificar, el dataset no puede tener ninguna columna `null` y
    `player_id` tiene que haber promocionado a double.
    """
    import importlib.util
    import pyarrow as pa
    import pyarrow.dataset as pads
    import pyarrow.parquet as pq

    spec = importlib.util.spec_from_file_location("adaptador", ruta_adaptador)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    d = Path("/tmp/banco_adversario")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    req = ["match_id"]

    pq.write_table(pa.table({
        "match_id": pa.array([1, 2], pa.int64()),
        "rara": pa.nulls(2, pa.null()),                 # <- el caso de pandas 2.x
        "player_id": pa.array([1.0, None], pa.float64()),
    }), d / "parte_000.parquet")
    pq.write_table(pa.table({
        "match_id": pa.array([3], pa.int64()),
        "rara": pa.array(["Punched Out"], pa.string()),
        "player_id": pa.array([7.0], pa.float64()),
    }), d / "parte_001.parquet")
    pq.write_table(pa.table({
        "match_id": pa.array([4], pa.int64()),
        "player_id": pa.array([9], pa.int64()),         # <- entero, no double
    }), d / "parte_002.parquet")

    partes = sorted(d.glob("parte_*.parquet"))
    ok, vacias, n_rep, n_cols = mod.unificar_partes(partes, req)
    assert ok, "unificar_partes rechazo un caso que deberia resolver"
    esq = pads.dataset(str(d), format="parquet").schema
    tipos = dict(zip(esq.names, [str(t) for t in esq.types]))
    assert tipos["rara"] == "string", f"`rara` quedo {tipos['rara']}"
    assert tipos["player_id"] == "double", f"`player_id` quedo {tipos['player_id']}"
    assert pads.dataset(str(d), format="parquet").count_rows() == 4
    # la columna rara de la parte 0 existe y esta vacia, no perdida
    t0 = pq.read_table(partes[0])
    assert "rara" in t0.column_names and t0.column("rara").null_count == 2
    print(f"prueba adversaria: rara={tipos['rara']}, "
          f"player_id={tipos['player_id']}, {n_rep}/3 partes reescritas")


BASE = Path("/tmp/banco")
RAW = BASE / "data/raw_api"
OUT = BASE / "data/api"

if "--solo-polars" in sys.argv:
    # Segunda mitad: se ejecuta en .venv, sobre lo que escribio .venv-sb.
    _verifica_polars(BASE / "data/api/eventos_api_ligamx")
    print("\nLECTURA OK")
    raise SystemExit(0)

shutil.rmtree(BASE, ignore_errors=True)
(RAW / "events").mkdir(parents=True)
OUT.mkdir(parents=True)

N_PARTIDOS = 12
EVENTOS = 900          # 10,800 eventos -> varias partes con filas_por_parte=2000

filas = []
for k in range(N_PARTIDOS):
    mid = 100000 + k
    local, visita = ("América", "Toluca") if k % 2 == 0 else ("Toluca", "América")
    filas.append({
        "match_id": mid, "season_id": 108,
        "match_date": f"2024-01-{k + 1:02d}", "match_week": k + 1,
        "status": "available", "status_360": "available",
        "home_team": local, "away_team": visita,
        "stage": "Apertura" if k < 10 else "Apertura - Quarter-finals",
    })
    evs = []
    for i in range(1, EVENTOS + 1):
        e = {
            "id": f"{mid}-{i}", "index": i, "match_id": mid, "period": 1,
            "minute": i // 10, "second": i % 60,
            "type": {"id": 30, "name": "Pass"},
            "team": {"id": 1, "name": local if i % 2 else visita},
            "possession": i // 5 + 1,
            "possession_team": {"id": 1, "name": local if i % 2 else visita},
            "play_pattern": {"id": 1, "name": "Regular Play"},
            "location": [60.0, 40.0],
            "player": {"id": 7, "name": "X"},
            "under_pressure": True if i % 3 == 0 else None,
        }
        # LA TRAMPA: una bandera que solo existe en los ultimos partidos.
        if k >= 8 and i == 5:   # partidos 8 y 9: regulares, ultima parte
            e["goalkeeper"] = {"type": {"id": 1, "name": "Punched Out"}}
            e["bad_behaviour"] = {"card": {"id": 5, "name": "Yellow Card"}}
        evs.append(e)
    (RAW / "events" / f"{mid}.json.gz").write_bytes(
        gzip.compress(json.dumps(evs).encode())
    )

with (RAW / "indice_partidos.csv").open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
    w.writeheader()
    w.writerows(filas)

rc = subprocess.run(
    [sys.executable, str(Path(sys.argv[1]).resolve()),
     "--raw", str(RAW), "--out", str(OUT), "--todos", "--formato", "parquet",
     "--excluir-liguilla", "--filas-por-parte", "2000",
     "--muestra-esquema", "3"],
    cwd=BASE,
).returncode
print(f"\n--- codigo de salida del adaptador: {rc}")
if rc != 0:
    raise SystemExit(rc)

import pyarrow.dataset as pads

d = OUT / "eventos_api_ligamx"
partes = sorted(d.glob("parte_*.parquet"))
print(f"partes: {len(partes)}")
ds = pads.dataset(str(d), format="parquet")
print(f"columnas unificadas: {len(ds.schema.names)}")
print(f"filas: {ds.count_rows()}  (esperado {10 * EVENTOS})")
assert ds.count_rows() == 10 * EVENTOS, "la liguilla no se excluyo"
nulas = [n for n, t in zip(ds.schema.names, ds.schema.types) if str(t) == "null"]
assert not nulas, f"columnas null: {nulas}"
assert "goalkeeper_type" in ds.schema.names, "se perdio la columna rara"

import pandas as pd
p0 = pd.read_parquet(partes[0])
assert "goalkeeper_type" in p0.columns, "la parte 0 no se relleno"
assert p0["goalkeeper_type"].isna().all(), "la parte 0 no deberia tener porteros"

fechas = pd.read_csv(OUT / "match_dates_ligamx.csv")
print(f"match_dates: {len(fechas)} filas")
assert len(fechas) == 10, "las fechas no cuadran con los partidos escritos"

# El consumidor real es polars, que vive en el OTRO entorno (.venv). Si esta
# disponible se comprueba aqui; si no, el INSTALAR.sh lo corre aparte con
# `--solo-polars`, que es el escenario de verdad: escribir con .venv-sb y leer
# con .venv.
try:
    import polars as pl
except ImportError:
    print("\n(polars no esta en este entorno: la lectura se verifica aparte)")
else:
    _verifica_polars(d)
_prueba_adversaria(Path(sys.argv[1]).resolve())
print("\nTODO OK")
