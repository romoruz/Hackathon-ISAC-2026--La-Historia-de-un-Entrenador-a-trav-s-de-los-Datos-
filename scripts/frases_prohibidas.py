"""Lista de frases prohibidas de ADR-59 §3 (y adenda 2 §8), como expresiones regulares.

La usan tres sitios: `12_reporte_html.py` (aborta si su salida contiene una),
`tests/test_frases_prohibidas.py` y la guía LaTeX. Un solo lugar para la lista.

El texto se normaliza antes de buscar: minúsculas y sin acentos, para que
"Significativo" y "significativo" caigan igual.
"""
from __future__ import annotations

import re
import unicodedata

# (patrón sobre texto normalizado, motivo según ADR-59 §3)
PROHIBIDAS: list[tuple[str, str]] = [
    (r"\bel exito de\b", "rendimiento / causal"),
    (r"\bgracias a\b", "causal"),
    (r"\bpermite[n]? sostener", "causal (tesis vieja del Proyecto)"),
    (r"\bpara sobrevivir al calendario", "intención"),
    (r"\bse apoya[n]? en\b", "causal"),
    (r"\bprovoc\w*", "causal"),
    (r"\bexplic\w*", "causal"),
    (r"\b(mejor|peor)(es)? (tecnico|entrenador|dt)\w*", "rendimiento"),
    (r"\bfirma (tactica|inalterable|del tecnico|propia)", "rasgo fijo del técnico"),
    (r"\badn\b", "rasgo fijo del técnico"),
    (r"\bno hay efecto", "nulo mal redactado"),
    (r"\bsignificativ\w*", "prohibido en B y C; en A se dice 'difiere'"),
    (r"\bimpone\w*|\bimponer\b", "intención como hecho"),
    # adenda 2 §8: las notas internas del roadmap no pasan a la página
    (r"\bpesa\w* mas que\b", "comparación de pesos entre club y técnico (ADR-59 §8)"),
    (r"\bdemuestra\w* que\b", "lenguaje de prueba fuera de nivel A"),
    (r"\bsu idea\b", "rasgo fijo del técnico"),
    # ADR-60 §7: la descomposición es un reparto contable, no una causa
    (r"\bse debe[n]? al?\b", "causal (ADR-60 §7)"),
    (r"\bpor culpa de\b", "causal (ADR-60 §7)"),
]

# "se adapta" solo vale dentro de "es compatible con ..." (nivel C)
_ADAPTA = re.compile(r"\b(se adapta\w*|adaptarse|adaptacion)\b")
_COMPATIBLE = re.compile(r"compatible con")


def normaliza(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower()


def revisa(texto: str) -> list[tuple[str, str, str]]:
    """Devuelve [(fragmento, patrón, motivo)] para cada frase prohibida."""
    t = normaliza(texto)
    malas = []
    for pat, motivo in PROHIBIDAS:
        for m in re.finditer(pat, t):
            a, b = max(0, m.start() - 40), min(len(t), m.end() + 40)
            malas.append((t[a:b].replace("\n", " "), pat, motivo))
    # "se adapta" fuera de una oración con "compatible con"
    for oracion in re.split(r"[.!?]\s", t):
        if _ADAPTA.search(oracion) and not _COMPATIBLE.search(oracion):
            malas.append((oracion[:90], _ADAPTA.pattern, "'se adapta' como hecho"))
    return malas
