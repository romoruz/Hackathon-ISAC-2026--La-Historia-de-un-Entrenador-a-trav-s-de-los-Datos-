import gzip, json, csv
from collections import defaultdict
from pathlib import Path
OUT = Path("data/raw_api")

def nom(d, *ks):
    for k in ks:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d

# ---------- 0. el bloque managers crudo, sin truncar
print("=" * 70); print("0. BLOQUE 'managers' CRUDO"); print("=" * 70)
for p in sorted((OUT / "matches").glob("*_108.json.gz")):
    for m in json.loads(gzip.decompress(p.read_bytes())).values():
        if str(m.get("match_date"))[:10] == "2021-07-23" and \
           "América" in json.dumps(m, ensure_ascii=False):
            for lado in ("home", "away"):
                print(f"--- {lado}: {nom(m, lado+'_team', lado+'_team_name')}")
                print(json.dumps((m.get(lado+"_team") or {}).get("managers"),
                                 ensure_ascii=False, indent=2))
            break
    else:
        continue
    break

# ---------- carga
reg = defaultdict(list)          # (club) -> [(fecha, dt)]
por_dt = defaultdict(list)       # dt -> [(fecha, club)]
for p in sorted((OUT / "matches").glob("*.json.gz")):
    for m in json.loads(gzip.decompress(p.read_bytes())).values():
        f = str(m.get("match_date"))[:10]
        if not f or f == "None":
            continue
        for lado in ("home", "away"):
            eq = str(nom(m, f"{lado}_team", f"{lado}_team_name"))
            ms = (m.get(f"{lado}_team") or {}).get("managers")
            if isinstance(ms, list) and ms:
                if len(ms) > 1:
                    print(f"  OJO: {len(ms)} managers en {f} {eq}")
                reg[eq].append((f, ms[0]["name"]))
                por_dt[ms[0]["name"]].append((f, eq))

# ---------- 1. un DT en dos clubes el mismo mes
print("\n" + "=" * 70); print("1. SOLAPAMIENTOS (un DT en 2 clubes a la vez)"); print("=" * 70)
hallados = 0
for dt, v in por_dt.items():
    pormes = defaultdict(set)
    for f, c in v:
        pormes[f[:7]].add(c)
    malos = {k: s for k, s in pormes.items() if len(s) > 1}
    if malos:
        hallados += 1
        print(f"  {dt}:")
        for k in sorted(malos):
            print(f"      {k}  ->  {sorted(malos[k])}")
print(f"  total: {hallados}" if hallados else "  ninguno. El campo es consistente.")

# ---------- 2. contra tus CSV verificados a mano
print("\n" + "=" * 70); print("2. API vs TUS ERAS VERIFICADAS"); print("=" * 70)
for club, ruta in (("América", "data/coach_eras.csv"),
                   ("Cruz Azul", "data/coach_eras_cruz_azul.csv")):
    pr = Path(ruta)
    if not pr.exists():
        print(f"\n  {club}: no encuentro {ruta}"); continue
    mias = list(csv.DictReader(pr.open(encoding="utf-8")))
    print(f"\n  --- {club} ---")
    print(f"  {'fecha':12s} {'mi CSV':22s} {'API':38s}")
    seq = sorted(reg[club])
    prev_api = prev_mio = None
    for f, dtapi in seq:
        mio = next((e["coach"] for e in mias
                    if e["start_date"] <= f <= e["end_date"]), "(sin era)")
        if dtapi != prev_api or mio != prev_mio:
            ok = "" if prev_api is None else (
                "  OK" if (dtapi != prev_api) == (mio != prev_mio) else "  <<< DISCREPA")
            print(f"  {f:12s} {mio:22s} {dtapi:38s}{ok}")
        prev_api, prev_mio = dtapi, mio
