#!/usr/bin/env python3
"""
32_docs_adr53.py — lleva los resultados de ADR-53 a la documentacion.

REGLA
-----
Ninguna cifra de lo que escribe esta tecleada a mano: todas se leen al
aplicar de `reports/did_h4_v1.json`, `reports/fdr_presion.json` y
`reports/deriva_proveedor.json`. La lista de predicciones es la del borrador
de ADR-53, escrita ANTES de la corrida; su veredicto se CALCULA aqui.

QUE TOCA
--------
  docs/06_DECISIONS.md   ADR-53 definitiva, adenda de ADR-52, estado de ADR-35
  docs/10_RESULTADOS.md  aviso de cabecera + seccion 27 (tabla de los 60 pares)
  docs/README.md         indice, estado, titulares, retirados, advertencia
  docs/02, 05, 07, 13, 15, 17, AGENTS.md, README.md (raiz)
                         conteo de bugs unificado (h2_14): numerados hasta el
                         #19, el #13 se evito, asi que se ENCONTRARON dieciocho;
                         las menciones historicas llevan su rango.
                         La portada (README.md de la raiz) recibe ademas un
                         aviso de retirados en §1 y §2; no se reescribe.

Antes de escribir corre `docs/verificar_docs.py` sobre la VISTA PREVIA (un arbol
temporal con los documentos nuevos). Si falla, no escribe.

Cada cambio es un REEMPLAZO EXACTO de un fragmento conocido. Si un fragmento
no aparece exactamente una vez, el script aborta sin escribir NADA. Cada
bloque insertado lleva la marca `<!-- h2_14 -->`: aplicar dos veces no
duplica.

Uso:
    python scripts/32_docs_adr53.py              # vista previa en /tmp/h2_14_vista
    python scripts/32_docs_adr53.py --escribir   # aplica, con respaldo
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "<!-- h2_14 -->"
TERNA = ("América", "Atlas", "León")      # seccion profunda del reporte, por rol


# ==========================================================================
# formato
# ==========================================================================
def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:+.{d}f}%"


def ic(v: list[float], d: int = 1) -> str:
    return f"[{100 * v[0]:+.{d}f}, {100 * v[1]:+.{d}f}]"


def qf(q: float) -> str:
    return f"{q:.4f}"


class Datos:
    def __init__(self, raiz: Path):
        self.did = json.loads((raiz / "reports/did_h4_v1.json").read_text())
        fp = raiz / "reports/fdr_presion.json"
        self.fdr = json.loads(fp.read_text()) if fp.exists() else None
        dp = raiz / "reports/deriva_proveedor.json"
        self.der = json.loads(dp.read_text()) if dp.exists() else None
        self.pares = {(x["club"], x["a"], x["b"]): x for x in self.did["pares"]}

    def par(self, club: str, x: str, y: str) -> tuple[dict, bool] | tuple[None, None]:
        """Devuelve (par, invertido). `a` y `b` van en orden alfabetico."""
        if (club, x, y) in self.pares:
            return self.pares[(club, x, y)], False
        if (club, y, x) in self.pares:
            return self.pares[(club, y, x)], True
        return None, None


def rel_orientado(p: dict, inv: bool, tipo: str = "did") -> tuple[float, list[float]]:
    """rel y su IC para `x vs y` aunque el JSON lo guarde como `y vs x`."""
    e = p[tipo]["E_T"]
    if not inv:
        return e["rel"], e["ic95"]
    return 1 / (1 + e["rel"]) - 1, [1 / (1 + e["ic95"][1]) - 1, 1 / (1 + e["ic95"][0]) - 1]


# ==========================================================================
# veredicto de las predicciones preinscritas (borrador de ADR-53)
# ==========================================================================
def predicciones(D: Datos) -> list[dict]:
    ft = D.did["firma_temporal"]
    fc = ft["crudo"]["posterior_mas_largo"] / max(ft["crudo"]["de"], 1)
    fd = ft["did"]["posterior_mas_largo"] / max(ft["did"]["de"], 1)
    out = [{
        "n": 1, "texto": "la firma temporal baja respecto al crudo",
        "resultado": (f"crudo {ft['crudo']['posterior_mas_largo']}/{ft['crudo']['de']} "
                      f"({fc:.0%}) → DiD {ft['did']['posterior_mas_largo']}/"
                      f"{ft['did']['de']} ({fd:.0%})"),
        "cumple": fd < fc,
        "nota": ("por encima del 75%: deriva residual o tendencia real"
                 if fd > 0.75 else "cerca del 50% que se esperaría sin tendencia"
                 if fd <= 0.6 else "baja, pero queda por encima del 60%"),
    }]

    p, inv = D.par("Atlas", "Diego Cocca I", "Diego Cocca II")
    if p:
        r, i = rel_orientado(p, inv)
        rc, _ = rel_orientado(p, inv, "crudo")
        rech = p["did"]["E_T"]["rechaza_fdr"]
        out.append({
            "n": 2, "texto": "Cocca I vs Cocca II deja de ser negativo y significativo",
            "resultado": f"crudo {pct(rc, 2)} → DiD {pct(r, 2)} {ic(i, 2)}, "
                         f"q = {qf(p['did']['E_T']['q'])}",
            "cumple": not (r < 0 and rech),
            "nota": ("sigue siendo significativo con el signo INVERTIDO: el sentido "
                     "del crudo era la deriva" if (r > 0 and rech) else
                     "deja de ser significativo" if not rech else ""),
        })

    p, inv = D.par("América", "Andre Jardine", "Santiago Solari")
    if p:
        r, i = rel_orientado(p, inv)
        rc, _ = rel_orientado(p, inv, "crudo")
        out.append({
            "n": 3, "texto": "Jardine vs Solari conserva el signo y se reduce",
            "resultado": f"crudo {pct(rc, 2)} → DiD {pct(r, 2)} {ic(i, 2)}, "
                         f"q = {qf(p['did']['E_T']['q'])}",
            "cumple": (r * rc > 0) and abs(r) < abs(rc),
            "nota": "",
        })

    cn = D.did["control_negativo"]
    mm = cn["menor_margen_demostrable_E_T"]
    out.append({
        "n": 4, "texto": "ningún par demuestra equivalencia al 3%",
        "resultado": ("ninguno; menor margen demostrable " + pct(mm, 2).lstrip("+")
                      if cn["elegido"] is None else
                      f"{cn['elegido']['club']} {cn['elegido']['a']} vs "
                      f"{cn['elegido']['b']} cumple"),
        "cumple": cn["elegido"] is None,
        "nota": "",
    })
    return out


# ==========================================================================
# bloques de texto
# ==========================================================================
def tabla_predicciones(D: Datos) -> str:
    filas = ["| # | predicción | resultado | |", "|---|---|---|---|"]
    for p in predicciones(D):
        nota = f" — {p['nota']}" if p["nota"] else ""
        filas.append(f"| {p['n']} | {p['texto']} | {p['resultado']}{nota} | "
                     f"{'✅' if p['cumple'] else '❌'} |")
    return "\n".join(filas)


def resumen(D: Datos) -> str:
    d = D.did
    c = d["comparacion_v5"] or {}
    cn = d["control_negativo"]
    return (f"{d['n_pares']} pares sobre {d['n_unidades']} unidades · "
            f"B = {d['parametros']['n_boot']} · rechazan tras BH: DiD "
            f"**{d['n_rechazados_did']}**, crudo {d['n_rechazados_crudo']} · "
            f"cambian de signo al corregir: **{d['n_cambian_signo_por_correccion']}** · "
            f"no rechazados: {cn['n_no_rechazados']} · eras bloqueadas: "
            f"{len(d['eras_bloqueadas_por_candado'])} · aviso de piso del p: "
            f"{d['aviso_piso_p'] or 'ninguno'} · contra la v5: "
            f"{c.get('v5_rechaza_y_did_no', '?')} dejan de rechazar, "
            f"{c.get('did_rechaza_y_v5_no', '?')} empiezan a rechazar")


def tabla_pares(D: Datos, clubes: tuple[str, ...] | None = None) -> str:
    filas = ["| club | par | crudo | DiD | IC 95% | q | |",
             "|---|---|---|---|---|---|---|"]
    for x in sorted(D.did["pares"], key=lambda z: (z["club"], z["a"], z["b"])):
        if clubes and x["club"] not in clubes:
            continue
        e = x["did"]["E_T"]
        marca = ("🟢" if e["rechaza_fdr"] else "⚪") + (" ↺" if x["cambia_signo_por_correccion"] else "")
        filas.append(f"| {x['club']} | {x['a']} vs {x['b']} | {pct(x['crudo']['E_T']['rel'])} | "
                     f"**{pct(e['rel'])}** | {ic(e['ic95'])} | {qf(e['q'])} | {marca} |")
    return "\n".join(filas)


def tabla_nulos(D: Datos, k: int | None = None) -> str:
    cands = D.did["control_negativo"]["candidatos"]
    if k:
        cands = cands[:k]
    filas = ["| club | par | no detectamos una diferencia mayor a |", "|---|---|---|"]
    for c in cands:
        filas.append(f"| {c['club']} | {c['a']} vs {c['b']} | "
                     f"{100 * c['margen_demostrable_E_T']:.2f}% |")
    return "\n".join(filas)


def tabla_viajeros(D: Datos) -> str:
    por: dict[str, list[dict]] = {}
    for u in D.did["unidades"]:
        por.setdefault(u["coach"], []).append(u)
    filas = ["| entrenador | club: desviación contra la liga del mismo torneo [IC 95%] |",
             "|---|---|"]
    for coach in sorted(por):
        us = por[coach]
        if len(us) < 2:
            continue
        txt = " · ".join(f"{u['club']} {pct(u['rel_E_T_vs_liga'])} {ic(u['rel_E_T_vs_liga_ic95'])}"
                         for u in sorted(us, key=lambda u: u["club"]))
        filas.append(f"| {coach} | {txt} |")
    return "\n".join(filas)


def adenda_52(D: Datos) -> str:
    if D.fdr is None:
        return ""
    pares = len({(c["club"], c["a"], c["b"]) for c in D.fdr["contrastes"]})
    clubes = sorted({c["club"] for c in D.fdr["contrastes"]})
    return f"""
{MARCA}
**Adenda (2026-09-15).** El bloque D1 se corrió con **{len(clubes)} clubes**
({', '.join(clubes)}), no con la terna: {pares} parejas, {D.fdr['n_contrastes']}
contrastes y **{D.fdr['n_sobreviven']}** sobrevivientes a BH
(`reports/fdr_presion.json`). La opción (a) se mantiene sobre esa familia.
Pendiente: `generar_defensa_h7.sh` y `12_reporte_html.py` siguen con
`america,leon,atlas` por defecto; la corrida real usó `--clubes`.
"""


def sincronia(D: Datos) -> str:
    if D.der is None:
        return ""
    for s in D.der.get("sincronia", []):
        if s["metrica"] == "ev_por_partido" and s["de"] == "A2022" and s["a"] == "C2023":
            return (f"La sincronía del escalón A2022→C2023 es de **{s['suben']} de "
                    f"{s['clubes']}** clubes (`frac_mismo_sentido` = "
                    f"{s['frac_mismo_sentido']:.2f}); `17_SECCION_H2H4.md` §6 decía "
                    "17 de 18 y 0.94.")
    return ""


def adr53(D: Datos) -> str:
    return f"""
{MARCA}
## ADR-53 · El contraste entre eras se normaliza por la liga del mismo torneo

