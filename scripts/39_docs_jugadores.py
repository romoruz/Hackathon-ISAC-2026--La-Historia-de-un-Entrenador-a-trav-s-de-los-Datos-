#!/usr/bin/env python3
"""
39_docs_jugadores.py — lleva ADR-58 y sus resultados a la documentacion.

Mismas reglas que `32_docs_adr53.py` y `37_docs_resultados.py`, cuyo motor y
formatos reutiliza (no los copia):
  * ninguna cifra tecleada: todas salen de reports/jugadores_v1.json;
  * reemplazos exactos; si un fragmento no aparece una vez, aborta sin escribir;
  * marca `<!-- h2_27 -->`: aplicar dos veces no duplica;
  * corre docs/verificar_docs.py sobre la vista previa y no escribe si falla.

QUE TOCA
  docs/06_DECISIONS.md   ADR-58 definitiva; nota de orientacion en ADR-54
  docs/10_RESULTADOS.md  seccion 33; nota de orientacion en el caveat de §28
  docs/13_CONTEXTO_IA.md 57 -> 58 ADRs
  docs/README.md         58 ADRs en el indice y una linea de jugadores

No hay bugs nuevos: el conteo (veinte, hasta el #21) no se toca y se imprime
para comprobarlo.

Uso:
    python scripts/39_docs_jugadores.py              # vista previa
    python scripts/39_docs_jugadores.py --escribir
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "<!-- h2_27 -->"
FUENTE = "reports/jugadores_v1.json"
FRANJA = ("banda izquierda", "centro-izquierda", "centro-derecha", "banda derecha")  # 13_verificar_ejes
PCT_BAJO = 0.15


def _carga(nombre: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, RAIZ / "scripts" / nombre)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M37 = _carga("37_docs_resultados.py", "docs37_j")
M32 = M37.M32
pp, num, icpp, icn, qf, preds_tabla = M37.pp, M37.num, M37.icpp, M37.icn, M37.qf, M37.preds_tabla
ETIQ = {"M1": "acciones/posesión", "M2": "P(remate)", "M4": "P(remate) concedido", "FT": "field tilt"}


class Datos:
    def __init__(self, raiz: Path):
        self.j = json.loads((raiz / FUENTE).read_text(encoding="utf-8"))


# ==========================================================================
# piezas calculadas
# ==========================================================================
def fmt_c(mt: str, c: dict) -> tuple[str, str]:
    if mt == "M1":
        return num(c.get("theta")), icn(c.get("ic95"))
    return pp(c.get("theta")), icpp(c.get("ic95"))


def excluye_cero(c: dict) -> bool:
    v = c.get("ic95") or [None, None]
    return v[0] is not None and (v[0] > 0 or v[1] < 0)


def rechazos(J: dict) -> list[tuple[dict, str, dict]]:
    return [(u, mt, u["C"][mt]) for u in J["unidades"] for mt in ("M1", "M2", "M4", "FT")
            if u["C"][mt].get("rechaza_adr52") or u["C"][mt].get("rechaza_casos")]


def orientacion(J: dict) -> dict:
    """Posicion del proveedor contra centro lateral de acciones (sin nombres)."""
    g = {"Right": [], "Left": []}
    for u in J["unidades"]:
        for r in u["B"]:
            c, p = r.get("centro_iy"), r.get("posicion_modal") or ""
            if c is None:
                continue
            if p.startswith("Right"):
                g["Right"].append(c)
            elif p.startswith("Left"):
                g["Left"].append(c)
    return {k: {"n": len(v), "mediana_iy": st.median(v) if v else float("nan"),
                "frac_derecha": (sum(x > 1.5 for x in v) / len(v)) if v else float("nan")}
            for k, v in g.items()}


def rotacion_era(u: dict) -> dict:
    completos = [a for a in u["A"].values() if not a.get("parcial")]
    pc = [a["percentil_continuidad"] for a in completos if a.get("percentil_continuidad") is not None]
    pn = [a["percentil_n80"] for a in completos if a.get("percentil_n80") is not None]
    return {"torneos": len(completos),
            "bajos": sum(x <= PCT_BAJO for x in pc),
            "med_cont": st.median(pc) if pc else float("nan"),
            "med_n80": st.median(pn) if pn else float("nan")}


def f2(x, d=2):
    return "—" if x is None or not np.isfinite(x) else f"{x:.{d}f}"


# ==========================================================================
# 06 · ADR-58
# ==========================================================================
def tabla_liga(J: dict) -> str:
    filas = ["| cambio | métrica | perdiendo | empatando | ganando |", "|---|---|---|---|---|"]
    for tipo, nom in (("Tactical", "táctico"), ("Injury", "por lesión")):
        for mt in ("M1", "M2", "M4", "FT"):
            celdas = []
            for k in ("perdiendo", "empatando", "ganando"):
                val, n = J["liga"][tipo][mt][k]
                s = num(val) if mt == "M1" else pp(val)
                celdas.append(f"{s} (n {n})")
            filas.append(f"| {nom} | {ETIQ[mt]} | " + " | ".join(celdas) + " |")
    return "\n".join(filas)


def adr58(D: Datos) -> str:
    J = D.j
    dg, fam = J["diagnostico"], J["familias"]
    rech = rechazos(J)
    lista = "\n".join(
        f"- {u['club']} · {u['coach']} · {mt}: θ {fmt_c(mt, c)[0]} {fmt_c(mt, c)[1]} "
        f"(q ADR-52 {qf(c.get('q_adr52'))}, q casos {qf(c.get('q_casos'))})" for u, mt, c in rech) or "- ninguno"
    return f"""
{MARCA}
## ADR-58 · Uso de jugadores: núcleo, roles y lo que pasa tras el primer cambio

