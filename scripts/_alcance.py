"""
_alcance.py — LA regla de alcance. Una sola implementacion, dos consumidores.

POR QUE EXISTE
--------------
`01_construir_eras.py` y `02_adaptar_eventos.py` tienen que producir
EXACTAMENTE el mismo universo de partidos: uno decide a que entrenador
pertenece cada partido, el otro decide que eventos entran al parquet. Si sus
reglas divergen aunque sea en una etapa, `phase0` cuenta partidos que ninguna
era cubre, o eras que reclaman partidos que no estan en los eventos.

Hasta el 2026-09-14 la regla estaba escrita dos veces, distinto:

    01_construir_eras.es_regular  -> excluia por palabras clave, nada mas
    02_adaptar_eventos.quiero     -> ademas exigia startswith(apertura|...)

Sobre las 21 etapas presentes en el indice del 2026-09-14 las dos coinciden.
Nadie lo habia comprobado. Es la trampa "umbrales distintos entre scripts"
de 13_CONTEXTO_IA §6, aplicada a la decision 3 de 16_MIGRACION_API.

REGLA (decision 3, 16_MIGRACION_API.md §4)
------------------------------------------
Entra al ajuste la FASE REGULAR. Quedan fuera liguilla, repechaje,
reclasificacion y play-in, que se reportan como sensibilidad.

La etiqueta `competition_stage` es inconsistente entre temporadas (la 235 dice
'Regular Season' donde las otras dicen 'Apertura'), asi que se reconoce por
prefijo Y por exclusion de las fases finales. Una etapa que no case con
ninguna de las dos listas NO se adivina: se clasifica DESCONOCIDA y el
consumidor avisa en voz alta. Adivinar en silencio es como se cuelan los
errores de esta clase.
"""

from __future__ import annotations

# Prefijos que identifican fase regular. `regular` cubre 'Regular Season'.
PREFIJOS_REGULAR = ("apertura", "clausura", "regular")

# Cualquiera de estas subcadenas marca fase final, aunque el prefijo case:
# 'Apertura - Quarter-finals' empieza con 'apertura' y NO es fase regular.
CLAVES_FINAL = ("final", "semi", "quarter", "reclasific", "play", "repechaje")

REGULAR = "regular"
LIGUILLA = "liguilla"
DESCONOCIDA = "DESCONOCIDA"


def clasificar(etapa: str | None) -> str:
    """-> 'regular' | 'liguilla' | 'DESCONOCIDA'."""
    e = (etapa or "").strip().lower()
    if not e:
        return DESCONOCIDA
    if any(k in e for k in CLAVES_FINAL):
        return LIGUILLA
    if e.startswith(PREFIJOS_REGULAR):
        return REGULAR
    return DESCONOCIDA


def es_regular(etapa: str | None) -> bool:
    """True solo para fase regular reconocida. DESCONOCIDA -> False.

    El default conservador es EXCLUIR: un partido de mas en el ajuste
    contamina una era en silencio; un partido de menos sale en el conteo y
    se nota.
    """
    return clasificar(etapa) == REGULAR


def auditar(etapas) -> dict[str, list[str]]:
    """Agrupa un iterable de etiquetas por clasificacion. Para imprimir."""
    out: dict[str, list[str]] = {REGULAR: [], LIGUILLA: [], DESCONOCIDA: []}
    for e in sorted({str(x) for x in etapas}):
        out[clasificar(e)].append(e)
    return out


def avisar_desconocidas(etapas, donde: str = "") -> int:
    """Imprime las etapas que ninguna regla reconoce. Devuelve cuantas hay."""
    desc = auditar(etapas)[DESCONOCIDA]
    if desc:
        print(f"\n  [ALCANCE] {len(desc)} etapa(s) NO reconocida(s){' en ' + donde if donde else ''}:")
        for e in desc:
            print(f"      {e!r}")
        print("      Se EXCLUYEN por defecto. Si alguna es fase regular, "
              "anadela a PREFIJOS_REGULAR en scripts/_alcance.py")
    return len(desc)


if __name__ == "__main__":
    # Auditoria rapida:  python scripts/_alcance.py
    import csv
    import sys
    from collections import Counter
    from pathlib import Path

    ruta = Path(sys.argv[1] if len(sys.argv) > 1
                else "data/raw_api/indice_partidos.csv")
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}")
    et = Counter(r["stage"] for r in csv.DictReader(ruta.open(encoding="utf-8")))
    grupos = auditar(et)
    for k in (REGULAR, LIGUILLA, DESCONOCIDA):
        n = sum(et[e] for e in grupos[k])
        print(f"\n{k.upper()}  ({len(grupos[k])} etiquetas, {n} partidos)")
        for e in grupos[k]:
            print(f"    {et[e]:5d}  {e}")