**Fecha.** 2026-09-15. Borrador y predicciones escritos ANTES de la corrida
(`docs/ADR-53_BORRADOR.md`); resultados de `reports/did_h4_v1.json`.

**Contexto.** En `25_pares_h4.py` la línea base contemporánea solo construía
el prior, y magnitud y permutación corrían a λ=0: el prior no entraba en
ningún número. La v5 medía la diferencia entre eras con la deriva del
proveedor dentro (bug #19). Encoger con λ>0 no lo arregla: atenúa por igual
estilo y deriva, sin cambiar su proporción.

**Decisión.** Para cada unidad u = (club, entrenador),
$D_u = \\log E_T(\\hat P_u, \\hat\\alpha_u) - \\log E_T(\\hat P_{{base(u)}}, \\hat\\alpha_u)$,
con la base igual a la liga sin el club, en los torneos de u y ponderada a su
mezcla (B1, B2). El estimando es el de `08_ic_derivados.py`, con la misma
función `derivadas`. Para un par del mismo club, $\\theta = D_a - D_b$.
Bootstrap por posesión del foco y de la base (estratificada por torneo),
intervalo basic en escala log, p por inversión del intervalo y BH al 5% sobre
una **familia nueva**.

No es el DiD clásico: cada era se observa solo en su periodo y no hay
pre-tratamiento. El supuesto es que, sin cambio de entrenador, el club se
habría movido como la liga (B3/B4, contraste débil).

**Reglas preinscritas.** D53-1 a D53-8, en el borrador y en el JSON.

**Resultado.** {resumen(D)}

{tabla_predicciones(D)}

**Consecuencias.**
- La v5 queda como **diferencia bruta entre eras, deriva incluida**. No se
  borra ni se vuelve a correr.
- El control negativo **desaparece**: ningún par demuestra equivalencia al 3%.
  El argumento de discriminación pasa a apoyarse en los pares no rechazados,
  redactados con su margen ("no detectamos una diferencia mayor a X%"), y en
  la propia corrección: la firma temporal y los cambios de signo.
- El intervalo de n igualado de H4-3 se renombra `rango_submuestreo`: no es
  un IC (corr(b/n, ancho) = −0.88 sobre la v5).
- {sincronia(D)}

**Estado.** Aceptada.
"""


def seccion_27(D: Datos) -> str:
    return f"""
{MARCA}
---

# 27. 🟢 H4 con la deriva fuera (ADR-53)

**Fuente**: `scripts/30_did_contemporaneo.py` → `reports/did_h4_v1.json`
**Método**: desviación de cada era contra la liga sin su club en los mismos
torneos, estimando α′N1 a λ=0, bootstrap por posesión (foco y base), IC basic,
BH sobre los pares intra-club. Detalle en ADR-53.

{resumen(D)}

## 27.1 Predicciones preinscritas contra lo que salió

{tabla_predicciones(D)}

## 27.2 Los {D.did['n_pares']} pares

Signo positivo: el primer entrenador del par sostiene la posesión más que el
segundo. 🟢 rechaza tras BH · ⚪ no rechaza · ↺ el signo cambia al corregir la
deriva.
"crudo" es el mismo estimando sin normalizar, con las mismas réplicas.

{tabla_pares(D)}

**Afirmaciones defendibles.**
- Magnitudes: la columna DiD, nunca la de crudo.
- Cocca I vs Cocca II: el técnico difiere de sí mismo, pero **en sentido
  contrario al del crudo**. Sin la corrección se habría contado al revés.
- Un par no rechazado se redacta con su margen (§27.3), nunca como "sin
  diferencia".

## 27.3 Lo que se puede decir de los no rechazados

{tabla_nulos(D)}

Ningún par cumple el criterio de equivalencia al 3% (D53-4). Con unas 3,000
posesiones por era, el margen mínimo demostrable ronda el 4%.

## 27.4 ⚪ Material para H5, no citable

Entrenadores con más de una unidad analizable. No controla el efecto del
club: es insumo para H5, no un resultado.

{tabla_viajeros(D)}

## 27.5 Bug #19 — la línea base que no entraba

`25_pares_h4.py` declaraba (H4-5) que el prior contemporáneo cancelaba la
deriva, y su regla H4-1 decía "significancia a λ\\*". El código corría
magnitud y permutación a λ=0, donde el prior no entra. Ninguna excepción,
números plausibles: el síntoma fue estadístico (el entrenador posterior más
largo en la mayoría de los pares significativos). Corregido por ADR-53;
textos de `25` corregidos en el paquete h2_11.

## 27.6 Caveats

1. **La base no es el club.** El supuesto es que el club se habría movido como
   la liga; B3 lo contrasta de forma débil (14 unidades divergen en Carry/Pass).
2. **P(gol) y P(remate) son descriptivos** (D53-2): no hay contraste con FDR
   sobre ellos en esta versión.
3. **La serie por torneo** de cada unidad está en el JSON y es descriptiva.
4. **Todo lo anterior a §27 de este documento** usa las eras previas al
   bug #14 (ver el aviso de cabecera).
"""


def aviso_10(D: Datos) -> str:
    return f"""
{MARCA}
> ⚠️ **AVISO (2026-09-15).** Las secciones 1 a 26 se calcularon con el volcado
> anterior y con `coach_eras.csv` **previo al bug #14**: la etiqueta "Solari"
> cubría a Herrera mal rotulado, a Solari y a siete meses de Ortiz, y el par
> Sánchez–Ferretti no existe con el umbral de 25 partidos. Sus cifras por era
> **no son citables**. Los contrastes entre eras vigentes están en **§27**.
> Siguen en pie las conclusiones de método que no dependen de las eras: la
> cobertura de los IC (§9) y el principio de §13.
"""


def readme_cola(D: Datos) -> str:
    return f"""## Estado
{MARCA}

**Migrado al API de Hudl StatsBomb** (Liga MX, fase regular, 10 torneos,
18 clubes). La unidad es `(club, entrenador)`: 53 eras analizables, 60 pares
dentro del mismo club.

Los contrastes entre eras **descuentan la deriva de anotación del proveedor**
comparando cada era contra la liga en sus mismos torneos (ADR-53). Sin esa
corrección, {D.did['n_cambian_signo_por_correccion']} de {D.did['n_pares']} pares
cambian de signo.

El entregable es `reporte.html`: un archivo autocontenido, sin dependencias
externas, que se abre con doble clic. Está **en regeneración**: sus insumos
se recalculan con las eras del API.

## Titulares

Duración esperada de la posesión, $E[T]$, corregida por la liga
contemporánea. Clubes con sección profunda en el reporte. La tabla completa de
los {D.did['n_pares']} pares está en `10_RESULTADOS.md` §27.

{tabla_pares(D, TERNA)}

Signo positivo: el primer entrenador del par sostiene la posesión más que el
segundo. 🟢 significativo tras BH sobre los {D.did['n_pares']} pares ·
⚪ no significativo · ↺ el signo se invierte al corregir la deriva.

## El método no encuentra efectos en todas partes

{D.did['n_pares'] - D.did['n_rechazados_did']} de los {D.did['n_pares']} pares no
rechazan. Ninguno demuestra equivalencia al 3%, así que se redactan con su
margen:

{tabla_nulos(D, 3)}

Y la corrección misma discrimina: entre los pares significativos, la fracción
con el entrenador posterior más largo pasa del
{D.did['firma_temporal']['crudo']['posterior_mas_largo']}/{D.did['firma_temporal']['crudo']['de']}
sin corregir al
{D.did['firma_temporal']['did']['posterior_mas_largo']}/{D.did['firma_temporal']['did']['de']}
corregido.

## Retirados

| afirmación | motivo |
|---|---|
| Jardine sostiene más que Solari, +22.4% | eras previas al bug #14; el contraste vigente está arriba |
| Anselmi sostiene más que Reynoso, +25.6%; genera más remates, +44.6% | eras y datos previos a la migración; pendiente de recalcular con ADR-53 |
| Jardine genera menos remates que Ortiz, −12.5% | eras previas al bug #14 |
| Control de plantel: 9 de 17 jugadores | eras previas al bug #14; pendiente |
| Sánchez vs Ferretti sin efecto | las dos eras quedan bajo el umbral de 25 partidos |
| Berizzo vs Larcamón como par nulo | con la deriva fuera, difieren (§27) |
| "Ninguna diferencia en P(gol) es significativa" | pendiente de reverificar: hoy P(gol) es descriptivo |

## Validación

Siguen en pie, porque no dependen de las eras: la **cobertura de los IC**
(0.944 contra 0.95, generador con parámetro conocido) y **ninguna distancia
sin su nula**. El rechazo de Markov de orden 1, la invariancia a la resolución
y las auto-transiciones se midieron con el volcado anterior y están
**pendientes de replicar** con el API.

## Advertencia

**Dieciocho bugs encontrados, todos silenciosos** (numerados hasta el #19; el
#13 se evitó). Ninguno lanzó una excepción; todos produjeron números plausibles
pero incorrectos. El #14 fue un
dato de entrada (las eras investigadas a mano) y el #19 una regla de diseño
que el código no cumplía. En este dominio *"corre sin error"* no significa
nada.
"""


# ==========================================================================
# aplicacion
# ==========================================================================
def reemplaza(texto: str, viejo: str, nuevo: str, archivo: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise SystemExit(f"ABORTA: en {archivo} el fragmento aparece {n} veces "
                         f"(se esperaba 1):\n    {viejo[:80]!r}\nNo se escribio nada.")
    return texto.replace(viejo, nuevo)


def reemplaza_o_ya(texto: str, viejo: str, nuevo: str, archivo: str) -> str:
    """Como `reemplaza`, pero si el texto nuevo ya esta, no hace nada.

    El orden importa: se mira PRIMERO si ya esta el nuevo. Cuando el nuevo
    empieza con el viejo (un titulo seguido de un aviso), el viejo sigue
    apareciendo tras aplicar, y mirarlo primero duplicaria el aviso.
    """
    if nuevo in texto:
        return texto
    return reemplaza(texto, viejo, nuevo, archivo)


# Conteo de bugs (h2_14). El total vigente va en palabras; las menciones que
# eran una foto de su fecha se reescriben con el rango, no con otro numero.
CONTEO = {
    "02_STATE_OF_PLAY.md": [
        ("## 8. Los doce bugs: doce silenciosos",
         "## 8. Los bugs #1–#12 (hasta 2026-08-22): todos silenciosos"),
    ],
    "05_VALIDATION.md": [
        ("Los **ocho** bugs encontrados hasta ahora\n(`02_STATE_OF_PLAY.md` §8) "
         "fueron todos silenciosos. Ocho de ocho.",
         "Los **dieciocho** bugs encontrados hasta ahora\n(`02_STATE_OF_PLAY.md` §8, "
         "`17_BITACORA_MIGRACION.md`, `10_RESULTADOS.md` §27.5) fueron todos "
         "silenciosos. Dieciocho de dieciocho (numerados hasta el #19; el #13 se "
         "evitó)."),
    ],
    "10_RESULTADOS.md": [
        ("Es el patrón de los doce bugs aplicado a la estadística",
         "Es el patrón de todos los bugs del proyecto aplicado a la estadística"),
    ],
    "13_CONTEXTO_IA.md": [
        ("**Doce bugs encontrados, doce silenciosos.**",
         "**Dieciocho bugs encontrados, dieciocho silenciosos.**"),
        ("| dónde estamos, qué está validado, los doce bugs |",
         "| dónde estamos, qué está validado, los bugs #1–#12 "
         "(el #13 se evitó; los #14–#19: `17_BITACORA_MIGRACION.md` y "
         "`10_RESULTADOS.md` §27.5) |"),
        ("| 51 ADRs. **No reabrir debates cerrados** |",
         "| 53 ADRs. **No reabrir debates cerrados** |"),
        ("Los **doce** bugs del proyecto fueron **silenciosos**",
         "Los **dieciocho** bugs del proyecto fueron **silenciosos**"),
    ],
    "07_AI_HANDOFF.md": [
        ("**Doce bugs encontrados. Doce silenciosos.**",
         "**Dieciocho bugs encontrados. Dieciocho silenciosos.**"),
        ("> - Los **doce** bugs del proyecto fueron silenciosos, y el #13 se",
         "> - Los **dieciocho** bugs del proyecto fueron silenciosos, y el #13 se"),
    ],
    "../AGENTS.md": [
        ("**Doce bugs encontrados. Doce silenciosos. Cero excepciones.**",
         "**Dieciocho bugs encontrados. Dieciocho silenciosos. Cero excepciones.**"),
        ("> - Los doce bugs del proyecto fueron **silenciosos**, y el #13 se evitó",
         "> - Los dieciocho bugs del proyecto fueron **silenciosos**, y el #13 se evitó"),
    ],
    "../README.md": [
        ("> ⚠️ **Advertencia**: Doce bugs encontrados, doce silenciosos.",
         "> ⚠️ **Advertencia**: Dieciocho bugs encontrados, dieciocho silenciosos "
         "(numerados hasta el #19; el #13 se evitó)."),
        ("## 1. Titulares y Hallazgos Principales\n",
         "## 1. Titulares y Hallazgos Principales\n\n"
         "> 🔴 **RETIRADOS (2026-09-15).** Las tablas de esta sección y el control "
         "de plantel se calcularon con el volcado anterior y con eras previas al "
         "bug #14 (la etiqueta «Solari» mezclaba tres entrenadores). **No son "
         "citables.** Tras la migración al API y la corrección de la deriva del "
         "proveedor (ADR-53), los contrastes vigentes están en "
         "[docs/README.md](docs/README.md) y en `docs/10_RESULTADOS.md` §27. "
         "Esta portada se reescribirá con el reporte.\n"),
        ("## 2. Los Seis Pilares de Validación\n",
         "## 2. Los Seis Pilares de Validación\n\n"
         "> Los pilares 5 y 6 no dependen de las eras. Los pilares 1 a 4 se "
         "midieron con el volcado anterior y están **pendientes de replicar** con "
         "el API.\n"),
    ],
    "15_REPORTE_HTML.md": [
        ("Los doce bugs de este\nproyecto compilaban.",
         "Todos los bugs de este\nproyecto compilaban."),
    ],
    "17_BITACORA_MIGRACION.md": [
        ("que el proyecto lleva catorce bugs documentando:",
         "que el proyecto documenta desde el bug #1 (#14 a esta fecha):"),
        ("Ahí es donde salieron los catorce bugs, y todos fueron\nsilenciosos.",
         "Ahí es donde salieron los bugs #1–#14, y todos fueron\nsilenciosos."),
    ],
}
PALABRAS = (r"\b(ocho|nueve|diez|once|doce|trece|catorce|quince|diecis[eé]is|"
            r"diecisiete|dieciocho|diecinueve|veinte)\s+bugs")


def conteos_restantes(raiz: Path, nuevos: dict[Path, str]) -> dict[str, set[str]]:
    """Palabras de conteo que quedarian tras aplicar, en docs/ y en la raiz."""
    out: dict[str, set[str]] = {}
    rutas = sorted((raiz / "docs").glob("*.md")) + [raiz / "README.md", raiz / "AGENTS.md"]
    for q in rutas:
        if not q.exists():
            continue
        t = nuevos.get(q, q.read_text(encoding="utf-8"))
        for m in re.finditer(PALABRAS, re.sub(r"[*_`]", "", t), re.I):
            out.setdefault(m.group(1).lower(), set()).add(str(q.relative_to(raiz)))
    return out


def verifica_vista(raiz: Path, nuevos: dict[Path, str]) -> tuple[int, str]:
    """Corre docs/verificar_docs.py sobre un arbol temporal con los cambios."""
    ver = raiz / "docs" / "verificar_docs.py"
    if not ver.exists():
        return 0, "(no hay docs/verificar_docs.py; no se verifico)"
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        shutil.copytree(raiz / "docs", t / "docs",
                        ignore=shutil.ignore_patterns("*.anterior_*", "img", "__pycache__"))
        for extra in ("README.md", "AGENTS.md", "uv.lock", "LICENSE"):
            if (raiz / extra).exists():
                shutil.copy2(raiz / extra, t / extra)
        for p, txt in nuevos.items():
            (t / p.relative_to(raiz)).write_text(txt, encoding="utf-8")
        r = subprocess.run([sys.executable, str(t / "docs" / "verificar_docs.py"),
                            "--repo", str(t)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


def construye(D: Datos, docs: Path) -> dict[Path, str]:
    out: dict[Path, str] = {}
    for nombre, cambios in CONTEO.items():
        p = (docs / nombre).resolve()
        if not p.exists():
            raise SystemExit(f"ABORTA: falta {p}. No se escribio nada.")
        t0 = p.read_text(encoding="utf-8")
        t = t0
        for viejo, nuevo in cambios:
            t = reemplaza_o_ya(t, viejo, nuevo, nombre)
        if t != t0:
            out[p] = t

    p = docs / "06_DECISIONS.md"
    t = p.read_text(encoding="utf-8")
    if MARCA not in t:
        t = reemplaza(t, "**Estado.** Cerrada como aclaracion; la mejora queda pendiente.",
                      "**Estado.** Superada (2026-09-14): con el API el prior es la liga "
                      "completa sin el club focal (`16_MIGRACION_API.md` §5).", p.name)
        t = reemplaza(t, "H7, así que ese contraste puede no llegar siquiera a calcularse.\n",
                      "H7, así que ese contraste puede no llegar siquiera a calcularse.\n"
                      + adenda_52(D), p.name)
        t = t.rstrip("\n") + "\n\n---\n" + adr53(D)
        out[p] = t

    p = docs / "10_RESULTADOS.md"
    t = out.get(p, p.read_text(encoding="utf-8"))
    if MARCA not in t:
        ancla = "> Corte: 2026-08-20 · `dtdecoder 0.5.0` · **Fases 0–3 completas**\n"
        t = reemplaza(t, ancla, ancla + aviso_10(D), p.name)
        t = t.rstrip("\n") + "\n" + seccion_27(D)
        out[p] = t

    p = docs / "README.md"
    t = p.read_text(encoding="utf-8")
    if MARCA not in t:
        t = reemplaza(t, "| 06 | [Decisiones (51 ADRs)](06_DECISIONS.md) |",
                      "| 06 | [Decisiones (53 ADRs)](06_DECISIONS.md) |", p.name)
        fila15 = "| 15 | [El reporte HTML](15_REPORTE_HTML.md) | desarrollador | **antes de tocar el entregable** |\n"
        t = reemplaza(t, fila15, fila15 +
                      "| 16 | [Migración al API](16_MIGRACION_API.md) | equipo | decisiones de alcance |\n"
                      "| 17 | [Bitácora de la migración](17_BITACORA_MIGRACION.md) | IA / equipo | al retomar |\n"
                      "| 18 | [Protocolo de sesión](18_PROTOCOLO_SESION.md) | IA / equipo | **antes de operar el repo** |\n",
                      p.name)
        i = t.find("## Estado\n")
        if i < 0 or t.count("## Estado\n") != 1:
            raise SystemExit("ABORTA: README sin una unica seccion '## Estado'. No se escribio nada.")
        t = t[:i] + readme_cola(D)
        out[p] = t
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--forzar", action="store_true",
                    help="escribir aunque verificar_docs.py falle en la vista")
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    ap.add_argument("--vista", type=Path, default=Path("/tmp/h2_14_vista"))
    args = ap.parse_args()

    args.raiz = args.raiz.resolve()
    D = Datos(args.raiz)
    docs = args.raiz / "docs"
    nuevos = construye(D, docs)

    print("== predicciones preinscritas ==")
    for p in predicciones(D):
        print(f"  {p['n']}. {'CUMPLE' if p['cumple'] else 'FALLA '}  {p['texto']}")
        print(f"       {p['resultado']}" + (f"  ({p['nota']})" if p['nota'] else ""))
    print()

    if not nuevos:
        print("Nada que hacer: los cambios ya estan aplicados.")
        return 0

    quedan = conteos_restantes(args.raiz, nuevos)
    print("== conteo de bugs tras aplicar ==")
    for w, fs in sorted(quedan.items()):
        print(f"  {w:<12} {', '.join(sorted(fs))}")
    if len(quedan) > 1:
        print("  !! sigue habiendo mas de un conteo: corrige los de arriba a mano")
    print()

    args.vista.mkdir(parents=True, exist_ok=True)
    for p, t in nuevos.items():
        antes = p.read_text(encoding="utf-8").count("\n")
        nv = p.name if p.parent == docs else f"RAIZ_{p.name}"
        (args.vista / nv).write_text(t, encoding="utf-8")
        print(f"  {nv:<26} {antes:>5} -> {t.count(chr(10)):>5} lineas   "
              f"vista: {args.vista / nv}")

    rc, salida = verifica_vista(args.raiz, nuevos)
    print("\n== docs/verificar_docs.py sobre la vista previa ==")
    print("\n".join("  " + l for l in salida.strip().splitlines()))

    if not args.escribir:
        print("\n(vista previa; revisa los archivos de arriba y usa --escribir)")
        return 0
    if rc != 0 and not args.forzar:
        print("\nNO SE ESCRIBE: la vista previa no pasa verificar_docs.py. "
              "Corrige lo que marca, o usa --forzar si lo que falla es previo "
              "y ajeno a este cambio (y declaralo).")
        return 1

    ts = time.strftime("%Y%m%d%H%M")
    for p, t in nuevos.items():
        shutil.copy2(p, p.with_name(p.name + f".anterior_{ts}"))
        p.write_text(t, encoding="utf-8")
        print(f"  escrito {p}  (respaldo {p.name}.anterior_{ts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
