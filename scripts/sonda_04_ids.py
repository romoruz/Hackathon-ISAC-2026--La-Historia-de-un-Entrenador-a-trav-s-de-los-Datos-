import pandas as pd
from statsbombpy import sb

CSV = "eventos_completos_america.csv"
mios = set(pd.read_csv(CSV, usecols=["match_id"]).match_id.unique())
print("match_id en mi volcado:", len(mios))

api = set()
for sid in [351, 318, 317, 281, 235, 108]:
    api |= set(sb.matches(competition_id=73, season_id=sid).match_id)
print("match_id en el API:", len(api))
print("interseccion:", len(mios & api))
print("mios que el API no tiene:", len(mios - api))
