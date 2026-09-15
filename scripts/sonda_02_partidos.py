import sys
from statsbombpy import sb

cid, sid = int(sys.argv[1]), int(sys.argv[2])

m = sb.matches(competition_id=cid, season_id=sid)
print("Partidos:", len(m))
print("\nColumnas con manager/week/date:")
print([x for x in m.columns if any(k in x for k in ("manager", "week", "date"))])

ver = [x for x in ["match_id", "match_date", "match_week", "home_team",
                   "away_team", "home_managers", "away_managers",
                   "home_manager_name", "away_manager_name"]
       if x in m.columns]
print("\n", m[ver].head(8).to_string(index=False))

print("\nEquipos distintos:", sorted(set(m.home_team) | set(m.away_team)))

mid = int(m.match_id.iloc[0])
e = sb.events(match_id=mid)
print(f"\nEventos del partido {mid}:", len(e))
print("Columnas:", len(e.columns))

clave = ["id", "index", "match_id", "period", "minute", "second", "type",
         "team", "possession", "possession_team", "play_pattern", "location",
         "duration", "pass_end_location", "carry_end_location",
         "shot_statsbomb_xg", "shot_freeze_frame", "under_pressure",
         "counterpress", "player_id", "obv_total_net", "obv_for_net"]
for k in clave:
    print(("  OK  " if k in e.columns else "  FALTA  ") + k)