**Fecha.** 2026-09-17. Preinscrita en `docs/preinscritos/ADR-58_BORRADOR.md`
(commit db715ef). Resultado: `{FUENTE}`.

**Decisión.** Tres bloques sobre las mismas eras y el mismo universo de
partidos que ADR-54 a ADR-57:

- **A · núcleo y rotación (descriptivo).** Minutos desde `positions`; por era y
  torneo: N80, continuidad del once, jugadores distintos y cambios tácticos por
  partido, cada uno como percentil en la liga del mismo torneo. Torneos con
  menos de {J['parametros']['min_partidos_torneo']} partidos de la era: parciales, sin percentil.
- **B · roles (descriptivo).** Posición modal y reparto 5×4 de las acciones de
  cada jugador con al menos {J['parametros']['min_minutos_rol']:.0f} minutos.
- **C · tras el primer cambio táctico (inferencial, nunca causal).** Primera
  sustitución táctica entre 10:00 y 35:00 del segundo tiempo; ventanas de
  10 minutos con exclusión de ±60 s; θ = Δ de la era − Δ de la liga sin el club,
  estandarizada por bloque × marcador × torneo. Bootstrap por partido,
  B = {J['parametros']['n_boot']}.

**Diagnóstico.** Reloj de `positions`: {dg['reloj_positions']} ({dg['muestras_reloj']}
muestras) · unión acciones–eventos {dg['union_acciones_eventos']:.4f} · partidos con
alineación {dg['partidos_con_alineacion']} · primeros cambios en la franja:
{dg['eventos_tacticos']} tácticos y {dg['eventos_lesion']} por lesión.

**Lo que hace la liga tras el primer cambio** (Δ = después − antes; M1 en
acciones, el resto en puntos porcentuales):

{tabla_liga(J)}

**Familias.** ADR-52: {fam['adr52']['rechazan']} de {fam['adr52']['m']} rechazan. Casos:
{fam['casos']['rechazan']} de {fam['casos']['m']}.
{lista}

{preds_tabla(J['predicciones'])}

**Redacción obligatoria.** "Tras sus primeros cambios, el equipo…". Nunca "sus
cambios provocan…": los técnicos cambian cuando el partido lo pide (confusión
por indicación), y la estratificación por minuto y marcador la atenúa sin
eliminarla. En A, el calendario cargado por competiciones que no están en los
datos (Concachampions, Leagues Cup) empuja a rotar y se declara como confusor.

