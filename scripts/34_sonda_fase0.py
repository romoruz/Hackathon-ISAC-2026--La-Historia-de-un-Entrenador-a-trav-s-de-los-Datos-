#!/usr/bin/env python
"""34_sonda_fase0.py — sonda de SOLO LECTURA para cerrar la Fase 0 (paquete h2_26).

No escribe nada fuera de:
  reports/sonda_fase0.txt
  ~/Descargas/h2_26_devolver_<AAAAMMDDHHMM>.tar.gz   (lo que se sube al chat)

Por qué existe: el asistente NO tiene el repo ni los datos. Antes de escribir
el documentador de ADR-58 y el panel 5.5 tiene que LEER el formato real
(error de proceso #6: adivinar el formato en vez de leerlo). Esta sonda junta:

  0. estado de git, de ADR-58 y del script 38
  1. --help de los scripts que se van a reusar (13, 14*, 37, 12, 30, 33, 38)
  2. firmas (ast) de los módulos con piezas comunes
  3. esquema del parquet de liga: ¿hay obv_*, xG, pass_end_location?
  4. ORIENTACIÓN OFENSIVA, independiente de 13: banda de jugadores conocidos
  5. ORIENTACIÓN DEFENSIVA, independiente de 14: Pressure contra la acción
     presionada, ¿mismo marco o rotado 180°?
  6. esqueleto de los seis JSON de resultados
  7. índice de partidos y artefactos por club
  8. empaqueta fuentes + JSON (agregados) + este log. NUNCA eventos crudos.

Uso (entorno .venv, desde la raíz del repo):
  python -u scripts/34_sonda_fase0.py 2>&1 | tee logs/sonda_fase0.log
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import glob
import json
import math
import os
import subprocess
import sys
import tarfile
import traceback
from pathlib import Path

REPO = Path.cwd()
TS = dt.datetime.now().strftime("%Y%m%d%H%M")


class Tee:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, "w", encoding="utf-8")
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush()
        self.f.flush()


def seccion(t):
    print(f"\n{'=' * 78}\n== {t}\n{'=' * 78}", flush=True)


def protegido(fn):
    def w(*a, **k):
        try:
            return fn(*a, **k)
        except Exception:
            print("!! FALLÓ ESTA SECCIÓN (las demás siguen):")
            traceback.print_exc(file=sys.stdout)
    return w


def sh(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -9, f"(timeout {timeout}s)"
    except Exception as e:  # noqa: BLE001
        return -1, repr(e)


# ---------------------------------------------------------------- 0
@protegido
def s0_estado():
    seccion("0 · entorno y estado")
    print("python   :", sys.executable)
    print("versión  :", sys.version.split()[0])
    try:
        import numpy, polars  # noqa: E401
        print("polars   :", polars.__version__, "· numpy:", numpy.__version__)
    except ImportError as e:
        print("!! falta:", e, "→ ¿activaste .venv (no .venv-sb)?")
    print("cwd      :", REPO)
    for c in (["git", "rev-parse", "--short", "HEAD"],
              ["git", "log", "--oneline", "-8"],
              ["git", "status", "--short", "--", "scripts/38_jugadores.py",
               "tests/test_jugadores.py", "docs/06_DECISIONS.md", "docs/10_RESULTADOS.md"]):
        rc, out = sh(c)
        print(f"\n$ {' '.join(c)}  [rc={rc}]\n{out or '(vacío = limpio/commiteado)'}")
    rc, out = sh(["git", "ls-files", "--error-unmatch", "scripts/38_jugadores.py", "tests/test_jugadores.py"])
    print("\n38 y su test versionados:", "SÍ" if rc == 0 else "NO → falta el commit del bloque 2")

    for doc, pats in (("docs/06_DECISIONS.md", ["ADR-58", "ADR-59"]),
                      ("docs/10_RESULTADOS.md", ["§33", "## 33", "ADR-58"]),
                      ("docs/13_CONTEXTO_IA.md", ["58 ADR", "ADR-58"]),
                      ("docs/README.md", ["ADR-58"])):
        p = REPO / doc
        if not p.exists():
            print(f"{doc}: NO EXISTE")
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        hits = {pt: txt.count(pt) for pt in pats}
        heads = [l for l in txt.splitlines() if l.startswith("## ")][-4:]
        print(f"{doc}: apariciones {hits} · últimos encabezados {heads}")
    for p in sorted(glob.glob(str(REPO / "docs/preinscritos/*"))):
        print("preinscrito:", Path(p).relative_to(REPO))


# ---------------------------------------------------------------- 1
AYUDAS = ["scripts/13_verificar_ejes.py", "scripts/14_verificar_ejes_def.py",
          "scripts/14_diagnostico_defensa.py", "scripts/37_docs_resultados.py",
          "scripts/32_docs_adr53.py", "scripts/12_reporte_html.py",
          "scripts/30_did_contemporaneo.py", "scripts/33_did_presion.py",
          "scripts/36_contexto.py", "scripts/38_jugadores.py",
          "scripts/verifica_reporte.py", "docs/verificar_docs.py"]


@protegido
def s1_ayudas():
    seccion("1 · existencia y --help")
    for s in sorted(set(glob.glob(str(REPO / "scripts/1[34]_*.py")))):
        print("encontrado:", Path(s).relative_to(REPO))
    for s in AYUDAS:
        p = REPO / s
        if not p.exists():
            print(f"\n-- {s}: NO EXISTE")
            continue
        rc, out = sh([sys.executable, str(p), "--help"], timeout=60)
        print(f"\n-- {s} --help  [rc={rc}]\n{out[:2500]}")


# ---------------------------------------------------------------- 2
FIRMAS = ["scripts/08_ic_derivados.py", "scripts/24_linea_base_contemporanea.py",
          "scripts/30_did_contemporaneo.py", "scripts/32_docs_adr53.py",
          "scripts/33_did_presion.py", "scripts/36_contexto.py",
          "scripts/37_docs_resultados.py", "scripts/38_jugadores.py"]


@protegido
def s2_firmas():
    seccion("2 · firmas de funciones (ast)")
    for s in FIRMAS:
        p = REPO / s
        if not p.exists():
            print(f"\n-- {s}: NO EXISTE")
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        print(f"\n-- {s} ({len(p.read_text(encoding='utf-8').splitlines())} líneas)")
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in n.args.args]
                print(f"   def {n.name}({', '.join(args)})")
            elif isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) for t in n.targets):
                nombres = [t.id for t in n.targets]
                if any(x.isupper() for x in nombres):
                    print(f"   {', '.join(nombres)} = …")


# ---------------------------------------------------------------- 3
def archivos_liga():
    base = REPO / "data/api/eventos_api_ligamx"
    return sorted(str(p) for p in base.rglob("*.parquet"))


def esquema_unido(files):
    import polars as pl
    esquemas = {}
    for f in files:
        esquemas[f] = pl.scan_parquet(f).collect_schema()
    return esquemas


OBJETIVO = ["match_id", "index", "period", "minute", "second", "type", "team",
            "possession", "possession_team", "play_pattern", "location",
            "pass_end_location", "carry_end_location", "pass_outcome",
            "pass_type", "shot_statsbomb_xg", "shot_outcome", "under_pressure",
            "counterpress", "obv_for_net", "obv_against_net", "obv_total_net",
            "obv_for_after", "player", "player_id", "position", "related_events",
            "duration", "shot_freeze_frame"]


@protegido
def s3_esquema():
    import polars as pl
    seccion("3 · esquema del parquet de liga")
    files = archivos_liga()
    print("partes:", len(files))
    if not files:
        print("!! no hay parquet en data/api/eventos_api_ligamx")
        return
    esq = esquema_unido(files)
    firmas = {tuple(sorted(s.items(), key=lambda kv: kv[0])) for s in esq.values()}
    print("esquemas distintos entre partes:", len(firmas))
    s0 = next(iter(esq.values()))
    print("columnas:", len(s0))
    for c in OBJETIVO:
        tipos = {str(s.get(c)) for s in esq.values()}
        print(f"   {c:<22} {'/'.join(sorted(tipos))}")
    print("\nobv*/xg*/prog*/tilt* presentes:",
          sorted(c for c in s0 if any(k in c.lower() for k in ("obv", "xg", "prog", "tilt"))))

    lf = pl.scan_parquet(files[0])
    muestra = lf.select([c for c in ("location", "pass_end_location", "under_pressure", "type", "team")
                         if c in s0]).head(400).collect()
    for c in ("location", "pass_end_location"):
        if c in muestra.columns:
            vals = [v for v in muestra[c].to_list() if v is not None][:3]
            print(f"muestra {c}: {[repr(v) for v in vals]}")
    if "under_pressure" in muestra.columns:
        print("under_pressure valores (parte 0, 400 filas):",
              muestra["under_pressure"].value_counts().to_dicts())

    full = pl.scan_parquet(files) if len(firmas) == 1 else pl.scan_parquet(files[0])
    if len(firmas) != 1:
        print("!! esquemas distintos: los conteos siguientes son SOLO de la parte 0")
    cols = [c for c in ("shot_statsbomb_xg", "obv_for_net", "obv_against_net", "obv_total_net",
                        "pass_end_location") if c in s0]
    agg = [pl.len().alias("filas"), pl.col("match_id").n_unique().alias("partidos"),
           pl.col("team").n_unique().alias("equipos")]
    agg += [pl.col(c).is_not_null().sum().alias(f"nn_{c}") for c in cols]
    print("\nconteos:", full.select(agg).collect().to_dicts()[0])
    tipos = (full.group_by("type").agg(pl.len().alias("n"),
             *[pl.col(c).is_not_null().sum().alias(f"nn_{c}") for c in cols if c.startswith("obv")])
             .sort("n", descending=True).collect())
    print("\ntipos de evento (con cobertura de obv):")
    with pl.Config(tbl_rows=45, tbl_cols=10, tbl_width_chars=140):
        print(tipos)


# ---------------------------------------------------------------- 4 y 5
def xy(v):
    if v is None:
        return None
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return None
    try:
        if len(v) >= 2 and v[0] is not None and v[1] is not None:
            return float(v[0]), float(v[1])
    except TypeError:
        return None
    return None


def bandera(v):
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return bool(v)


JUGADORES = {"derecha": ["Zendejas", "Kevin Álvarez", "Jorge Sánchez"],
             "izquierda": ["Cristian Borja", "Luis Fuentes"]}


@protegido
def s4_orientacion_ofensiva(club):
    import polars as pl
    seccion("4 · orientación OFENSIVA (independiente de 13)")
    print("criterio (bug #12): atacando hacia x=120, y=0 queda a la IZQUIERDA.")
    print("un lateral/extremo DERECHO debe vivir en y alta (iy=3 ⇔ y ≥ 60).")
    files = archivos_liga()
    lf = pl.scan_parquet(files)
    base = (lf.filter((pl.col("team") == club) & pl.col("type").is_in(["Pass", "Carry"]))
              .select("player", "location"))
    for lado, nombres in JUGADORES.items():
        for nom in nombres:
            df = base.filter(pl.col("player").str.contains(nom, literal=True)).collect()
            pts = [p for p in map(xy, df["location"].to_list()) if p]
            if len(pts) < 50:
                print(f"   {lado:<9} {nom:<15} n={len(pts)} (insuficiente o nombre distinto)")
                continue
            ys = [p[1] for p in pts]
            alta = sum(y >= 60 for y in ys) / len(ys)
            baja = sum(y < 20 for y in ys) / len(ys)
            print(f"   {lado:<9} {nom:<15} n={len(pts):>5}  y≥60: {alta:.3f}  y<20: {baja:.3f}  "
                  f"nombres={sorted(set(df['player'].to_list()))[:2]}")
    print("VEREDICTO esperado: derecha con y≥60 alto, izquierda con y<20 alto.")


@protegido
def s5_orientacion_defensiva(n_partidos):
    import polars as pl
    seccion("5 · orientación DEFENSIVA (independiente de 14)")
    print("empareja cada Pressure con la acción rival marcada under_pressure más")
    print("cercana (±5 índices) y mide en qué marco coinciden sus coordenadas.")
    files = archivos_liga()
    lf = pl.scan_parquet(files)
    ids = (lf.select(pl.col("match_id").unique()).collect()["match_id"].sort().to_list())
    paso = max(1, len(ids) // n_partidos)
    elegidos = ids[::paso][:n_partidos]
    df = (lf.filter(pl.col("match_id").is_in(elegidos))
            .select("match_id", "index", "type", "team", "location", "under_pressure")
            .collect().sort("match_id", "index"))
    filas = df.to_dicts()
    d = {"mismo": [], "rot180": [], "espejo_x": [], "espejo_y": []}
    pares = 0
    por_partido = {}
    for r in filas:
        por_partido.setdefault(r["match_id"], []).append(r)
    for rows in por_partido.values():
        for k, r in enumerate(rows):
            if r["type"] != "Pressure":
                continue
            p = xy(r["location"])
            if not p:
                continue
            mejor = None
            for j in range(max(0, k - 5), min(len(rows), k + 6)):
                o = rows[j]
                if j == k or o["team"] == r["team"] or not bandera(o["under_pressure"]):
                    continue
                q = xy(o["location"])
                if q and (mejor is None or abs(j - k) < mejor[0]):
                    mejor = (abs(j - k), q)
            if not mejor:
                continue
            qx, qy = mejor[1]
            pares += 1
            d["mismo"].append(math.dist(p, (qx, qy)))
            d["rot180"].append(math.dist(p, (120 - qx, 80 - qy)))
            d["espejo_x"].append(math.dist(p, (120 - qx, qy)))
            d["espejo_y"].append(math.dist(p, (qx, 80 - qy)))
    print(f"partidos: {len(por_partido)} · pares: {pares}")
    if not pares:
        print("!! sin pares: revisar nombres de columnas/valores")
        return
    med = {k: sorted(v)[len(v) // 2] for k, v in d.items()}
    for k, v in med.items():
        print(f"   distancia mediana, marco {k:<9}: {v:6.2f} m")
    gana = min(med, key=med.get)
    print(f"VEREDICTO: la presión y la acción presionada coinciden en el marco «{gana}».")
    if gana == "rot180":
        print("   ⇒ cada evento está en el marco de QUIEN LO EJECUTA. π_e(z) se calcula sobre")
        print("     acciones del rival: la zona z está en el marco del RIVAL. Para pintarla")
        print("     desde el defensor hay que rotar 180° (x→120−x, y→80−y), o sea zona")
        print("     (ix, iy) → (nx−1−ix, ny−1−iy). Revisar que 33/12 lo hagan.")


# ---------------------------------------------------------------- 6
RESULTADOS = ["did_h4_v1.json", "did_presion_v1.json", "balon_parado_v1.json",
              "balon_parado_v2.json", "contexto_v1.json", "jugadores_v1.json",
              "deriva_proveedor.json"]


def esqueleto(o, prof=0, maxp=4):
    pad = "  " * prof
    if prof > maxp:
        return f"{pad}…"
    if isinstance(o, dict):
        ls = []
        for i, (k, v) in enumerate(o.items()):
            if i >= 25:
                ls.append(f"{pad}… (+{len(o) - 25} llaves)")
                break
            if isinstance(v, (dict, list)):
                ls.append(f"{pad}{k}: {type(v).__name__}[{len(v)}]")
                ls.append(esqueleto(v, prof + 1, maxp))
            else:
                ls.append(f"{pad}{k}: {repr(v)[:60]}")
        return "\n".join(ls)
    if isinstance(o, list):
        return esqueleto(o[0], prof, maxp) if o else f"{pad}(lista vacía)"
    return f"{pad}{repr(o)[:60]}"


@protegido
def s6_json():
    seccion("6 · esqueleto de los JSON de resultados")
    for n in RESULTADOS:
        p = REPO / "reports" / n
        if not p.exists():
            print(f"\n-- {n}: NO EXISTE")
            continue
        print(f"\n-- {n}  ({p.stat().st_size / 1e6:.2f} MB, mtime "
              f"{dt.datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M})")
        print(esqueleto(json.loads(p.read_text(encoding="utf-8")), maxp=3))


# ---------------------------------------------------------------- 7
@protegido
def s7_artefactos(club_slug):
    import polars as pl
    seccion("7 · índice de partidos y artefactos por club")
    idx = REPO / "data/raw_api/indice_partidos.csv"
    if idx.exists():
        with open(idx, encoding="utf-8") as f:
            for i, l in enumerate(f):
                if i > 2:
                    break
                print("  ", l.rstrip())
    dirs = sorted(glob.glob(str(REPO / "data/processed_api_*")))
    print("processed_api_*:", len(dirs), [Path(x).name for x in dirs][:20])
    cand = [x for x in dirs if club_slug in Path(x).name] or dirs[:1]
    for x in cand[:1]:
        for f in sorted(Path(x).iterdir()):
            print(f"   {f.name:<40} {f.stat().st_size / 1e6:8.2f} MB")
        t = Path(x) / "transitions.parquet"
        if t.exists():
            print("   transitions.parquet:", dict(pl.scan_parquet(t).collect_schema()))
    lu = sorted(glob.glob(str(REPO / "data/raw_api/lineups/*")))[:1]
    print("lineups, ejemplo:", [Path(x).name for x in lu])


# ---------------------------------------------------------------- 8
DEVOLVER = ["config/default.yaml",
            "scripts/08_ic_derivados.py", "scripts/12_reporte_html.py",
            "scripts/13_verificar_ejes.py", "scripts/24_linea_base_contemporanea.py",
            "scripts/30_did_contemporaneo.py", "scripts/32_docs_adr53.py",
            "scripts/33_did_presion.py", "scripts/36_contexto.py",
            "scripts/37_docs_resultados.py", "scripts/38_jugadores.py",
            "scripts/verifica_reporte.py", "scripts/humo_reporte.py", "scripts/humo_reporte.js",
            "tests/test_jugadores.py", "docs/verificar_docs.py",
            "docs/06_DECISIONS.md", "docs/10_RESULTADOS.md", "docs/13_CONTEXTO_IA.md",
            "docs/15_REPORTE_HTML.md", "docs/16_MIGRACION_API.md", "docs/README.md"]
PATRONES = ["scripts/14_*.py", "docs/preinscritos/*", "docs/**/ROADMAP_CIERRE_RETO.md",
            "ROADMAP_CIERRE_RETO.md", "src/dtdecoder/grid.py"]
MAX_MB = 25


def s8_empaquetar(log_path: Path):
    seccion("8 · paquete de regreso")
    destino_dir = Path.home() / "Descargas"
    if not destino_dir.is_dir():
        destino_dir = REPO / "logs"
    destino = destino_dir / f"h2_26_devolver_{TS}.tar.gz"
    rutas = [REPO / r for r in DEVOLVER]
    for pat in PATRONES:
        rutas += [Path(p) for p in glob.glob(str(REPO / pat), recursive=True)]
    rutas += [REPO / "reports" / n for n in RESULTADOS]
    total = 0
    with tarfile.open(destino, "w:gz") as tar:
        for p in dict.fromkeys(rutas):
            if not p.is_file():
                print(f"   (no existe) {p.relative_to(REPO)}")
                continue
            mb = p.stat().st_size / 1e6
            if mb > MAX_MB:
                print(f"   (omitido, {mb:.1f} MB) {p.relative_to(REPO)}")
                continue
            if "raw_api" in p.parts or "api" in p.parts[-3:-1]:
                continue  # nunca datos licenciados
            tar.add(p, arcname=f"h2_26_devolver/{p.relative_to(REPO)}")
            total += mb
        sys.stdout.flush()
        tar.add(log_path, arcname="h2_26_devolver/reports/sonda_fase0.txt")
    print(f"\nPAQUETE: {destino}")
    print(f"tamaño sin comprimir ≈ {total:.1f} MB · comprimido "
          f"{destino.stat().st_size / 1e6:.2f} MB")
    print("→ súbelo al chat tal cual.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", default="América")
    ap.add_argument("--club-slug", default="america")
    ap.add_argument("--partidos-presion", type=int, default=40)
    ap.add_argument("--sin-paquete", action="store_true")
    a = ap.parse_args()
    if not (REPO / "src/dtdecoder").is_dir():
        sys.exit("ABORTA: corre desde la raíz del repo (cd \"…/Hackathon2026\")")
    log_path = REPO / "reports/sonda_fase0.txt"
    tee = Tee(log_path)
    sys.stdout = tee
    print(f"sonda_fase0 · {TS} · club={a.club}")
    s0_estado()
    s1_ayudas()
    s2_firmas()
    s3_esquema()
    s4_orientacion_ofensiva(a.club)
    s5_orientacion_defensiva(a.partidos_presion)
    s6_json()
    s7_artefactos(a.club_slug)
    tee.flush()
    if not a.sin_paquete:
        s8_empaquetar(log_path)
    print("\n== sonda terminada ==")
    tee.flush()


if __name__ == "__main__":
    main()
