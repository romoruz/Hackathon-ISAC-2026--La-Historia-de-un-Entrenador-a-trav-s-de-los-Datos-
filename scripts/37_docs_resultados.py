#!/usr/bin/env python3
"""
37_docs_resultados.py — lleva ADR-54 a ADR-57 y sus resultados a la documentacion.

Mismas reglas que `32_docs_adr53.py`, de donde reutiliza el motor:
  * ninguna cifra tecleada: todas salen de reports/*.json al aplicar;
  * reemplazos exactos; si un fragmento no aparece, aborta sin escribir;
  * marca `<!-- h2_23 -->`: aplicar dos veces no duplica;
  * corre docs/verificar_docs.py sobre la vista previa y no escribe si falla.

Fuentes: did_presion_v1.json (ADR-54), balon_parado_v2.json (ADR-55 + casos),
contexto_v1.json (ADR-56/57), did_h4_v1.json (tabla descriptiva de casos).

Uso:
    python scripts/37_docs_resultados.py              # vista previa
    python scripts/37_docs_resultados.py --escribir
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "<!-- h2_23 -->"


def _carga32():
    spec = importlib.util.spec_from_file_location("docs32", RAIZ / "scripts" / "32_docs_adr53.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M32 = _carga32()


# ==========================================================================
def pp(x, d=2):
    return "—" if x is None or not np.isfinite(x) else f"{100 * x:+.{d}f} pp"


def num(x, d=3):
    return "—" if x is None or not np.isfinite(x) else f"{x:+.{d}f}"


def icpp(v, d=2):
    if not v or v[0] is None:
        return "—"
    return f"[{100 * v[0]:+.{d}f}, {100 * v[1]:+.{d}f}]"


def icn(v, d=3):
    if not v or v[0] is None:
        return "—"
    return f"[{v[0]:+.{d}f}, {v[1]:+.{d}f}]"


def qf(x):
    return "—" if x is None or not np.isfinite(x) else f"{x:.4f}"


def marca(c):
    return "✅" if c is True else ("❌" if c is False else "n/e")


def corto(v):
    return json.dumps(v, ensure_ascii=False, default=lambda o: round(float(o), 4))[:120]


class Datos:
    def __init__(self, raiz: Path):
        r = raiz / "reports"
        self.d1 = json.loads((r / "did_presion_v1.json").read_text())
        bp = r / "balon_parado_v2.json"
        self.bp = json.loads((bp if bp.exists() else r / "balon_parado_v1.json").read_text())
        self.cx = json.loads((r / "contexto_v1.json").read_text())
        h4 = r / "did_h4_v1.json"
        self.h4 = json.loads(h4.read_text()) if h4.exists() else None


# ==========================================================================
# ADR-54 · D1
# ==========================================================================
def tabla_d1(D) -> str:
    filas = ["| club | par | E1 q | E2 (pp) | E3 (‰/toque) | E4 (pp) | E5 (pp) |",
             "|---|---|---|---|---|---|---|"]
    for x in D.d1["pares"]:
        c = x["contrastes"]
        def celda(e, escala):
            if "did" not in c[e]:
                return "excluido"
            d = c[e]["did"]
            ok = "🟢 " if d.get("rechaza") else ""
            if e == "E1":
                return f"{ok}{qf(d.get('q'))}"
            v = d["theta"] * escala
            return f"{ok}{v:+.2f} (q {qf(d.get('q'))})"
        filas.append(f"| {x['club']} | {x['a']} vs {x['b']} | {celda('E1', 1)} | {celda('E2', 100)} | "
                     f"{celda('E3', 1000)} | {celda('E4', 100)} | {celda('E5', 100)} |")
    return "\n".join(filas)


def zonas_d1(D) -> str:
    out = []
    for x in D.d1["pares"]:
        zs = [z for z in (x.get("zonas") or []) if z["rechaza"]]
        if not zs:
            continue
        out.append(f"\n**{x['club']} · {x['a']} vs {x['b']}** — {len(zs)} zonas tras BH dentro del par:\n")
        out.append("| zona (ix, iy) | Δ | IC 95% | q | crudo | logit mismo signo |")
        out.append("|---|---|---|---|---|---|")
        for z in zs:
            out.append(f"| {z['zona']} ({z['ix']}, {z['iy']}) | {pp(z['delta'])} | {icpp(z['ic95'])} | "
                       f"{qf(z['q'])} | {pp(z['delta_crudo'])} | {'sí' if z['signo_logit_coincide'] else 'NO'} |")
    return "\n".join(out) if out else "Ningún par pasó a la etapa 2."


def preds_tabla(preds, clave_valor=None) -> str:
    filas = ["| # | predicción | valor | |", "|---|---|---|---|"]
    for p in preds:
        v = {k: p[k] for k in p if k not in ("n", "texto", "cumple", "adr")}
        texto = p["texto"].replace("|", "\\|")
        filas.append(f"| {p['n']} | {texto} | `{corto(v)}` | {marca(p['cumple'])} |")
    return "\n".join(filas)


def adr54(D) -> str:
    d = D.d1
    viven = [(x, e) for x in d["pares"] for e, c in x["contrastes"].items()
             if c.get("did", {}).get("rechaza")]
    lista = "\n".join(f"- {x['club']} · {x['a']} vs {x['b']} · {e}" for x, e in viven) or "- ninguno"
    nc, nd = d["n_rechaza_crudo"], d["n_rechaza_did"]
    peso = (f"La corrección pesó más de lo que suponía el diseño: sin ella rechazaban {nc} "
            f"contrastes y con ella {nd}." if nc > nd else
            f"Sin corregir rechazaban {nc} contrastes y con la corrección {nd}.")
    return f"""
{MARCA}
## ADR-54 · El bloque defensivo D1 se normaliza por la liga del mismo torneo

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-54_BORRADOR.md`
(commit 2af2ab2) con las adendas 1 (vista defensora, bug #20) y 2 (universo de
partidos completos). Resultado: `reports/did_presion_v1.json`.

**Decisión.** Cada era defendiendo (acciones reales del rival, marco del club)
se compara con la liga sin **ningún** partido del club, en los mismos torneos y
estandarizada por torneo × zona. Unidad y base salen de la vista defensora
(`min_actions_defense = 1`). Cinco contrastes por par (E1 geografía ómnibus,
E2 nivel en k ≥ 3, E3 pendiente, E4/E5 posesiones de una acción), bootstrap por
partido con la base compartida en el club, B = 6000, familia en dos etapas con
BH al 5%.

**Resultado.** {d['n_pares']} pares · etapa 1: {d['m_etapa1']} contrastes · rechazan
**{d['n_rechaza_did']}** con la corrección y {d['n_rechaza_crudo']} sin ella ·
cambian de veredicto {d['n_cambian_veredicto']} · partidos excluidos por la
adenda 2: {len(d['diagnostico_vista']['partidos_excluidos_d54_12'])}.

Sobreviven:
{lista}

{preds_tabla(d['predicciones'])}

La predicción 2 quedó contaminada por el humo con la base vieja (adenda 1).
{peso}

**Estado.** Aceptada. Antes de redactar frases de geografía, la orientación de
las zonas se comprueba con `13_verificar_ejes.py`.
"""


# ==========================================================================
# ADR-55 · balon parado
# ==========================================================================
def adr55(D) -> str:
    b = D.bp
    m, L = b["modelo"], b["liga"]
    ex = L.get("exploratorio_adenda_1", {})
    fc = b.get("familia_casos", {})
    rech = [(u, k) for u in b["unidades"] for k in ("C1_of", "C1_def", "C2_of", "C2_def")
            if u[k].get("rechaza") or u[k].get("rechaza_casos")]
    lista = "\n".join(
        f"- {u['club']} · {u['coach']} · {k}: unidad {u[k]['unidad']:.4f}, liga {u[k]['base']:.4f}, "
        f"diferencia {u[k]['did']:+.4f} {icn(u[k]['ic95'], 4)} "
        f"(q ADR-52 {qf(u[k].get('q'))}, q casos {qf(u[k].get('q_casos'))})" for u, k in rech) or "- ninguno"
    cad = L["cadena_corner"]
    notas = []
    ps, p10 = L["P_S_secuencia"].get("corner"), (ex.get("P_S_10s") or {}).get("corner")
    if ps and p10 is not None:
        notas.append(f"De la P(remate | secuencia de córner) de {ps:.3f}, {p10:.3f} ocurre en los "
                     f"primeros 10 s ({p10 / ps:.0%}).")
    pg, pr = L["P_G_secuencia"].get("corner"), L["producto_posesion"]["producto"]
    notas.append(f"P(gol) por secuencia {pg:.4f}; producto de las dos capas {pr:.4f}; cadena "
                 f"{cad['P_gol']:.4f}. P(remate) por posesión: empírica "
                 f"{L['producto_posesion']['P_S_posesion']:.3f}, cadena {cad['P_remate']:.3f}.")
    if cad["P_remate"] < 0.75 * L["producto_posesion"]["P_S_posesion"]:
        notas.append("La cadena de primer orden subestima el peligro del balón parado (rechazo de "
                     "Markov, `03_METHODS.md` §7.1); su versión quedó descriptiva desde la preinscripción.")
    notas = " ".join(notas)
    return f"""
{MARCA}
## ADR-55 · Balón parado: la cadena para la prevención, la geometría para la supresión

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-55_BORRADOR.md`
(commit 9aa5524) con la adenda 1 (sensibilidades exploratorias, bug #21).
Integra el proyecto previo de córners. Resultado: `reports/balon_parado_v2.json`.

**Decisión.** Secuencias de córner, tiro libre indirecto y saque de banda
construidas desde los eventos. C1 = P(remate | secuencia), C2 = E[xG | remate],
con un modelo de balón parado ajustado una vez para la liga (distancia, ángulo,
cabeza y geometría del freeze frame, fuera de pliegue por partido). Cada era se
compara con la liga del mismo torneo; bootstrap por partido, B = 6000. Familias:
ADR-52 ({b['familia']['m']} contrastes) y casos de ADR-57 ({fc.get('m')}).

**Liga.** P(remate | secuencia): {corto(L['P_S_secuencia'])}. P(gol | secuencia):
{corto(L['P_G_secuencia'])}. Exploratorio, remate en 10 s: {corto(ex.get('P_S_10s'))};
dentro de la fase del proveedor: {corto(ex.get('P_S_fase'))}. Cadena en córners:
P(remate) {cad['P_remate']:.4f}, P(gol) {cad['P_gol']:.4f}, E[T] {cad['E_T']:.2f}.

**Modelo.** {m['n_remates']} remates y {m['n_goles']} goles · AUC base {m['auc_base']:.3f},
con geometría {m['auc_full']:.3f}, StatsBomb {m['auc_statsbomb']:.3f} · ΔAUC
{m['delta_auc']:+.3f} {icn(m['delta_auc_ic95_percentil'])} · cabeza
{m['beta_base_estandarizado']['cabeza']:+.3f} {icn(m['beta_base_ic95']['cabeza'])} ·
interacción cabeza × distancia {m['beta_interaccion']['dist_x_cabeza']:+.3f}.

**Familias.** ADR-52: {b['familia']['rechazan']} de {b['familia']['m']} rechazan.
Casos: {fc.get('rechazan')} de {fc.get('m')}.
{lista}

{preds_tabla(b['predicciones'])}

{notas}

**Estado.** Aceptada.
"""


# ==========================================================================
# ADR-56 · contexto
# ==========================================================================
ETIQ = {"M1": "acciones/posesión (ataque)", "M2": "P(remate) (ataque)",
        "M3": "π de presión (defensa)", "M4": "P(remate) concedido"}


def tabla_liga_cx(D) -> str:
    L = D.cx["liga"]
    filas = ["| contexto | métrica | A | B |", "|---|---|---|---|"]
    for c in ("localia", "marcador", "momento", "rival", "marcador_60"):
        for mt in ("M1", "M2", "M3", "M4"):
            t = L[c][mt]
            ks = [k for k in t if k != "otro"]
            f = (lambda x: f"{x:.3f}") if mt == "M1" else (lambda x: f"{100 * x:.1f}%")
            filas.append(f"| {c} | {ETIQ[mt]} | {ks[0]}: {f(t[ks[0]])} | {ks[1]}: {f(t[ks[1]])} |")
    return "\n".join(filas)


def adr56(D) -> str:
    c = D.cx
    fam = c["familias"]
    rech = [(u, k, v) for u in c["unidades"] for k, v in u["contrastes"].items()
            if v.get("rechaza_adr52") or v.get("rechaza_casos")]
    lista = "\n".join(
        f"- {u['club']} · {u['coach']} · {k}: θ {v['theta']:+.4f} {icn(v['ic95'], 4)} "
        f"(q ADR-52 {qf(v.get('q_adr52'))}, q casos {qf(v.get('q_casos'))})" for u, k, v in rech) or "- ninguno"
    preds = [p for p in c["predicciones"] if p["adr"] == 56]
    return f"""
{MARCA}
## ADR-56 · Contexto: cuánto ajusta el entrenador más allá de lo que ajusta la liga

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-56_BORRADOR.md`
con la adenda 1 (B = 16,000). Resultado: `reports/contexto_v1.json`.

**Decisión.** θ = [M_era(A) − M_era(B)] − [M_liga(A) − M_liga(B)] desde la
perspectiva del club (el marcador del rival se invierte), para localía,
marcador, momento (minuto 60) y rival (tercio por diferencia de xG sin el
partido propio). Métricas M1–M4. Bootstrap por partido, que conserva la
dependencia dentro del partido; B = 16,000.

**Lo que ajusta la liga** (A y B de cada contexto):

{tabla_liga_cx(D)}

**Eras que se separan de ese ajuste.** ADR-52:
{fam['adr52']['rechazan']} de {fam['adr52']['m']}. Casos: {fam['casos']['rechazan']} de
{fam['casos']['m']}.
{lista}

{preds_tabla(preds)}

**Estado.** Aceptada. Un contraste sin rechazo se redacta con su intervalo:
"no detectamos un ajuste distinto al de la liga mayor a…".
"""


# ==========================================================================
# ADR-57 · casos
# ==========================================================================
def viaja_nueve(D) -> tuple[list, int]:
    casos = D.cx["casos"]
    nueve = [c for c, clubes in casos.items() if len(clubes) >= 2 and "América" not in clubes]
    res = []
    for c in sorted(nueve):
        sg = [np.sign(u["contrastes"]["marcador|M1"]["theta"]) for u in D.cx["unidades"]
              if u["coach"] == c and u["club"] in casos[c]]
        res.append((c, sg, len(set(sg)) == 1))
    return res, sum(r[2] for r in res)


def adr57(D) -> str:
    casos = D.cx["casos"]
    res, n_ok = viaja_nueve(D)
    lectura = ("" if not res else
               " El ajuste al marcador **no viaja** con el entrenador en la mayoría de los casos."
               if n_ok < len(res) / 2 else
               " El ajuste al marcador **viaja** con el entrenador en la mayoría de los casos.")
    tabla = "\n".join(f"| {c} | {', '.join(v)} |" for c, v in casos.items())
    signos = "\n".join(f"| {c} | {' / '.join('+' if s > 0 else '−' for s in sg)} | "
                       f"{'sí' if ok else 'no'} |" for c, sg, ok in res)
    return f"""
{MARCA}
## ADR-57 · Casos del informe: el América y los entrenadores con varios clubes

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-57_BORRADOR.md`.

**Decisión.** Casos = las eras del América más los entrenadores con al menos
dos eras analizables en clubes distintos. Es un criterio estructural,
recalculado por los scripts; coincidió con la tabla preinscrita
(diferencias: {corto(D.cx.get('casos_difieren_del_adr', {}))}).

| entrenador | clubes |
|---|---|
{tabla}

La familia de casos se reporta aparte de la de ADR-52, en balón parado y en
contexto. Lo que viaja en E[T] y en balón parado es **descriptivo**, porque
esos puntos se vieron antes de preinscribir.

**Predicción 1** (al menos 6 de los 9 técnicos de varios clubes mantienen el
signo del ajuste al marcador en M1): **{n_ok} de {len(res)}** →
{marca(None if not res else n_ok >= 6)}.

| entrenador | signo por club | mismo signo |
|---|---|---|
{signos}

*Corrección:* `36_contexto.py` imprimió este conteo sobre 11 técnicos
(incluía a Jardine y a Ortiz), cuando el texto preinscrito dice nueve. El
veredicto no cambia.{lectura}

**Estado.** Aceptada.
"""


# ==========================================================================
# 10_RESULTADOS
# ==========================================================================
def tabla_bp_casos(D) -> str:
    filas = ["| era | partidos | C1 of (dif.) | C1 def (dif.) | C2 of (dif.) | C2 def (dif.) |",
             "|---|---|---|---|---|---|"]
    for u in D.bp["unidades"]:
        if not u.get("en_casos"):
            continue
        filas.append(f"| {u['coach']} ({u['club']}) | {u['n_partidos']} | {pp(u['C1_of']['did'], 1)} "
                     f"{icpp(u['C1_of']['ic95'], 1)} | {pp(u['C1_def']['did'], 1)} {icpp(u['C1_def']['ic95'], 1)} | "
                     f"{num(u['C2_of']['did'], 4)} | {num(u['C2_def']['did'], 4)} |")
    return "\n".join(filas)


def tabla_america_cx(D) -> str:
    out = []
    for u in D.cx["unidades"]:
        if u["club"] != "América":
            continue
        out.append(f"\n**{u['coach']}** ({u['n_partidos']} partidos)\n")
        out.append("| contraste | θ | IC 95% | q (ADR-52) |")
        out.append("|---|---|---|---|")
        for k, c in u["contrastes"].items():
            if not c["familia"]:
                continue
            if k.endswith("M1"):
                t, ic = num(c["theta"]), icn(c["ic95"])
            else:
                t, ic = pp(c["theta"]), icpp(c["ic95"])
            out.append(f"| {k.replace('|', ' · ')} | {t} | {ic} | {qf(c.get('q_adr52'))} |")
    return "\n".join(out)


def tabla_casos(D) -> str:
    h4 = {(u["club"], u["coach"]): u for u in (D.h4 or {}).get("unidades", [])}
    bp = {(u["club"], u["coach"]): u for u in D.bp["unidades"]}
    cx = {(u["club"], u["coach"]): u for u in D.cx["unidades"]}
    filas = ["| entrenador | club | E[T] vs liga (H4) | ajuste al marcador, M1 | C1 of | C1 def |",
             "|---|---|---|---|---|---|"]
    for c, clubes in D.cx["casos"].items():
        for cl in clubes:
            e = h4.get((cl, c))
            et = f"{100 * e['rel_E_T_vs_liga']:+.1f}%" if e else "—"
            mk = cx.get((cl, c), {}).get("contrastes", {}).get("marcador|M1", {}).get("theta")
            b = bp.get((cl, c))
            filas.append(f"| {c} | {cl} | {et} | {num(mk)} | "
                         f"{pp(b['C1_of']['did'], 1) if b else '—'} | {pp(b['C1_def']['did'], 1) if b else '—'} |")
    return "\n".join(filas)


def secciones_10(D) -> str:
    d, b, c = D.d1, D.bp, D.cx
    n_ci = sum(1 for u in c["unidades"] if u["club"] == "América"
               for k, v in u["contrastes"].items()
               if v["familia"] and v["ic95"][0] is not None and (v["ic95"][0] > 0 or v["ic95"][1] < 0))
    n_tot = sum(1 for u in c["unidades"] if u["club"] == "América"
                for v in u["contrastes"].values() if v["familia"])
    return f"""
{MARCA}
---

# 28. 🟢 D1 con la deriva fuera (ADR-54)

**Fuente**: `scripts/33_did_presion.py` → `reports/did_presion_v1.json`.
{d['m_etapa1']} contrastes en la etapa 1; rechazan {d['n_rechaza_did']} con la
corrección ({d['n_rechaza_crudo']} sin ella). 🟢 = rechaza tras BH.

{tabla_d1(D)}

## 28.1 Etapa 2: zonas dentro de los pares cuyo E1 rechaza

{zonas_d1(D)}

**Caveats.** (1) Antes de redactar dónde presiona cada técnico, hay que
comprobar la orientación de las zonas con `13_verificar_ejes.py`. (2) E2
condiciona a sobrevivir hasta k = 3. (3) La presión es asociación: StatsBomb
la anota cuando un defensor se acerca.

---

# 29. 🟢 Balón parado (ADR-55)

**Fuente**: `scripts/35_balon_parado.py` → `reports/balon_parado_v2.json`.
La síntesis está en ADR-55. Eras de casos (diferencia contra la liga del mismo
torneo; C2 en unidades de xG por remate):

{tabla_bp_casos(D)}

---

# 30. 🟢 Contexto (ADR-56)

**Fuente**: `scripts/36_contexto.py` → `reports/contexto_v1.json`. La tabla de
la liga está en ADR-56. Las eras del América:

{tabla_america_cx(D)}

En las eras del América, {n_ci} de {n_tot} intervalos excluyen el cero **antes**
de corregir y **ninguno** sobrevive a BH. La frase correcta: ningún técnico del
América ajusta al contexto de forma detectablemente distinta a la liga.

---

# 31. ⚪ Casos: lo que viaja con el entrenador (descriptivo)

Tabla de ADR-57. E[T] y balón parado se vieron antes de preinscribir: son
descriptivos.

{tabla_casos(D)}

---

# 32. Bugs #20 y #21

**#20 · la base de D1 truncaba distinto que la unidad.** `data/prior_liga`
usa `min_actions = 2`; las eras defendiendo, `min_actions_defense = 1`. La
base no tenía las posesiones de una acción que terminan sin fila `TERMINAL`,
justo el producto de una presión exitosa (y de un córner despejado al primer
toque). Corregido con la vista defensora (ADR-54, adenda 1).

**#21 · el freeze frame del API es JSON.** `xg_remate.features` se escribió
para el texto de Python del volcado viejo (`True`/`False`) y devolvía `None`
en silencio con el JSON del API (`true`/`false`). `35` detecta el formato
sobre una muestra y aborta si ninguno funciona (ADR-55, adenda 1).

Los dos produjeron números o vacíos sin excepción. Con estos, el registro
suma **veinte bugs encontrados**, numerados hasta el #21 (el #13 se evitó).
"""


def readme_bloque(D) -> str:
    d, b, c = D.d1, D.bp, D.cx
    viven = sorted({f"{x['club']}: {x['a']} vs {x['b']}" for x in d["pares"]
                    for e, v in x["contrastes"].items() if v.get("did", {}).get("rechaza")})
    pb = {p["n"]: p["cumple"] for p in b["predicciones"]}
    importa = ("La cabeza y la geometría del remate cambian el xG." if pb.get(3) and pb.get(4)
               else "Ver ADR-55 para el papel de la cabeza y la geometría.")
    res, n_ok = viaja_nueve(D)
    viaja = ("" if not res else f" El ajuste al marcador mantiene su signo en {n_ok} de {len(res)}.")
    pares_txt = f"{len(viven)} par" + ("" if len(viven) == 1 else "es")
    return f"""## Defensa, balón parado y contexto
{MARCA}

- **Presión (ADR-54).** Contra la liga del mismo torneo, sobreviven
  {d['n_rechaza_did']} de {d['m_etapa1']} contrastes ({d['n_rechaza_crudo']} sin la
  corrección), en {pares_txt}: {'; '.join(viven) or '—'}. `10_RESULTADOS.md` §28.
- **Balón parado (ADR-55).** {b['familia']['rechazan']} de {b['familia']['m']} contrastes
  separan a una era de la liga (familia de casos: {b['familia_casos']['rechazan']} de
  {b['familia_casos']['m']}). {importa} §29.
- **Contexto (ADR-56).** Cada era comparada con el ajuste de la liga a la
  localía, el marcador, el momento y el rival: se separan
  {c['familias']['adr52']['rechazan']} de {c['familias']['adr52']['m']} contrastes. §30.
- **Casos (ADR-57).** Las eras del América y los técnicos con varios clubes.{viaja} §31.

## Retirados
"""


# ==========================================================================
CONTEO = {
    "05_VALIDATION.md": [
        ("Los **dieciocho** bugs encontrados hasta ahora\n(`02_STATE_OF_PLAY.md` §8, `17_BITACORA_MIGRACION.md`, "
         "`10_RESULTADOS.md` §27.5) fueron todos silenciosos. Dieciocho de dieciocho (numerados hasta el #19; "
         "el #13 se evitó).",
         "Los **veinte** bugs encontrados hasta ahora\n(`02_STATE_OF_PLAY.md` §8, `17_BITACORA_MIGRACION.md`, "
         "`10_RESULTADOS.md` §27.5 y §32) fueron todos silenciosos. Veinte de veinte (numerados hasta el #21; "
         "el #13 se evitó)."),
    ],
    "13_CONTEXTO_IA.md": [
        ("**Dieciocho bugs encontrados, dieciocho silenciosos.**",
         "**Veinte bugs encontrados, veinte silenciosos.**"),
        ("(el #13 se evitó; los #14–#19: `17_BITACORA_MIGRACION.md` y `10_RESULTADOS.md` §27.5) |",
         "(el #13 se evitó; los #14–#21: `17_BITACORA_MIGRACION.md` y `10_RESULTADOS.md` §27.5 y §32) |"),
        ("| 53 ADRs. **No reabrir debates cerrados** |", "| 57 ADRs. **No reabrir debates cerrados** |"),
        ("Los **dieciocho** bugs del proyecto fueron **silenciosos**",
         "Los **veinte** bugs del proyecto fueron **silenciosos**"),
    ],
    "07_AI_HANDOFF.md": [
        ("**Dieciocho bugs encontrados. Dieciocho silenciosos.**",
         "**Veinte bugs encontrados. Veinte silenciosos.**"),
        ("> - Los **dieciocho** bugs del proyecto fueron silenciosos, y el #13 se",
         "> - Los **veinte** bugs del proyecto fueron silenciosos, y el #13 se"),
    ],
    "../AGENTS.md": [
        ("**Dieciocho bugs encontrados. Dieciocho silenciosos. Cero excepciones.**",
         "**Veinte bugs encontrados. Veinte silenciosos. Cero excepciones.**"),
        ("> - Los dieciocho bugs del proyecto fueron **silenciosos**, y el #13 se evitó",
         "> - Los veinte bugs del proyecto fueron **silenciosos**, y el #13 se evitó"),
    ],
    "../README.md": [
        ("Dieciocho bugs encontrados, dieciocho silenciosos (numerados hasta el #19; el #13 se evitó).",
         "Veinte bugs encontrados, veinte silenciosos (numerados hasta el #21; el #13 se evitó)."),
    ],
    "README.md": [
        ("| 06 | [Decisiones (53 ADRs)](06_DECISIONS.md) |", "| 06 | [Decisiones (57 ADRs)](06_DECISIONS.md) |"),
        ("**Dieciocho bugs encontrados, todos silenciosos** (numerados hasta el #19; el\n#13 se evitó).",
         "**Veinte bugs encontrados, todos silenciosos** (numerados hasta el #21; el\n#13 se evitó)."),
    ],
}


def construye(D: Datos, docs: Path) -> dict:
    out: dict = {}
    for nombre, cambios in CONTEO.items():
        p = (docs / nombre).resolve()
        if not p.exists():
            raise SystemExit(f"ABORTA: falta {p}. No se escribio nada.")
        t0 = p.read_text(encoding="utf-8")
        t = t0
        for viejo, nuevo in cambios:
            t = M32.reemplaza_o_ya(t, viejo, nuevo, nombre)
        if t != t0:
            out[p] = t

    p = (docs / "06_DECISIONS.md").resolve()
    t = out.get(p, p.read_text(encoding="utf-8"))
    if MARCA not in t:
        t = t.rstrip("\n") + "\n\n---\n" + adr54(D) + "\n---\n" + adr55(D) + "\n---\n" + adr56(D) + "\n---\n" + adr57(D)
        out[p] = t

    p = (docs / "10_RESULTADOS.md").resolve()
    t = out.get(p, p.read_text(encoding="utf-8"))
    if MARCA not in t:
        out[p] = t.rstrip("\n") + "\n" + secciones_10(D)

    p = (docs / "README.md").resolve()
    t = out.get(p, p.read_text(encoding="utf-8"))
    if MARCA not in t:
        out[p] = M32.reemplaza(t, "## Retirados\n", readme_bloque(D), "README.md")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    ap.add_argument("--vista", type=Path, default=Path("/tmp/h2_23_vista"))
    args = ap.parse_args()
    args.raiz = args.raiz.resolve()
    D = Datos(args.raiz)
    docs = args.raiz / "docs"
    nuevos = construye(D, docs)
    res, n_ok = viaja_nueve(D)
    print(f"ADR-57 P1 recalculada sobre los nueve: {n_ok} de {len(res)}")
    if not nuevos:
        print("Nada que hacer: los cambios ya estan aplicados.")
        return 0
    quedan = M32.conteos_restantes(args.raiz, nuevos)
    print("== conteo de bugs tras aplicar ==")
    for w, fs in sorted(quedan.items()):
        print(f"  {w:<12} {', '.join(sorted(fs))}")
    args.vista.mkdir(parents=True, exist_ok=True)
    for p, t in nuevos.items():
        nv = p.name if p.parent == docs else f"RAIZ_{p.name}"
        (args.vista / nv).write_text(t, encoding="utf-8")
        print(f"  {nv:<26} -> {t.count(chr(10)):>5} lineas   vista: {args.vista / nv}")
    rc, salida = M32.verifica_vista(args.raiz, nuevos)
    print("\n== docs/verificar_docs.py sobre la vista previa ==")
    print("\n".join("  " + l for l in salida.strip().splitlines()))
    if not args.escribir:
        print("\n(vista previa; usa --escribir)")
        return 0
    if rc != 0 and not args.forzar:
        print("\nNO SE ESCRIBE: la vista previa no pasa verificar_docs.py.")
        return 1
    ts = time.strftime("%Y%m%d%H%M")
    for p, t in nuevos.items():
        shutil.copy2(p, p.with_name(p.name + f".anterior_{ts}"))
        p.write_text(t, encoding="utf-8")
        print(f"  escrito {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