**Estado.** Aceptada.
"""


# ==========================================================================
# 10 · seccion 33
# ==========================================================================
def tabla_rotacion_america(J: dict) -> str:
    filas = ["| era | torneo | partidos | N80 (pct) | continuidad (pct) | jugadores distintos (pct) | "
             "cambios tácticos/partido (pct) |", "|---|---|---|---|---|---|---|"]
    for u in J["unidades"]:
        if u["club"] != "América":
            continue
        for t, a in u["A"].items():
            if a.get("parcial"):
                filas.append(f"| {u['coach']} | {t} | {a['partidos']} | {a['n80']} (parcial) | "
                             f"{f2(a['continuidad'])} (parcial) | {a['jugadores_distintos']} (parcial) | "
                             f"{f2(a['cambios_tacticos_por_partido'])} (parcial) |")
                continue
            filas.append(
                f"| {u['coach']} | {t} | {a['partidos']} | {a['n80']} ({f2(a['percentil_n80'])}) | "
                f"{f2(a['continuidad'])} ({f2(a['percentil_continuidad'])}) | "
                f"{a['jugadores_distintos']} ({f2(a['percentil_jugadores_distintos'])}) | "
                f"{f2(a['cambios_tacticos_por_partido'])} ({f2(a['percentil_cambios_tacticos_por_partido'])}) |")
    return "\n".join(filas)


def lectura_rotacion(J: dict) -> str:
    out = []
    for u in J["unidades"]:
        if u["club"] != "América":
            continue
        r = rotacion_era(u)
        if not r["torneos"]:
            continue
        out.append(f"- **{u['coach']}**: en {r['bajos']} de {r['torneos']} torneos completos su "
                   f"continuidad del once cae en el {int(PCT_BAJO * 100)}% inferior de la liga "
                   f"(mediana del percentil {f2(r['med_cont'])}; de N80, {f2(r['med_n80'])}).")
    return "\n".join(out)


def tabla_rotacion_casos(J: dict) -> str:
    filas = ["| entrenador | club | torneos completos | en el 15% inferior de continuidad | "
             "mediana pct continuidad | mediana pct N80 |", "|---|---|---|---|---|---|"]
    for u in sorted(J["unidades"], key=lambda x: (x["coach"], x["club"])):
        if not u.get("en_casos"):
            continue
        r = rotacion_era(u)
        filas.append(f"| {u['coach']} | {u['club']} | {r['torneos']} | {r['bajos']} | "
                     f"{f2(r['med_cont'])} | {f2(r['med_n80'])} |")
    return "\n".join(filas)


def tabla_roles_america(J: dict, k: int = 5) -> str:
    filas = ["| era | posición modal | minutos | centro ix (0 = propio) | centro iy | franja más cercana |",
             "|---|---|---|---|---|---|"]
    for u in J["unidades"]:
        if u["club"] != "América":
            continue
        for r in u["B"][:k]:
            iy = r.get("centro_iy")
            fr = FRANJA[int(round(min(max(iy, 0), 3)))] if iy is not None else "—"
            filas.append(f"| {u['coach']} | {r['posicion_modal']} | {r['minutos']:.0f} | "
                         f"{f2(r.get('centro_ix'))} | {f2(iy)} | {fr} |")
    return "\n".join(filas)


def tabla_c_america(J: dict) -> str:
    filas = ["| era | eventos | métrica | θ | IC 95% | q (ADR-52) | θ sin exclusión |",
             "|---|---|---|---|---|---|---|"]
    for u in J["unidades"]:
        if u["club"] != "América":
            continue
        for mt in ("M1", "M2", "M4", "FT"):
            c = u["C"][mt]
            t, ic = fmt_c(mt, c)
            s0 = num(c.get("sin_exclusion_theta")) if mt == "M1" else pp(c.get("sin_exclusion_theta"))
            filas.append(f"| {u['coach']} | {u['C']['eventos']} | {ETIQ[mt]} | {t} | {ic} | "
                         f"{qf(c.get('q_adr52'))} | {s0} |")
    return "\n".join(filas)


def seccion_33(D: Datos) -> str:
    J = D.j
    fam = J["familias"]
    am = [u for u in J["unidades"] if u["club"] == "América"]
    n_ci = sum(excluye_cero(u["C"][mt]) for u in am for mt in ("M1", "M2", "M4", "FT"))
    n_tot = 4 * len(am)
    n_rech_am = sum(bool(u["C"][mt].get("rechaza_adr52")) for u in am for mt in ("M1", "M2", "M4", "FT"))
    frase_c = ("Ningún técnico del América se separa de forma detectable de lo que hace la liga "
               "tras su primer cambio." if n_rech_am == 0 else
               f"{n_rech_am} contrastes del América sobreviven a BH; ver la tabla.")
    o = orientacion(J)
    return f"""
{MARCA}
---

