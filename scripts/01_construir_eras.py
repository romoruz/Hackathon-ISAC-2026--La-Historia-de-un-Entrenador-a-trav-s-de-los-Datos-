#!/usr/bin/env python3
"""
01_construir_eras.py — genera coach_eras_<club>.csv desde los metadatos del API.

NO sustituye la verificacion humana: la ordena. Emite banderas que dicen
exactamente que fronteras hay que confirmar contra prensa, y cuales no.

Lecciones que codifica (2026-09-14):
  * El API acierta en los cambios a media temporada. Sobre las 4 fronteras
    verificadas contra fuentes externas, acerto 4 de 4.
  * La PRIMERA era de la ventana es la unica que ninguna evidencia INTERNA
    puede confirmar: no hay un partido anterior contra el que contrastar el
    cambio de DT. Por eso se marca PRIMERA_DE_VENTANA. Es una bandera
    PRECAUTORIA, no un indicio: no se ha encontrado ningun error del API.

    CORRECCION 2026-09-14. La version anterior de esta linea decia que "el
    API puede errar en la primera era (caso America: los partidos de Herrera
    aparecen como Solari)". Eso es el ERROR #2 de la bitacora §7: se
    reconocio un nombre en un club y se dio por verificado sin fuente. Herrera
    dejo el America en diciembre de 2020, fuera de la ventana, asi que no hay
    partidos suyos que etiquetar mal. Quien se equivoco fue el
    `coach_eras.csv` investigado a mano, no el API.

    Se corrige porque una justificacion retirada que sigue escrita como hecho
    reabre un debate cerrado dentro de un mes.
  * Una era es un periodo CONTINUO: rachas no contiguas se emiten I, II...

Uso:
    python scripts/01_construir_eras.py
    python scripts/01_construir_eras.py --min-partidos 25
    python scripts/01_construir_eras.py --club "América" --detalle
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _alcance import avisar_desconocidas, es_regular  # noqa: E402

SALIDA = Path("data/eras_api")


def sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def corto(nombre: str, nick: str | None, alias: dict | None = None,
          cid=None) -> str:
    """Nombre legal -> etiqueta.

    NO hay heuristica fiable para nombres hispanos/portugueses:
    'Santiago Hernan Solari Poggio' -> el apellido es el TERCER token,
    'Andre Soares Jardine'          -> es el tercero tambien,
    'Fernando Ortiz'                -> es el segundo.
    Por eso el orden es: alias manual > nickname del API > nombre completo.
    La etiqueta es COSMETICA: la clave del analisis es coach_id.
    """
    if alias and cid in alias and alias[cid]:
        return alias[cid]
    if nick:
        return sin_acentos(nick)
    return sin_acentos(nombre)


def leer_alias(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    out = {}
    import csv as _csv
    for r in _csv.DictReader(ruta.open(encoding="utf-8")):
        if r.get("etiqueta", "").strip():
            out[int(r["coach_id"])] = r["etiqueta"].strip()
    return out


def leer_correcciones(ruta: Path):
    """club,start_date,end_date,coach_id,coach,nota -> reasignacion manual."""
    if not ruta.exists():
        return []
    import csv as _csv
    return [r for r in _csv.DictReader(ruta.open(encoding="utf-8"))
            if r.get("club")]


def nom(d, *ks):
    for k in ks:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d


def torneo_de(fecha: str) -> str:
    anio, mes = int(fecha[:4]), int(fecha[5:7])
    return f"A{anio}" if mes >= 7 else f"C{anio}"


CATALOGO: dict = {}


# `es_regular` vivia aqui con una regla distinta a la de
# 02_adaptar_eventos.py. Ahora las dos importan scripts/_alcance.py: los dos
# scripts TIENEN que producir el mismo universo de partidos.


def cargar(raw: Path, excluir_liguilla=False, excluir_temporadas=()):
    """-> {club: [(fecha, coach_id, nombre, nick, etapa, n_managers, match_id)]}

    `match_id` es el ultimo elemento y se anadio para `--dump-asignacion`: sin
    el, un partido absorbido por una fusion de interinato no es identificable y
    no se puede excluir del ajuste.
    """
    reg = defaultdict(list)
    etapas_vistas = set()
    for p in sorted((raw / "matches").glob("*.json.gz")):
        sid = int(p.stem.split("_")[1].split(".")[0])
        if sid in excluir_temporadas:
            continue
        crudo = json.loads(gzip.decompress(p.read_bytes()))
        for m in (crudo.values() if isinstance(crudo, dict) else crudo):
            f = str(m.get("match_date"))[:10]
            if not f or f == "None":
                continue
            etapa = str(nom(m, "competition_stage", "name") or "")
            etapas_vistas.add(etapa)
            if excluir_liguilla and not es_regular(etapa):
                continue
            mid = m.get("match_id")
            for lado in ("home", "away"):
                club = nom(m, f"{lado}_team", f"{lado}_team_name")
                ms = (m.get(f"{lado}_team") or {}).get("managers")
                if not club or not isinstance(ms, list) or not ms:
                    continue
                reg[str(club)].append((f, ms[0].get("id"), ms[0].get("name"),
                                       ms[0].get("nickname"), etapa, len(ms),
                                       mid))
                CATALOGO[ms[0].get("id")] = (ms[0].get("name"),
                                             ms[0].get("nickname"))
    if excluir_liguilla:
        avisar_desconocidas(etapas_vistas, "data/raw_api/matches/")
    # Orden por (fecha, coach_id) con clave explicita: `sort()` sobre las
    # tuplas comparaba `coach_id` crudo y un `None` habria reventado con
    # TypeError a media corrida.
    for c in reg:
        reg[c].sort(key=lambda t: (t[0], str(t[1]), str(t[6])))
    return reg


def rachas(partidos):
    """Agrupa partidos consecutivos del mismo entrenador."""
    out, actual = [], None
    for f, cid, nombre, nick, etapa, nman, mid in partidos:
        if actual is None or cid != actual["coach_id"]:
            if actual:
                out.append(actual)
            actual = {"coach_id": cid, "nombre": nombre, "nick": nick,
                      "inicio": f, "fin": f, "n": 0, "torneos": set(),
                      "multi": 0, "propios": []}
        actual["fin"] = f
        actual["n"] += 1
        actual["propios"].append(mid)
        actual["torneos"].add(torneo_de(f))
        actual["multi"] += (nman > 1)
    if actual:
        out.append(actual)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw_api"))
    ap.add_argument("--out", type=Path, default=SALIDA)
    ap.add_argument("--min-partidos", type=int, default=25,
                    help="umbral de era analizable (ver ADR-25: Ortiz con 26 "
                         "ya daba params_per_obs=0.502 en 6x4)")
    ap.add_argument("--club", default=None)
    ap.add_argument("--detalle", action="store_true")
    ap.add_argument("--alias", type=Path, default=Path("data/alias_entrenadores.csv"))
    ap.add_argument("--correcciones", type=Path,
                    default=Path("data/eras_correcciones.csv"))
    ap.add_argument("--excluir-liguilla", action="store_true",
                    help="deja fuera liguilla, repechaje y play-in (DECISION 3)")
    ap.add_argument("--excluir-temporadas", type=int, nargs="*", default=[],
                    help="p.ej. 351, la temporada en curso (DECISION 2)")
    ap.add_argument("--compat", type=Path, default=Path("data/eras_compat"),
                    help="ademas, escribe el formato de 3 columnas que espera "
                         "eras.load_eras")
    # OJO: `action="store_true"` con `default=True` no se puede apagar nunca.
    # Importa porque al extender fronteras el compat no tiene huecos JAMAS, y
    # entonces `unmapped_matches` sale 0 por construccion y deja de servir como
    # control. Con --no-extender-fronteras se ve cuantos partidos caen de
    # verdad entre eras.
    ap.add_argument("--extender-fronteras", dest="extender_fronteras",
                    action="store_true", default=True,
                    help="end_date de cada era = dia antes del inicio de la "
                         "siguiente, para que ningun partido quede sin mapear")
    ap.add_argument("--no-extender-fronteras", dest="extender_fronteras",
                    action="store_false",
                    help="deja las fechas reales de primer y ultimo partido; "
                         "los huecos salen como unmapped_matches en phase0")
    ap.add_argument("--dump-asignacion", action="store_true",
                    help="escribe asignacion_partidos.csv (una fila por "
                         "club-partido) y absorbidos.csv (los partidos que una "
                         "fusion de interinato metio en la era de otro DT)")
    ap.add_argument("--fusionar-interinatos", type=int, default=2,
                    help="una era de <=N partidos entre dos del MISMO tecnico "
                         "se descarta y las vecinas se fusionan")
    args = ap.parse_args()

    reg = cargar(args.raw, args.excluir_liguilla, set(args.excluir_temporadas))
    if args.excluir_liguilla or args.excluir_temporadas:
        print(f"  alcance: liguilla={'fuera' if args.excluir_liguilla else 'dentro'}"
              f"  temporadas excluidas={args.excluir_temporadas or 'ninguna'}\n")
    if not reg:
        print(f"No hay metadatos en {args.raw}/matches/.")
        return 1

    alias = leer_alias(args.alias)
    corr = leer_correcciones(args.correcciones)

    # --- correcciones manuales: reasignan el DT de un rango de fechas
    n_corr = 0
    for c in corr:
        club = c["club"]
        cid = int(c["coach_id"]) if c.get("coach_id") else -abs(hash(c["coach"])) % 10**6
        if club not in reg:
            print(f"  correccion ignorada, club desconocido: {club}"); continue
        nuevos = []
        for (f, oid, nombre, nick, etapa, nman, mid) in reg[club]:
            if c["start_date"] <= f <= c["end_date"]:
                nuevos.append((f, cid, c["coach"], c["coach"], etapa, nman, mid))
                n_corr += 1
            else:
                nuevos.append((f, oid, nombre, nick, etapa, nman, mid))
        reg[club] = sorted(nuevos, key=lambda t: (t[0], str(t[1]), str(t[6])))
    if n_corr:
        print(f"  correcciones manuales aplicadas: {n_corr} partidos\n")

    # --- catalogo de alias para que el humano lo revise UNA vez
    if not args.alias.exists():
        args.alias.parent.mkdir(parents=True, exist_ok=True)
        with args.alias.open("w", encoding="utf-8") as fh:
            fh.write("coach_id,nombre_completo,nickname_api,etiqueta\n")
            for cid, (nombre, nick) in sorted(CATALOGO.items(),
                                              key=lambda x: str(x[1][0])):
                prop = sin_acentos(nick) if nick else ""
                fh.write(f'"{cid}","{nombre}","{nick or ""}","{prop}"\n')
        print(f"  escrito {args.alias}: rellena la columna 'etiqueta' y "
              f"vuelve a correr.\n")

    args.out.mkdir(parents=True, exist_ok=True)
    clubes = [args.club] if args.club else sorted(reg)
    resumen, n_verificar = [], 0
    asig, absorbidos = [], []

    for club in clubes:
        if club not in reg:
            print(f"  {club}: sin datos"); continue
        rs = rachas(reg[club])

        # fusionar interinatos cortos que parten la era del mismo tecnico
        if args.fusionar_interinatos > 0:
            cambio = True
            while cambio and len(rs) >= 3:
                cambio = False
                for k in range(1, len(rs) - 1):
                    if (rs[k]["n"] <= args.fusionar_interinatos
                            and rs[k - 1]["coach_id"] == rs[k + 1]["coach_id"]):
                        a, b = rs[k - 1], rs[k + 1]
                        a["fin"] = b["fin"]
                        a["n"] += b["n"]
                        a["torneos"] |= b["torneos"]
                        a["multi"] += b["multi"]
                        a["interinatos"] = a.get("interinatos", 0) + 1
                        a["propios"] = a["propios"] + b["propios"]
                        # Los partidos del interino quedan DENTRO del rango de
                        # la era fusionada pero NO se suman a `n`. Antes se
                        # perdian sin dejar rastro: la era cubria 102 partidos
                        # y declaraba 100, y la diferencia solo se veia
                        # cruzando el CSV contra el indice a mano. Ahora se
                        # nombran, para poder excluirlos del ajuste.
                        a.setdefault("absorbidos", []).extend(
                            {"match_id": m, "coach_id": rs[k]["coach_id"],
                             "coach": rs[k]["nombre"]}
                            for m in rs[k]["propios"]
                        )
                        a["absorbidos"].extend(b.pop("absorbidos", []))
                        rs = rs[:k] + rs[k + 2:]
                        cambio = True
                        break

        # rachas no contiguas del mismo DT -> sufijos I, II, ...
        veces = defaultdict(int)
        for r in rs:
            veces[r["coach_id"]] += 1
        visto = defaultdict(int)

        filas = []
        for i, r in enumerate(rs):
            base = corto(r["nombre"], r["nick"], alias, r["coach_id"])
            if veces[r["coach_id"]] > 1:
                visto[r["coach_id"]] += 1
                etiqueta = f"{base} {'I' * visto[r['coach_id']]}"
            else:
                etiqueta = base

            banderas = []
            if i == 0:
                banderas.append("PRIMERA_DE_VENTANA")   # verificar a mano
                n_verificar += 1
            if r["n"] < args.min_partidos:
                banderas.append("CORTA")
            if veces[r["coach_id"]] > 1:
                banderas.append("NO_CONTIGUA")
            if r["multi"]:
                banderas.append(f"MULTI_MANAGER({r['multi']})")
            if r.get("interinatos"):
                banderas.append(f"FUSIONADA({r['interinatos']})")
            if len(r["torneos"]) == 1 and r["n"] >= args.min_partidos:
                pass
            filas.append({
                "club": club, "coach": etiqueta, "coach_full": r["nombre"],
                "coach_id": r["coach_id"], "start_date": r["inicio"],
                "end_date": r["fin"], "n_partidos": r["n"],
                # `n_partidos` = partidos que este DT dirigio de verdad.
                # `n_en_rango` = partidos del club dentro de [inicio, fin], que
                # es lo que `eras.match_coach_table` le va a asignar, porque el
                # compat solo lleva fechas. Si difieren, la era esta absorbiendo
                # partidos de un interino y hay que decidir si se excluyen.
                "n_en_rango": r["n"] + len(r.get("absorbidos", [])),
                "n_absorbidos": len(r.get("absorbidos", [])),
                "torneos": "|".join(sorted(r["torneos"])),
                "analizable": int(r["n"] >= args.min_partidos),
                "banderas": ";".join(banderas),
            })

        # --- asignacion partido a partido (para auditar las fusiones)
        if args.dump_asignacion:
            fecha_de = {t[6]: t[0] for t in reg[club]}
            for x, r in zip(filas, rs):
                for mid in r["propios"]:
                    asig.append({
                        "club": club, "match_id": mid,
                        "match_date": fecha_de.get(mid, ""),
                        "era": x["coach"], "era_start": x["start_date"],
                        "era_end": x["end_date"],
                        "coach_real": x["coach_full"],
                        "coach_id_real": r["coach_id"],
                        "dirigio_la_era": 1,
                    })
                for ab in r.get("absorbidos", []):
                    fila = {
                        "club": club, "match_id": ab["match_id"],
                        "match_date": fecha_de.get(ab["match_id"], ""),
                        "era": x["coach"], "era_start": x["start_date"],
                        "era_end": x["end_date"],
                        "coach_real": ab["coach"],
                        "coach_id_real": ab["coach_id"],
                        "dirigio_la_era": 0,
                    }
                    asig.append(fila)
                    absorbidos.append(fila)

        # --- formato de 3 columnas para eras.load_eras
        if args.compat:
            args.compat.mkdir(parents=True, exist_ok=True)
            comp = [dict(x) for x in filas]
            if args.extender_fronteras:
                for a, b in zip(comp, comp[1:]):
                    import datetime as _dt
                    d = _dt.date.fromisoformat(b["start_date"]) - _dt.timedelta(days=1)
                    a["end_date"] = d.isoformat()
            cdst = (args.compat /
                    f"coach_eras_{sin_acentos(club).lower().replace(' ', '_')}.csv")
            with cdst.open("w", encoding="utf-8") as fh:
                fh.write("coach,start_date,end_date\n")
                for x in comp:
                    fh.write(f'{x["coach"]},{x["start_date"]},{x["end_date"]}\n')

        dst = args.out / f"coach_eras_{sin_acentos(club).lower().replace(' ', '_')}.csv"
        campos = list(filas[0].keys())
        with dst.open("w", encoding="utf-8") as fh:
            fh.write(",".join(campos) + "\n")
            for x in filas:
                fh.write(",".join(f'"{x[c]}"' for c in campos) + "\n")
        resumen.extend(filas)

        ok = sum(f["analizable"] for f in filas)
        print(f"  {club:20s} {len(filas):3d} eras, {ok:2d} analizables  -> {dst.name}")
        if args.detalle:
            for x in filas:
                print(f"      {x['start_date']} .. {x['end_date']}  "
                      f"{x['n_partidos']:3d}  {x['coach']:26s} {x['banderas']}")

    if args.dump_asignacion:
        sufijo = ("_" + sin_acentos(args.club).lower().replace(" ", "_")
                  if args.club else "")
        for nombre, filas_d in (("asignacion_partidos", asig),
                                ("absorbidos", absorbidos)):
            d = args.out / f"{nombre}{sufijo}.csv"
            campos_d = ["club", "match_id", "match_date", "era", "era_start",
                        "era_end", "coach_real", "coach_id_real",
                        "dirigio_la_era"]
            with d.open("w", encoding="utf-8") as fh:
                fh.write(",".join(campos_d) + "\n")
                for x in sorted(filas_d, key=lambda z: (z["club"], z["match_date"])):
                    fh.write(",".join(f'"{x[c]}"' for c in campos_d) + "\n")
            print(f"  dump -> {d}  ({len(filas_d)} filas)")
        if absorbidos:
            print(f"\n  PARTIDOS ABSORBIDOS POR FUSION: {len(absorbidos)}")
            print("  Estan dentro del rango de una era y los dirigio OTRO DT.")
            print("  El compat de 3 columnas no puede expresar el hueco: o se")
            print("  toleran y se declara, o se excluyen en phase0.\n")
            for x in sorted(absorbidos, key=lambda z: (z["club"], z["match_date"])):
                print(f"      {x['match_date']}  {x['club']:20s} "
                      f"match {x['match_id']}  dirigio {x['coach_real']}  "
                      f"-> contado como {x['era']}")

    if args.club:
        # NO sobrescribir el global en una corrida de un solo club:
        # ya paso dos veces y deja el archivo con 4 y con 10 filas.
        print("\n  (--club: no se reescribe eras_todas.csv)")
        return 0

    glob = args.out / "eras_todas.csv"
    campos = list(resumen[0].keys())
    with glob.open("w", encoding="utf-8") as fh:
        fh.write(",".join(campos) + "\n")
        for x in resumen:
            fh.write(",".join(f'"{x[c]}"' for c in campos) + "\n")

    ok = sum(x["analizable"] for x in resumen)
    print(f"\n  TOTAL: {len(resumen)} eras, {ok} analizables (>={args.min_partidos})")
    print(f"  global -> {glob}")
    if args.compat:
        print(f"  compat (3 columnas, para eras.load_eras) -> {args.compat}/")
    print(f"\n  A VERIFICAR A MANO: {n_verificar} fronteras marcadas "
          f"PRIMERA_DE_VENTANA.")
    print("  Es donde el API fallo en el America (Herrera -> Solari).")
    print("  Las demas fronteras el API las acerto; verificar por muestreo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
