#!/usr/bin/env python3
"""Comprueba que la documentación no se contradiga a sí misma.

POR QUÉ EXISTE
--------------
La documentación de este proyecto llegó a decir tres cifras distintas para el
número de bugs (ocho, once, doce), a declarar el eje Y resuelto en un documento
y pendiente en otros tres, y a dar dos consejos opuestos sobre escalar a 18
equipos en la misma página.

Ninguna de esas contradicciones lanzó un error, porque la documentación no se
ejecuta. **Es exactamente el patrón de riesgo del proyecto, aplicado a la
prosa**: nada falla, y lo que lees es plausible y equivocado.

Este script es el `pytest -q` de los documentos. Correr después de tocar
cualquier `.md`.

Uso:
    python docs/verificar_docs.py
    python docs/verificar_docs.py --repo /ruta/al/Hackathon2026
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

fallos: list[str] = []
avisos: list[str] = []


def leer(raiz: Path) -> dict[str, str]:
    """Indexa por RUTA RELATIVA, no por nombre.

    `README.md` existe dos veces —en la raiz y en `docs/`— y al indexar por
    nombre el de la raiz pisaba al de `docs/`. La comprobacion del indice se
    ejecutaba entonces contra el README unificado del repositorio, que no lleva
    el indice de documentos, y fallaba siempre.
    """
    d = {}
    for p in sorted((raiz / "docs").glob("*.md")):
        d[f"docs/{p.name}"] = p.read_text(encoding="utf-8")
    for extra in ("README.md", "AGENTS.md"):
        q = raiz / extra
        if q.exists():
            d[extra] = q.read_text(encoding="utf-8")
    return d


def comprueba(nombre: str, ok: bool, detalle: str = "") -> None:
    print(("  ok    " if ok else "  FALLA ") + nombre + (f" — {detalle}" if detalle and not ok else ""))
    if not ok:
        fallos.append(nombre + (f": {detalle}" if detalle else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None)
    args = ap.parse_args()
    raiz = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parent.parent
    if not (raiz / "docs").is_dir():
        sys.exit(f"no encuentro {raiz}/docs")

    D = leer(raiz)
    todo = "\n".join(D.values())
    print(f"revisando {len(D)} documentos en {raiz}\n")

    # ---- 1. el conteo de bugs es único --------------------------------
    # Se quita el marcado ANTES de buscar. La version anterior fallaba con
    # «**ocho** bugs»: entre la cifra y la palabra hay «** », no un espacio, y
    # `\s+` no casaba. El chequeo decia verde con ocho, doce y catorce
    # conviviendo en cinco documentos. Es el patron del proyecto aplicado a su
    # propio verificador: un resultado plausible y equivocado, sin excepcion.
    plano = re.sub(r"[*_`]", "", todo)
    numeros = set()
    for m in re.finditer(r"\b(ocho|nueve|diez|once|doce|trece|catorce|quince|"
                         r"dieciseis|diecis[eé]is|diecisiete|dieciocho|"
                         r"diecinueve|veinte)\s+bugs", plano, re.I):
        numeros.add(m.group(1).lower())
    comprueba("el número de bugs es consistente en todos los documentos",
              len(numeros) <= 1, f"conviven {sorted(numeros)}")

    # ---- 2. el eje Y no está resuelto y pendiente a la vez -------------
    pendiente = [n for n, t in D.items()
                 if re.search(r"pendiente.{0,80}eje Y|eje Y.{0,60}pendiente", t, re.I | re.S)]
    comprueba("el eje Y no aparece como pendiente en ningún sitio",
              not pendiente, f"lo dan por pendiente: {pendiente}")

    # ---- 3. las afirmaciones retiradas no se citan como vivas ---------
    # Se buscan SOLO fuera del bloque de retractaciones, que es donde deben vivir.
    # Se busca la EVIDENCIA que se retiro, no el sujeto de la frase. La version
    # anterior buscaba "Anselmi sostiene la presion" y saltaba contra el
    # hallazgo VIVO de §18, que empieza igual. Un aviso que salta siempre
    # ensena a ignorarlo, y entonces deja de proteger.
    retiradas = [
        ("Jardine presiona mas que Solari",
         r"Jardine\s+presiona\s+m[áa]s\s+(al\s+rival\s+)?que\s+Solari"),
        ("Anselmi sostiene la presion con p=0.001",
         r"Anselmi[^.]{0,120}?p\s*=\s*0\.001"),
        ("Jardine gana mas balones al primer toque",
         r"Jardine[^.]{0,80}?gana\s+m[áa]s\s+balones"),
    ]
    hogar = "docs/10_RESULTADOS.md"      # donde SI deben estar, en el bloque §16
    for etiqueta, patron in retiradas:
        malos = [n for n, t in D.items()
                 if re.search(patron, t, re.I | re.S) and n != hogar
                 and "ACTUALIZACIONES" not in n and "historico" not in n]
        comprueba(f"la afirmacion retirada «{etiqueta}» no se cita como viva",
                  not malos, f"aparece en {malos}")

    # ---- 4. toda cifra de presión declara su estimando -----------------
    tiene_adr48 = "ADR-48" in todo
    comprueba("ADR-48 (dos estimandos de presión) está documentada", tiene_adr48)

    # ---- 5. las ADR referenciadas existen -----------------------------
    definidas = set(re.findall(r"^##\s+ADR-(\d+)", D.get("docs/06_DECISIONS.md", ""), re.M))
    citadas = set(re.findall(r"ADR-(\d+)", todo))
    huerfanas = sorted(int(x) for x in (citadas - definidas))
    comprueba("toda ADR citada está definida en 06_DECISIONS.md",
              not huerfanas, f"citadas y no definidas: {huerfanas}")

    # ---- 6. los enlaces internos apuntan a archivos que existen -------
    rotos = []
    for n, t in D.items():
        for destino in re.findall(r"\]\((\d\d_[A-Za-z_]+\.md)\)", t):
            if not (raiz / "docs" / destino).exists():
                rotos.append(f"{n} → {destino}")
    comprueba("los enlaces entre documentos apuntan a archivos existentes",
              not rotos, str(rotos))

    # ---- 7. el bloque defensivo está integrado ------------------------
    comprueba("los resultados D1 están en 10_RESULTADOS.md",
              "Bloque defensivo D1" in D.get("docs/10_RESULTADOS.md", ""))
    comprueba("03_METHODS ya no dice que el modelo es solo con balón",
              "El modelo describe solo la fase con balón"
              not in D.get("docs/03_METHODS.md", ""))

    # ---- 7b. la sobreafirmacion de tau^2 no vuelve --------------------
    # Se colo una vez: §25 se titulaba «El estilo de entrenador es medible».
    # tau^2 mide la varianza ENTRE ERAS, que contiene tambien plantel y
    # contexto. La etiqueta importa tanto como el numero.
    mal = [n for n, t in D.items()
           if re.search(r"estilo de entrenador\s+\**es\**\s+medible", t, re.I)
           and "historico" not in n and "ACTUALIZACIONES" not in n]
    comprueba("tau^2 no se presenta como «el estilo de entrenador es medible»",
              not mal, f"aparece en {mal}")
    comprueba("existe la seccion que explica que contiene tau^2",
              "Qué contiene $\\tau^2$" in D.get("docs/10_RESULTADOS.md", ""))

    # ---- 7c. la referencia de rivales no se llama «la liga» -----------
    liga = [n for n, t in D.items()
            if re.search(r"promedio de (toda )?la [Ll]iga MX", t)
            and "No es el promedio" not in t and "historico" not in n]
    comprueba("los rivales enfrentados no se llaman «el promedio de la Liga MX»",
              not liga, f"aparece en {liga}")

    # ---- 7d. el indice lista todos los documentos --------------------
    # El indice vive en `docs/README.md`; el de la raiz es la portada del
    # repositorio y no tiene por que listar los documentos.
    idx = D.get("docs/README.md", D.get("README.md", ""))
    faltan_idx = [f"{i:02d}" for i in range(16)
                  if list((raiz / "docs").glob(f"{i:02d}_*.md"))
                  and f"{i:02d}_" not in idx]
    comprueba("el índice del README lista todos los documentos",
              not faltan_idx, f"faltan {faltan_idx}")

    # ---- 8. el umbral de posesiones es el mismo en todas partes -------
    umbrales = set(re.findall(r"MIN_POS\w*\s*[=:]?\s*(\d{3,5})", todo))
    comprueba("MIN_POSESIONES / MIN_POSS coinciden",
              len(umbrales) <= 1, f"conviven {sorted(umbrales)}")

    # ---- 9. avisos (no bloquean) --------------------------------------
    if "ACTUALIZACIONES_DOCS.md" in D or "ACTUALIZACIONES_DOCS_v2.md" in D:
        avisos.append(
            "Los ACTUALIZACIONES_DOCS*.md siguen en docs/. Ya están integrados: "
            "muévelos a docs/historico/ con la nota de cabecera "
            "(14_LIMPIEZA_REPO.md §5).")
    if not (raiz / "AGENTS.md").exists():
        avisos.append("Falta AGENTS.md en la raíz: es el punto de entrada de los agentes.")
    if not (raiz / "uv.lock").exists():
        avisos.append("Falta uv.lock. `uv lock` y versionarlo (08_REPRODUCIBILITY §2).")
    if not (raiz / "LICENSE").exists():
        avisos.append("Falta LICENSE.")

    print()
    if avisos:
        print("AVISOS (no bloquean)")
        for a in avisos:
            print(f"  · {a}")
        print()
    if fallos:
        print(f"{len(fallos)} CONTRADICCIONES")
        sys.exit(1)
    print("documentación coherente")


if __name__ == "__main__":
    main()