# 33. 🟢 Uso de jugadores (ADR-58)

**Fuente**: `scripts/38_jugadores.py` → `{FUENTE}`. La tabla de la liga y las
predicciones están en ADR-58. Familias: ADR-52 {fam['adr52']['rechazan']} de
{fam['adr52']['m']}; casos {fam['casos']['rechazan']} de {fam['casos']['m']}.

## 33.1 ⚪ Núcleo y rotación (descriptivo)

Percentil en la liga del mismo torneo, sin el club. **Un percentil de
continuidad bajo significa que el once cambia más que en casi toda la liga**; un
N80 alto, que los minutos se reparten entre más jugadores.

{tabla_rotacion_america(J)}

{lectura_rotacion(J)}

Las eras de casos, para ver si la rotación viaja con el entrenador:

{tabla_rotacion_casos(J)}

**Caveats.** (1) Descriptivo: no hay contraste ni familia. (2) El América juega
competiciones que no están en los datos, y el calendario cargado empuja a rotar.
(3) N80 depende del número de partidos: por eso los torneos parciales no llevan
percentil.

## 33.2 ⚪ Roles (descriptivo)

Los cinco jugadores con más minutos de cada era del América. `centro` es la
media del índice de zona de sus acciones (ix de 0 a 4 hacia el arco rival; iy
de 0 a 3, de la banda izquierda a la derecha). La tabla trae `player_id` en el
JSON; los nombres se unen en el reporte.

{tabla_roles_america(J)}

## 33.3 🟢 Tras el primer cambio táctico

{tabla_c_america(J)}

En las eras del América, {n_ci} de {n_tot} intervalos excluyen el cero **antes**
de corregir. {frase_c} Redacción: "tras sus primeros cambios, el equipo…",
nunca causal.

## 33.4 Orientación de las zonas, comprobada (2026-09-17)

