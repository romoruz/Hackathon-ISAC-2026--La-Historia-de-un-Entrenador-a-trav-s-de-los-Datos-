#!/usr/bin/env python3
"""Revisa los cuatro parches que no encontraron su anclaje.

`anclaje x0` significa dos cosas distintas y hay que separarlas:

  · el contenido YA ESTÁ, escrito de otra forma  → no hay nada que hacer
  · el contenido FALTA y el texto que buscaba cambió → hay que arreglarlo

Este script mira el contenido, no el anclaje.
"""
import re
import sys
from pathlib import Path

raiz = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
docs = raiz / "docs"

CASOS = [
    ("13_CONTEXTO_IA.md", "las columnas del parquet",
     [(r"score_state_club", "menciona `score_state_club`"),
      (r"coach_faced", "menciona `coach_faced`"),
      (r"under_pressure", "menciona `under_pressure`"),
      (r"ENTERO|enteros", "avisa de que los estados son ENTEROS")]),
    ("08_REPRODUCIBILITY.md", "el lockfile en la tabla de §1",
     [(r"falta \*?lockfile", "AÚN dice que falta el lockfile  ← revisar"),
      (r"uv\.lock.*versionad|✅.*uv\.lock", "dice que uv.lock existe")]),
    ("14_LIMPIEZA_REPO.md", "las carpetas de instaladores en §3.1",
     [(r"tarball.*extrae|instalaci[óo]n al extraer|\*\.anterior",
       "menciona las carpetas de instaladores")]),
    ("02_STATE_OF_PLAY.md", "§10 siguiente acción",
     [(r"min_carry_length", "sigue listando min_carry_length"),
       (r"shot_statsbomb_xg.*hecha|✅ \*\*hecha\*\*",
        "marca la validación externa como hecha"),
      (r"ADR-50|predictivo espacial", "menciona el chequeo espacial")]),
]

print(f"revisando {raiz}\n")
pendientes = 0
for archivo, que, comprobaciones in CASOS:
    p = docs / archivo
    print("=" * 66)
    print(f"{archivo} — {que}")
    if not p.exists():
        print("  el archivo no existe")
        continue
    t = p.read_text(encoding="utf-8")
    for patron, desc in comprobaciones:
        hay = bool(re.search(patron, t, re.I))
        marca = "sí " if hay else "NO "
        alerta = "  ← revisar" in desc
        if (not hay and not alerta) or (hay and alerta):
            pendientes += 1
            marca = "!! "
        print(f"  {marca} {desc}")

print("\n" + "=" * 66)
if pendientes:
    print(f"{pendientes} cosas que revisar. Las marcadas con !! son las que faltan\n"
          "o las que contradicen el estado real.")
else:
    print("Nada pendiente: los cuatro parches no aplicaron porque el contenido\n"
          "ya estaba, escrito de otra forma. El `anclaje x0` era benigno.")
