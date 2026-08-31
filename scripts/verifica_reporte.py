#!/usr/bin/env python3
"""Comprueba el HTML embebido en 12_reporte_html.py sin necesitar datos.

Tres cosas, ninguna de las cuales necesita `reports/`:
  1. el modulo importa y `HTML` existe
  2. el <script> es JavaScript sintacticamente valido (node --check)
  3. las etiquetas <div>/<section> del cuerpo estatico cierran

Es el equivalente barato de "corre sin error" para una plantilla que solo se
ejecuta en un navegador. No prueba los numeros; prueba que la pagina cargue.
"""
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent if AQUI.name == "scripts" else AQUI
ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "scripts" / "12_reporte_html.py"
if not ruta.exists():
    sys.exit(f"no encuentro {ruta}")
src = ruta.read_text()

m = re.search(r'^HTML = r"""(.*?)"""$', src, re.S | re.M)
assert m, "no encuentro la plantilla HTML"
html = m.group(1)

js = re.search(r"<script>(.*)</script>", html, re.S).group(1)
js = js.replace("__DATOS__", '{"clubes":{}}')
import shutil as _sh
if _sh.which("node") is None:
    print("node no esta instalado: me salto la comprobacion del JavaScript")
    r = None
else:
    chk = Path("/tmp/_dtdecoder_check.js")
    chk.write_text(js)
    r = subprocess.run(["node", "--check", str(chk)], capture_output=True, text=True)
if r is not None:
    if r.returncode:
        print(r.stderr)
        sys.exit("JS INVALIDO")
    print("js ok")

css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
if css.count("{") != css.count("}"):
    sys.exit(f"CSS descuadrado: {css.count('{')} llaves abren, {css.count('}')} cierran")
print("css ok")

# variables CSS usadas contra declaradas
declaradas = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
usadas = set(re.findall(r"var\((--[a-z0-9-]+)\)", html))
faltan = usadas - declaradas
if faltan:
    sys.exit(f"variables CSS usadas y NO declaradas: {sorted(faltan)}")
print(f"css vars ok ({len(declaradas)} declaradas)")
