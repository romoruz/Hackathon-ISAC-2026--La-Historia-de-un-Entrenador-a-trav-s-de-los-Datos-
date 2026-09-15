import os
from statsbombpy import sb

assert os.environ.get("SB_USERNAME"), "Falta export SB_USERNAME"
assert os.environ.get("SB_PASSWORD"), "Falta export SB_PASSWORD"

c = sb.competitions()
print("Total de competencias con acceso:", len(c))
print()

mex = c[
    c.country_name.str.contains("Mexico", case=False, na=False)
    | c.competition_name.str.contains("Liga MX|Mexic", case=False, na=False)
]

cols = [x for x in ["competition_id", "season_id", "country_name",
                    "competition_name", "season_name",
                    "match_available", "match_available_360"]
        if x in c.columns]

if len(mex):
    print(mex[cols].to_string(index=False))
else:
    print("Nada con 'Mexico'. Lista completa de paises/competencias:")
    print(c[["country_name", "competition_name", "season_name"]]
          .drop_duplicates().to_string(index=False))
