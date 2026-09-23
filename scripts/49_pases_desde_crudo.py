#!/usr/bin/env python3
"""
49_pases_desde_crudo.py — F4 / ADR-62: el receptor de pase, de los JSON crudos.

Los eventos de StatsBomb ya están en `data/raw_api/events/*.json.gz` (los bajó
`00_fetch_statsbomb.py`, el único archivo del proyecto que habla con la red).
Traen `pass.recipient.id`, así que NO hay que volver a pedir nada al API: se lee
el mismo byte del que salieron los parquets publicados.

Escribe en un directorio NUEVO (`data/pases_api/`). No toca
`data/processed_api_*` ni ningún JSON de `reports/`.

Dos modos, y el cotejo es obligatorio antes de medir nada:

  --extraer   lee los gz y escribe data/pases_api/pases.parquet con lo justo:
              match_id, team, coach, pasador, receptor, si el pase se completó,
              la posesión y el minuto. Nada más.
  --cotejar   comprueba contra los parquets publicados que hablamos del mismo
              universo: mismos partidos, mismos equipos, mismos jugadores.
              ABORTA si algo no cuadra.

Uso:
    python scripts/49_pases_desde_crudo.py --extraer
    python scripts/49_pases_desde_crudo.py --cotejar
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "data" / "raw_api" / "events"
DESTINO = RAIZ / "data" / "pases_api"


class Aborta(Exception):
    pass


def _n(x):
    """El nombre de un campo que puede venir como dict {id, name} o plano."""
    return x.get("name") if isinstance(x, dict) else x


def _i(x):
    return x.get("id") if isinstance(x, dict) else None


def pases_de(ruta: Path):
    """Los pases de un partido. Un pase COMPLETADO es el que no trae outcome
    (convención de StatsBomb). El receptor de un pase fallido es el destinatario
    previsto, no quien recibió: se guarda, pero marcado."""
    d = json.loads(gzip.open(ruta).read())
    ev = d.values() if isinstance(d, dict) else d
    out = []
    for e in ev:
        if _n(e.get("type")) != "Pass":
            continue
        p = e.get("pass") or {}
        rec = p.get("recipient")
        if not rec:
            continue
        jug = e.get("player") or {}
        out.append({
            "match_id": e.get("match_id"),
            "team": _n(e.get("team")),
            "player_id": _i(jug), "player": _n(jug),
            "recipient_id": _i(rec), "recipient": _n(rec),
            "completado": p.get("outcome") is None,
            "possession": e.get("possession"),
            "minute": e.get("minute"),
            "tipo_pase": _n(p.get("type")),
        })
    return out


def eras_publicadas():
    """(match_id, team) → coach, de los parquets publicados. Es el mapeo que ya
    está validado en el proyecto; aquí no se vuelve a inferir nada."""
    import polars as pl
    dirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    if not dirs:
        raise Aborta("no hay data/processed_api_*")
    partes = []
    for d in dirs:
        p = Path(d) / "transitions.parquet"
        if not p.exists():
            raise Aborta(f"falta {p}")
        partes.append(pl.read_parquet(p, columns=["match_id", "team", "coach", "player_id"])
                      .filter(pl.col("coach").is_not_null()))
    return pl.concat(partes)


def extraer(a):
    import polars as pl
    rutas = sorted(CRUDOS.glob("*.json.gz"))
    if not rutas:
        raise Aborta(f"no hay eventos crudos en {CRUDOS}")
    pub = eras_publicadas()
    quiero = set(pub["match_id"].unique().to_list())
    print(f"{len(rutas)} partidos en crudo · {len(quiero)} en el universo publicado")
    filas, leidos, t0 = [], 0, time.time()
    saltados = 0
    for r in rutas:
        # OJO: Path("3799351.json.gz").stem es "3799351.json", no "3799351".
        try:
            mid = int(r.name.split(".")[0])
        except ValueError:
            saltados += 1
            continue
        if mid not in quiero:
            continue
        filas += pases_de(r)
        leidos += 1
        if leidos % 200 == 0:
            print(f"  {leidos} partidos · {len(filas):,} pases · {time.time() - t0:.0f} s"
                  .replace(",", " "), flush=True)
    if leidos == 0:
        raise Aborta(f"ningún archivo de {CRUDOS} cayó en el universo publicado "
                     f"({saltados} con nombre no numérico de {len(rutas)}). "
                     f"Ejemplo de nombre: {rutas[0].name}; ejemplo de match_id publicado: "
                     f"{sorted(quiero)[0]}")
    if not filas:
        raise Aborta(f"se leyeron {leidos} partidos pero no salió ni un pase: revisa la forma "
                     f"de los JSON (¿cambió el anidado de type/pass/recipient?)")
    t = pl.DataFrame(filas)
    # el técnico, desde los parquets publicados (no se infiere aquí)
    mapa = pub.select("match_id", "team", "coach").unique()
    t = t.join(mapa, on=["match_id", "team"], how="left")
    sin = int(t["coach"].is_null().sum())
    DESTINO.mkdir(parents=True, exist_ok=True)
    t.write_parquet(DESTINO / "pases.parquet")
    print(f"\nescrito {DESTINO / 'pases.parquet'}")
    print(f"  {t.height:,} pases con receptor en {leidos} partidos".replace(",", " "))
    print(f"  completados: {int(t['completado'].sum()):,} "
          f"({100 * t['completado'].mean():.1f}%)".replace(",", " "))
    print(f"  sin técnico asignado: {sin:,} (son del rival en partidos del universo)"
          .replace(",", " "))
    print(f"  {time.time() - t0:.0f} s")


def cotejar(a):
    import polars as pl
    f = DESTINO / "pases.parquet"
    if not f.exists():
        raise Aborta(f"falta {f}: corre primero --extraer")
    t = pl.read_parquet(f)
    pub = eras_publicadas()
    res = {}

    # 1. mismos partidos
    m_crudo = set(t["match_id"].unique().to_list())
    m_pub = set(pub["match_id"].unique().to_list())
    faltan = sorted(m_pub - m_crudo)
    res["partidos_publicados"] = len(m_pub)
    res["partidos_en_crudo"] = len(m_crudo)
    res["publicados_sin_crudo"] = faltan[:20]
    if faltan:
        raise Aborta(f"{len(faltan)} partidos publicados no tienen eventos crudos "
                     f"(por ejemplo {faltan[:5]}): el universo no coincide")

    # 2. mismos equipos por partido
    par_c = set(map(tuple, t.select("match_id", "team").unique().rows()))
    par_p = set(map(tuple, pub.select("match_id", "team").unique().rows()))
    sin_par = sorted(par_p - par_c)
    res["pares_partido_equipo_publicados"] = len(par_p)
    res["publicados_sin_pases"] = len(sin_par)
    if sin_par:
        raise Aborta(f"{len(sin_par)} pares (partido, equipo) publicados no tienen ni un pase "
                     f"en crudo: {sin_par[:5]}")

    # 3. los jugadores del parquet están entre los del crudo
    jc = t.select(pl.col("match_id"), pl.col("team"), pl.col("player_id")).unique()
    jp = pub.select("match_id", "team", "player_id").unique().filter(pl.col("player_id").is_not_null())
    fuera = jp.join(jc, on=["match_id", "team", "player_id"], how="anti")
    res["jugadores_publicados"] = jp.height
    res["jugadores_publicados_sin_un_solo_pase"] = fuera.height
    res["proporcion_sin_pase"] = round(fuera.height / max(jp.height, 1), 4)
    # un jugador puede aparecer en las transiciones sin haber dado ni un pase
    # (entró, remató y salió): eso es normal. Lo que no lo sería es que fuera masivo.
    if fuera.height / max(jp.height, 1) > .15:
        raise Aborta(f"{fuera.height} de {jp.height} (jugador, partido, equipo) del parquet no "
                     f"tienen ni un pase en crudo: más del 15%, algo no cuadra")

    # 4. proporción de pases sobre transiciones de tipo Pass, solo informativa
    res["pases_totales"] = t.height
    res["pases_completados"] = int(t["completado"].sum())
    res["cobertura_completados"] = round(float(t["completado"].mean()), 4)
    por_era = (t.filter(pl.col("coach").is_not_null())
               .group_by(["team", "coach"]).agg(pl.len().alias("n_pases"),
                                                pl.col("player_id").n_unique().alias("n_jugadores"))
               .sort(["team", "coach"]))
    res["eras"] = por_era.rows(named=True)

    print("=== cotejo contra el universo publicado ===")
    print(f"  partidos: {res['partidos_en_crudo']} de {res['partidos_publicados']} · ok")
    print(f"  pares (partido, equipo) sin pases: {res['publicados_sin_pases']} · ok")
    print(f"  jugadores del parquet sin ni un pase: {fuera.height} de {jp.height} "
          f"({100 * res['proporcion_sin_pase']:.1f}%) · normal si es bajo")
    print(f"  pases con receptor: {t.height:,}".replace(",", " "))
    print(f"  completados: {res['pases_completados']:,} "
          f"({100 * res['cobertura_completados']:.1f}%)".replace(",", " "))
    print("\n=== tamaño por era (club · técnico) ===")
    for r in res["eras"]:
        print(f"  {r['team']:<20s} {r['coach']:<22s} {r['n_pases']:6d} pases · "
              f"{r['n_jugadores']:3d} jugadores")
    out = RAIZ / "reports" / "pases_cotejo.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nescrito {out}")
    print("El cotejo NO mide ninguna relación: solo comprueba que es el mismo universo.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extraer", action="store_true")
    ap.add_argument("--cotejar", action="store_true")
    a = ap.parse_args()
    if not (a.extraer or a.cotejar):
        ap.error("elige --extraer o --cotejar")
    try:
        if a.extraer:
            extraer(a)
        if a.cotejar:
            cotejar(a)
    except Aborta as e:
        sys.exit(f"ABORTA: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
