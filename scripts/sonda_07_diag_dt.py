import gzip, json
from collections import defaultdict
from pathlib import Path
OUT = Path("data/raw_api")

def nom(d, *ks):
    for k in ks:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d

# --- A) el bloque crudo de managers de un partido temprano del America
print("=" * 70)
print("A. BLOQUE CRUDO DE 'managers' (America, jornada 1 Apertura 2021)")
print("=" * 70)
for p in sorted((OUT / "matches").glob("*_108.json.gz")):
    crudo = json.loads(gzip.decompress(p.read_bytes()))
    for m in (crudo.values() if isinstance(crudo, dict) else crudo):
        if str(m.get("match_date"))[:10] == "2021-07-23":
            print(json.dumps(m, ensure_ascii=False, indent=2)[:2500])
            break

# --- B) cambios de DT por club y por torneo
print("\n" + "=" * 70)
print("B. CAMBIOS DE ENTRENADOR POR TORNEO (jul-dic = A, ene-jun = C)")
print("=" * 70)
reg = defaultdict(list)
for p in sorted((OUT / "matches").glob("*.json.gz")):
    crudo = json.loads(gzip.decompress(p.read_bytes()))
    for m in (crudo.values() if isinstance(crudo, dict) else crudo):
        f = str(m.get("match_date"))[:10]
        if not f or f == "None":
            continue
        anio, mes = int(f[:4]), int(f[5:7])
        torneo = f"A{anio}" if mes >= 7 else f"C{anio}"
        for lado in ("home", "away"):
            eq = str(nom(m, f"{lado}_team", f"{lado}_team_name") or m.get(f"{lado}_team"))
            ms = (m.get(f"{lado}_team", {}) or {}).get("managers") or m.get(f"{lado}_managers")
            dt = ms[0].get("name") if isinstance(ms, list) and ms else None
            if dt:
                reg[(eq, torneo)].append((f, dt))

torneos = sorted({t for _, t in reg})
clubes = sorted({c for c, _ in reg})
print(f"\n{'club':20s}" + "".join(f"{t:>7s}" for t in torneos))
for c in clubes:
    fila = f"{c:20s}"
    for t in torneos:
        v = sorted(reg.get((c, t), []))
        fila += f"{(len({d for _, d in v}) if v else 0):>7d}"
    print(fila)
print("\n(numero = entrenadores distintos vistos en ese torneo)")
print("Una columna entera de 1s es sospechosa: en Liga MX siempre hay ceses.")
