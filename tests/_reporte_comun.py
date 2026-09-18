"""Utilidades compartidas por los tests del informe (H7)."""
import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"
REPORTS = RAIZ / "reports"
sys.path.insert(0, str(SCRIPTS))


def carga(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / archivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = carga("reporte_h7", "12_reporte_html.py")
humo = carga("humo_h7", "humo_reporte.py")


def modelo_desde(dir_reports: Path):
    J, traza = gen.recolecta(dir_reports, dir_reports / "no_existe.parquet")
    datos, M = gen.construye(J, traza)
    pagina = gen.HTML.replace("__DATOS__", json.dumps(datos, ensure_ascii=False))
    return datos, M, pagina


def hay_reales():
    return all((REPORTS / n).exists() for n, _ in gen.FUENTES.values())