Sin nombres de jugadores: los que la alineación marca por la derecha tienen su
centro lateral por encima de 1.5 en el {100 * o['Right']['frac_derecha']:.1f}% de los casos
(n = {o['Right']['n']}, mediana {o['Right']['mediana_iy']:.3f}); los de la izquierda, en el
{100 * o['Left']['frac_derecha']:.1f}% (n = {o['Left']['n']}, mediana {o['Left']['mediana_iy']:.3f}).
Con nombres, `13_verificar_ejes.py` (ataque) y `14_verificar_ejes_def.py`
(defensa, América y Cruz Azul) dieron CORRECTO sobre los datos del API. Las
etiquetas de banda de §28 y de esta sección se pueden redactar.
"""


def readme_linea(D: Datos) -> str:
    fam = D.j["familias"]
    am = [u for u in D.j["unidades"] if u["club"] == "América"]
    rot = "; ".join(f"{u['coach']} {rotacion_era(u)['bajos']} de {rotacion_era(u)['torneos']}"
                    for u in am if rotacion_era(u)["torneos"])
    return (f"- **Jugadores (ADR-58).** Tras el primer cambio táctico, se separan de la liga "
            f"{fam['adr52']['rechazan']} de {fam['adr52']['m']} contrastes. Torneos con la continuidad "
            f"del once en el 15% inferior de la liga: {rot}. §33. {MARCA}\n")


# ==========================================================================
CAMBIOS = {
    "13_CONTEXTO_IA.md": [
        ("| 57 ADRs. **No reabrir debates cerrados** |", "| 58 ADRs. **No reabrir debates cerrados** |"),
    ],
    "README.md": [
        ("| 06 | [Decisiones (57 ADRs)](06_DECISIONS.md) |", "| 06 | [Decisiones (58 ADRs)](06_DECISIONS.md) |"),
    ],
}
NOTA_54 = ("**Estado.** Aceptada. Antes de redactar frases de geografía, la orientación de\n"
           "las zonas se comprueba con `13_verificar_ejes.py`.")
NOTA_54_NUEVA = NOTA_54 + (" Comprobada el 2026-09-17 con 13 y 14 sobre los datos\n"
                           "del API (`10_RESULTADOS.md` §33.4).")
NOTA_28 = ("**Caveats.** (1) Antes de redactar dónde presiona cada técnico, hay que\n"
           "comprobar la orientación de las zonas con `13_verificar_ejes.py`.")
NOTA_28_NUEVA = NOTA_28 + " Hecho el 2026-09-17 (§33.4)."
ANCLA_README = "§31.\n\n## Retirados\n"


def restantes_57(raiz: Path, nuevos: dict[Path, str]) -> list[str]:
    out = []
    rutas = sorted((raiz / "docs").glob("*.md")) + [raiz / "README.md", raiz / "AGENTS.md"]
    for q in rutas:
        if q.exists():
            t = nuevos.get(q.resolve(), q.read_text(encoding="utf-8"))
            if re.search(r"\b57\s+ADRs?\b", t):
                out.append(str(q.relative_to(raiz)))
    return out


def construye(D: Datos, docs: Path) -> dict[Path, str]:
    out: dict[Path, str] = {}
    for nombre, cambios in CAMBIOS.items():
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
        if "## ADR-58" in t:
            raise SystemExit("ABORTA: 06_DECISIONS.md ya tiene una ADR-58 sin la marca h2_27.")
        t = M32.reemplaza_o_ya(t, NOTA_54, NOTA_54_NUEVA, "06_DECISIONS.md")
        out[p] = t.rstrip("\n") + "\n\n---\n" + adr58(D)

    p = (docs / "10_RESULTADOS.md").resolve()
    t = out.get(p, p.read_text(encoding="utf-8"))
    if MARCA not in t:
        if re.search(r"^# 33\.", t, re.M):
            raise SystemExit("ABORTA: 10_RESULTADOS.md ya tiene una seccion 33 sin la marca h2_27.")
        t = M32.reemplaza_o_ya(t, NOTA_28, NOTA_28_NUEVA, "10_RESULTADOS.md")
        out[p] = t.rstrip("\n") + "\n" + seccion_33(D)

    p = (docs / "README.md").resolve()
    t = out.get(p, p.read_text(encoding="utf-8"))
    if MARCA not in t:
        out[p] = M32.reemplaza(t, ANCLA_README, "§31.\n" + readme_linea(D) + "\n## Retirados\n", "README.md")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--forzar", action="store_true", help="escribir aunque verificar_docs.py falle")
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    ap.add_argument("--vista", type=Path, default=Path("/tmp/h2_27_vista"))
    args = ap.parse_args()
    args.raiz = args.raiz.resolve()
    D = Datos(args.raiz)
    docs = args.raiz / "docs"
    nuevos = construye(D, docs)
    o = orientacion(D.j)
    print(f"orientacion sin nombres: Right {o['Right']} · Left {o['Left']}")
    if not nuevos:
        print("Nada que hacer: los cambios ya estan aplicados.")
        return 0
    quedan = M32.conteos_restantes(args.raiz, nuevos)
    print("== conteo de bugs tras aplicar (debe quedar solo 'veinte') ==")
    for w, fs in sorted(quedan.items()):
        print(f"  {w:<12} {', '.join(sorted(fs))}")
    r57 = restantes_57(args.raiz, nuevos)
    print(f"== menciones de '57 ADRs' que quedan: {r57 or 'ninguna'}")
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
        return 0 if rc == 0 else 1
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
