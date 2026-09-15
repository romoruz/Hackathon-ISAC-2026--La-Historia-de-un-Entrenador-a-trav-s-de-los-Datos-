from statsbombpy import sb
import pandas as pd

SEASONS = [351, 318, 317, 281, 235, 108]
CID = 73
filas, equipos, dts = [], set(), set()

for sid in SEASONS:
    m = sb.matches(competition_id=CID, season_id=sid)
    equipos |= set(m.home_team) | set(m.away_team)
    for col in ("home_managers", "away_managers",
                "home_manager_name", "away_manager_name"):
        if col in m.columns:
            dts |= set(m[col].dropna().astype(str))
    filas.append({
        "season_id": sid,
        "season": m.season.iloc[0] if "season" in m.columns else "?",
        "partidos": len(m),
        "equipos": m[["home_team", "away_team"]].stack().nunique(),
        "con_360": int((m.match_status_360 == "available").sum())
                   if "match_status_360" in m.columns else -1,
        "disponibles": int((m.match_status == "available").sum())
                       if "match_status" in m.columns else -1,
        "etapas": m.competition_stage.nunique()
                  if "competition_stage" in m.columns else -1,
    })

t = pd.DataFrame(filas)
print(t.to_string(index=False))
print("\nTOTAL partidos:", t.partidos.sum())
print("Equipos distintos en la ventana:", len(equipos))
print(sorted(equipos))
print("\nEntrenadores distintos vistos:", len(dts))
