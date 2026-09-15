import gzip, json, sys
from pathlib import Path
CLUB = sys.argv[1] if len(sys.argv) > 1 else "América"
OUT = Path("data/raw_api")

def nom(d, *ks):
    for k in ks:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d

filas = []
for p in sorted((OUT / "matches").glob("*.json.gz")):
    crudo = json.loads(gzip.decompress(p.read_bytes()))
    for m in (crudo.values() if isinstance(crudo, dict) else crudo):
        for lado, otro in (("home", "away"), ("away", "home")):
            eq = str(nom(m, f"{lado}_team", f"{lado}_team_name") or m.get(f"{lado}_team"))
            if eq != CLUB:
                continue
            ms = (m.get(f"{lado}_team", {}) or {}).get("managers") or m.get(f"{lado}_managers")
            dt = ms[0].get("name") if isinstance(ms, list) and ms else str(ms)
            filas.append((str(m.get("match_date"))[:10], m.get("match_week"),
                          str(nom(m, "competition_stage", "name"))[:22],
                          str(nom(m, f"{otro}_team", f"{otro}_team_name") or m.get(f"{otro}_team"))[:16],
                          dt))

filas.sort()
print(f"{CLUB}: {len(filas)} partidos\n")
prev = None
for f, j, et, riv, dt in filas:
    marca = "  <<< CAMBIO" if dt != prev else ""
    print(f"{f}  J{str(j):>3}  {et:22s}  {riv:16s}  {str(dt):35s}{marca}")
    prev = dt
