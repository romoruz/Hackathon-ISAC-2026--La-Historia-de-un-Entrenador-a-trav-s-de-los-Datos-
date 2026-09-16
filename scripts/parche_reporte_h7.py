#!/usr/bin/env python3
"""
parche_reporte_h7.py — adapta `12_reporte_html.py` al universo del API.

Se aplica UNA VEZ. Es idempotente: si ya esta aplicado, avisa y no toca nada.
Deja respaldo `12_reporte_html.py.anterior_AAAAMMDDHHMM`.

TRES CAMBIOS
============

1. BUG DE EMPAREJAMIENTO DE HUELLAS  (el grave)
-----------------------------------------------
    ap = a.split()[-1].lower()
    for c in REPORTS.glob("huella_*.parquet"):
        if ap in c.stem.lower():

Empareja por SUBCADENA de la ultima palabra. Con el universo viejo colaba de
milagro; con el nuevo no:

    "Diego Cocca I"   -> ap = "i"   -> "i" in "huella_andrejardine"  => True

Cocca I se quedaria con la huella del primer archivo que devuelva el glob. No
lanza excepcion: pinta el mapa de otro entrenador bajo su nombre. Es el bug
#12 (modelar a uno, rotular a otro) reaparecido.

Se sustituye por igualdad exacta contra `huella_<nombre sin espacios>`, el
mismo slug que emiten `generar_todo_h7.sh`, `ic_` y `plantel_`.

2. `CLUBES` DEJA DE ESTAR FIJO EN EL CODIGO
-------------------------------------------
Apuntaba a `data/processed` y `data/processed_cruzazul`, la epoca de dos
clubes. Ahora se construye leyendo `phase0_report.json` de cada slug de
`CLUBES_H7`, que es la terna preinscrita, y se puede ampliar con la variable
de entorno `DTDECODER_CLUBES=america,leon,atlas,tigres_uanl`.

El nombre del club NO se inventa: sale de `phase0_report.json`, que es el
mismo que usan `25_pares_h4.py` y `27_robustez_h4.py`. Si el reporte lo
escribiera distinto, las claves del JSON de pares no casarian y la tabla
saldria vacia sin decir por que.

3. LAS RUTAS DEL JAVASCRIPT
---------------------------
    const dir=n==="Cruz Azul"?"data/processed_cruzazul":"data/processed";
    const eq=n==="Cruz Azul"?"Cruz Azul":"América";

Solo alimentan el texto de ayuda que el reporte muestra cuando falta un
artefacto, pero ese texto es un comando que el lector puede copiar: si esta
mal, manda a correr el script sobre el club equivocado. Pasan a leerse de
`c.dir` y `c.team`, que el parche añade a cada club en los datos.

LO QUE NO HACE
==============
No toca la plantilla HTML ni el resto del JavaScript. No incrusta la tabla de
los 60 pares: eso es `28_tabla_pares.py` y una seccion nueva, que es trabajo
de diseno y necesita decidirse mirando la pagina.
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

RUTA = Path("scripts/12_reporte_html.py")

VIEJO_CLUBES = '''CLUBES = {
    "Club América": {"dir": RAIZ / "data" / "processed", "team": "América"},
    "Cruz Azul": {"dir": RAIZ / "data" / "processed_cruzazul", "team": "Cruz Azul"},
}'''

NUEVO_CLUBES = '''# Clubes con seccion profunda. Criterio preinscrito por ROL EN EL ARGUMENTO,
# nunca por magnitud del efecto: America es el foco del reto, Leon aporta el
# control negativo (equivalencia preinscrita) y Atlas el limite del metodo
# (Cocca I vs Cocca II: un tecnico difiere de si mismo).
# Ampliable sin tocar el codigo:  DTDECODER_CLUBES=america,leon,atlas,...
CLUBES_H7 = os.environ.get("DTDECODER_CLUBES", "america,leon,atlas").split(",")


def _descubre_clubes() -> dict:
    """Construye CLUBES desde `phase0_report.json`, no desde nombres a mano.

    El nombre del club tiene que ser EL MISMO que usan 25_pares_h4.py y
    27_robustez_h4.py, porque las claves de `pares_h4_v5.json` vienen de ahi.
    Si el reporte lo escribiera distinto ("Club León" contra "León"), la tabla
    de pares no casaria y la seccion saldria vacia sin decir por que.
    """
    out: dict = {}
    for slug in [s.strip() for s in CLUBES_H7 if s.strip()]:
        d = RAIZ / "data" / f"processed_api_{slug}"
        rp = d / "phase0_report.json"
        if not (d / "transitions.parquet").exists():
            print(f"[salto] {slug}: sin transitions.parquet en {d}",
                  file=sys.stderr)
            continue
        equipo = None
        if rp.exists():
            equipo = (json.loads(rp.read_text()).get("coaches") or {}).get("club")
        if not equipo:
            print(f"[salto] {slug}: phase0_report.json sin nombre de club",
                  file=sys.stderr)
            continue
        out[equipo] = {"dir": d, "team": equipo, "slug": slug}
    if not out:
        print("NINGUN club disponible. Revisa data/processed_api_*.",
              file=sys.stderr)
    return out


CLUBES = _descubre_clubes()'''

VIEJO_HUELLA = '''        for a in lista:
            ap = a.split()[-1].lower()
            for c in REPORTS.glob("huella_*.parquet"):
                if ap in c.stem.lower():'''

NUEVO_HUELLA = '''        for a in lista:
            # Igualdad EXACTA contra el slug, no subcadena de la ultima
            # palabra. La version anterior hacia `ap = a.split()[-1].lower()`
            # y `if ap in c.stem.lower()`: para "Diego Cocca I" eso da
            # ap = "i", y "i" esta dentro de casi cualquier nombre de
            # archivo. Cocca I se quedaba con la huella del primer parquet
            # que devolviera el glob, sin error ni aviso.
            ap = a.replace(" ", "").lower()
            for c in REPORTS.glob("huella_*.parquet"):
                if c.stem.lower() == f"huella_{ap}":'''

VIEJO_CLUBDICT = '''        club = {"entrenadores": lista,
                "posesiones": dict(zip(lista, dts["n"].to_list())),
                "pares": {}, "huella": {}, "jugadores": {}, "cadena": {}}'''

NUEVO_CLUBDICT = '''        club = {"entrenadores": lista,
                "posesiones": dict(zip(lista, dts["n"].to_list())),
                # `dir` y `team` viajan a los datos porque el JavaScript los
                # necesita para componer el comando de ayuda que se muestra
                # cuando falta un artefacto. Antes los deducia de un ternario
                # con dos clubes escritos a mano.
                "dir": str(cfg["dir"].relative_to(RAIZ)),
                "team": equipo,
                "pares": {}, "huella": {}, "jugadores": {}, "cadena": {}}'''

VIEJO_JS = ''' const dir=n==="Cruz Azul"?"data/processed_cruzazul":"data/processed";
 const eq=n==="Cruz Azul"?"Cruz Azul":"América";'''

NUEVO_JS = ''' /* La ruta y el equipo vienen de los datos, no de un ternario con dos
    clubes escritos a mano: este texto es un comando que el lector copia y
    pega, y apuntar al club equivocado es peor que no mostrarlo. */
 const dir=c.dir||"data/processed";
 const eq=c.team||n;'''


def main() -> int:
    if not RUTA.exists():
        sys.exit(f"no encuentro {RUTA}. Corre esto desde la raiz del repo.")
    s = RUTA.read_text()

    if "_descubre_clubes" in s:
        print("El parche YA esta aplicado. No se toca nada.")
        return 0

    faltan = [n for n, v in (("CLUBES", VIEJO_CLUBES),
                             ("huella", VIEJO_HUELLA),
                             ("club_dict", VIEJO_CLUBDICT),
                             ("js", VIEJO_JS)) if v not in s]
    if faltan:
        sys.exit(f"no encuentro los bloques {faltan}. El archivo cambio "
                 f"respecto al que se audito; NO se aplica nada.")

    sello = dt.datetime.now().strftime("%Y%m%d%H%M")
    resp = RUTA.with_suffix(f".py.anterior_{sello}")
    shutil.copy2(RUTA, resp)
    print(f"respaldo -> {resp}")

    s = s.replace(VIEJO_CLUBES, NUEVO_CLUBES)
    s = s.replace(VIEJO_HUELLA, NUEVO_HUELLA)
    s = s.replace(VIEJO_CLUBDICT, NUEVO_CLUBDICT)
    s = s.replace(VIEJO_JS, NUEVO_JS)

    # `os` hace falta para leer la variable de entorno
    if "\nimport os\n" not in s:
        s = s.replace("\nimport json\n", "\nimport json\nimport os\n", 1)

    RUTA.write_text(s)

    import ast
    try:
        ast.parse(s)
    except SyntaxError as e:
        shutil.copy2(resp, RUTA)
        sys.exit(f"el resultado NO compila ({e}); revertido al respaldo.")

    print("parche aplicado y compila.")
    print("\nComprueba antes de generar:")
    print("  python scripts/verifica_reporte.py")
    print("  python -c \"import runpy,sys; sys.argv=['x','--help']; "
          "runpy.run_path('scripts/12_reporte_html.py', run_name='__main__')\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
