#!/usr/bin/env python3
"""
00_fetch_statsbomb.py — descarga idempotente y reanudable del API de StatsBomb.

REGLA DEL PROYECTO: este es el UNICO archivo que habla con la red.
`src/dtdecoder/` jamas importa statsbombpy.

Guarda el JSON CRUDO comprimido. El parseo es otra etapa: si cambias el
adaptador no vuelves a pegarle al API.

Uso:
    export SB_USERNAME=...  SB_PASSWORD=...
    python scripts/00_fetch_statsbomb.py --solo-metadatos     # 1 min
    python scripts/00_fetch_statsbomb.py                      # eventos, ~1h
    python scripts/00_fetch_statsbomb.py --con-360            # aparte, pesado

Reanudable: si un archivo ya existe, no se vuelve a pedir. Ctrl-C y relanzar
continua donde iba.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path

LIGA_MX = 73
SEASONS_DEFAULT = [108, 235, 281, 317, 318, 351]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def guardar(obj, destino: Path) -> int:
    """Escribe JSON gzip de forma atomica (tmp + rename)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    datos = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
    tmp.write_bytes(gzip.compress(datos, compresslevel=6))
    tmp.rename(destino)
    return destino.stat().st_size


def con_reintentos(fn, *args, intentos=5, espera=2.0, **kwargs):
    """Backoff exponencial. Si agota intentos, propaga la excepcion."""
    for i in range(intentos):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if i == intentos - 1:
                raise
            pausa = espera * (2**i)
            log(f"    fallo ({type(exc).__name__}: {exc}); reintento en {pausa:.0f}s")
            time.sleep(pausa)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw_api", type=Path)
    ap.add_argument("--competition", type=int, default=LIGA_MX)
    ap.add_argument("--seasons", type=int, nargs="+", default=SEASONS_DEFAULT)
    ap.add_argument("--sleep", type=float, default=0.35,
                    help="pausa entre llamadas, en segundos")
    ap.add_argument("--solo-metadatos", action="store_true",
                    help="solo partidos y alineaciones; sin eventos")
    ap.add_argument("--con-360", action="store_true",
                    help="descarga freeze frames (PESADO: varios GB)")
    ap.add_argument("--sin-lineups", action="store_true")
    ap.add_argument("--limite", type=int, default=0,
                    help="descarga solo los primeros N partidos (prueba)")
    args = ap.parse_args()

    if not os.environ.get("SB_USERNAME") or not os.environ.get("SB_PASSWORD"):
        log("ERROR: falta export SB_USERNAME / SB_PASSWORD")
        return 1

    from statsbombpy import sb  # import tardio: tras validar credenciales

    # statsbombpy NO lanza excepcion con un 401: imprime y devuelve vacio.
    # Por eso hay que verificar con una llamada real antes de nada.
    log("verificando credenciales...")
    try:
        comps = sb.competitions()
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR al consultar competencias: {exc}")
        return 1
    if comps is None or len(comps) == 0:
        log("ERROR: el API devolvio VACIO. Credenciales incorrectas o sin acceso.")
        log("  Revisa SB_USERNAME / SB_PASSWORD y vuelve a intentar.")
        return 1
    log(f"credenciales OK ({len(comps)} competencias con acceso)")

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    fallos_path = out / "_fallos.csv"
    if not fallos_path.exists():
        fallos_path.write_text("tipo,id,error\n", encoding="utf-8")

    def anota_fallo(tipo: str, ident, exc) -> None:
        err = str(exc).replace(",", ";").replace("\n", " ")[:200]
        with fallos_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{tipo},{ident},{err}\n")

    # ---------------------------------------------------------------- 1. partidos
    todos: list[dict] = []
    for sid in args.seasons:
        dst = out / "matches" / f"{args.competition}_{sid}.json.gz"
        crudo = None
        if dst.exists():
            crudo = json.loads(gzip.decompress(dst.read_bytes()))
            if not crudo:
                log(f"partidos temporada {sid}: CACHE VACIA, se borra y reintenta")
                dst.unlink()
                crudo = None
            else:
                log(f"partidos temporada {sid}: cache ({len(crudo)})")
        if crudo is None:
            try:
                crudo = con_reintentos(
                    sb.matches, competition_id=args.competition,
                    season_id=sid, fmt="dict",
                )
            except Exception as exc:  # noqa: BLE001
                log(f"partidos temporada {sid}: FALLO")
                anota_fallo("matches", sid, exc)
                continue
            if not crudo:
                log(f"ERROR: temporada {sid} devolvio VACIO (401 o sin permiso).")
                log("  ABORTO. No se guarda nada. Revisa las credenciales.")
                return 1
            guardar(crudo, dst)
            log(f"partidos temporada {sid}: {len(crudo)} descargados")
            time.sleep(args.sleep)

        for mid, m in (crudo.items() if isinstance(crudo, dict)
                       else ((x["match_id"], x) for x in crudo)):
            m = dict(m)
            m["_season_id"] = sid
            m["match_id"] = int(mid)
            todos.append(m)

    # indice plano, comodo para inspeccionar sin volver a la red
    idx = out / "indice_partidos.csv"
    campos = ["match_id", "_season_id", "match_date", "match_week",
              "match_status", "match_status_360"]
    with idx.open("w", encoding="utf-8") as fh:
        fh.write("match_id,season_id,match_date,match_week,status,status_360,"
                 "home_team,away_team,stage\n")
        for m in sorted(todos, key=lambda r: r["match_id"]):
            def g(d, *ks):
                for k in ks:
                    d = (d or {}).get(k) if isinstance(d, dict) else None
                return d
            fila = [
                m.get("match_id"), m.get("_season_id"),
                str(m.get("match_date", ""))[:10], m.get("match_week", ""),
                m.get("match_status", ""), m.get("match_status_360", ""),
                g(m, "home_team", "home_team_name") or "",
                g(m, "away_team", "away_team_name") or "",
                str(g(m, "competition_stage", "name") or "").replace(",", ";"),
            ]
            fh.write(",".join(f'"{x}"' for x in fila) + "\n")
    log(f"indice escrito: {idx}  ({len(todos)} partidos)")

    disponibles = [m for m in todos if m.get("match_status") == "available"]
    log(f"con eventos disponibles: {len(disponibles)} de {len(todos)}")

    if args.solo_metadatos:
        log("--solo-metadatos: termino aqui.")
        return 0

    ids = sorted({m["match_id"] for m in disponibles})
    if args.limite:
        ids = ids[: args.limite]

    # ---------------------------------------------------------------- 2. eventos
    def descarga(tipo: str, fn, ids_obj, ext="json.gz"):
        carpeta = out / tipo
        for i in ids_obj:  # una cache de 0 bytes utiles es un fallo disfrazado
            f = carpeta / f"{i}.{ext}"
            if f.exists() and f.stat().st_size < 60:
                f.unlink()
        pendientes = [i for i in ids_obj if not (carpeta / f"{i}.{ext}").exists()]
        log(f"{tipo}: {len(ids_obj) - len(pendientes)} en cache, "
            f"{len(pendientes)} por descargar")
        bytes_tot, t0, vacios = 0, time.time(), [0]
        for n, mid in enumerate(pendientes, 1):
            try:
                obj = con_reintentos(fn, mid, fmt="dict")
            except Exception as exc:  # noqa: BLE001
                log(f"  {tipo} {mid}: FALLO definitivo")
                anota_fallo(tipo, mid, exc)
                continue
            if not obj:
                # vacio no es un dato: es un fallo que no lanzo excepcion
                log(f"  {tipo} {mid}: VACIO, no se guarda")
                anota_fallo(tipo, mid, "respuesta vacia")
                vacios[0] += 1
                if vacios[0] >= 10:
                    log("  ABORTO: 10 respuestas vacias seguidas.")
                    raise SystemExit(1)
                continue
            vacios[0] = 0
            bytes_tot += guardar(obj, carpeta / f"{mid}.{ext}")
            if n % 25 == 0 or n == len(pendientes):
                transcurrido = time.time() - t0
                ritmo = n / max(transcurrido, 1e-9)
                queda = (len(pendientes) - n) / max(ritmo, 1e-9)
                log(f"  {tipo}: {n}/{len(pendientes)}  "
                    f"{bytes_tot/1e6:.0f} MB  "
                    f"faltan ~{queda/60:.0f} min")
            time.sleep(args.sleep)

    descarga("events", sb.events, ids)

    if not args.sin_lineups:
        descarga("lineups", sb.lineups, ids)

    if args.con_360:
        con360 = sorted({m["match_id"] for m in disponibles
                         if m.get("match_status_360") == "available"})
        log(f"360: {len(con360)} partidos. Esto puede ocupar varios GB.")
        descarga("frames", sb.frames, con360)

    fallos = fallos_path.read_text(encoding="utf-8").strip().split("\n")
    log(f"LISTO. Fallos registrados: {len(fallos) - 1} (ver {fallos_path})")
    log("Relanza el mismo comando para reintentar solo lo que falta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
