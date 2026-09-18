#!/usr/bin/env python3
"""
12_reporte_html.py — el informe final (H7), reescrito para ADR-59.

QUÉ PRODUCE
-----------
Un solo `reporte.html`, autocontenido (ADR-38): datos embebidos, figuras en SVG
dibujadas por JavaScript, sin CDN ni fuentes remotas. Se abre con doble clic.

CÓMO ESTÁ HECHO
---------------
1. `recolecta()` lee los siete JSON de `reports/` (y, si existe, el parquet de
   transiciones del América para el mapa de zonas).
2. `Modelo` guarda cada cifra con su fuente (JSON › ruta) y cada frase con su
   nivel de evidencia (A probado, B medido, C descriptivo). Una frase lleva un
   solo nivel; una frase B sin intervalo no se puede construir.
3. La prosa se escribe aquí, en Python, con plantillas. El JavaScript solo
   pinta: secciones, figuras e interacción. Así el texto se revisa sin navegador.
4. Antes de escribir, la salida entera pasa por `frases_prohibidas.revisa()`.
   Si aparece una frase de ADR-59 §3, el script termina con error.

La estructura es la de ADR-59 §4 (diez secciones) con los ajustes de nivel de
`docs/preinscritos/ADR-59_ADENDA_1.md`.

Uso:
    python scripts/12_reporte_html.py
    python scripts/12_reporte_html.py --reports reports --out reporte.html
    python scripts/12_reporte_html.py --tex docs/cifras_reporte.tex
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
from frases_prohibidas import revisa  # noqa: E402

# ---------------------------------------------------------------------------
# insumos
# ---------------------------------------------------------------------------
FUENTES = {
    "h4":   ("did_h4_v1.json",        "python scripts/30_did_contemporaneo.py"),
    "pres": ("did_presion_v1.json",   "python scripts/33_did_presion.py"),
    "bp":   ("balon_parado_v2.json",  "python scripts/35_balon_parado.py"),
    "ctx":  ("contexto_v1.json",      "python scripts/36_contexto.py"),
    "jug":  ("jugadores_v1.json",     "python scripts/38_jugadores.py"),
    "met":  ("metricas_v1.json",      "python scripts/40_panel_55.py"),
    "der":  ("deriva_proveedor.json", "script de deriva del proveedor (ver 06_DECISIONS)"),
}
PARQUET_AMERICA = "data/processed_api_america/transitions.parquet"

CLUB = "América"
FOCO = "Andre Jardine"
ERAS_CLUB = ["Andre Jardine", "Fernando Ortiz", "Santiago Solari"]
FUERA = [("Atlético San Luis", "Andre Jardine"), ("Monterrey", "Fernando Ortiz")]

# Reglas numéricas del informe. Son reglas, no resultados: cada una con su origen.
REGLAS = {
    "cont_inferior": (0.15, "ADR-59 §4 · §6: continuidad en el 15% inferior"),
    "n80_mediana":   (0.50, "ADR-59 adenda 1, punto 6: N80 por encima de la mediana"),
    "alpha":         (0.05, "BH al 5% (ADR-53 a 58)"),
    "equivalencia":  (0.03, "ADR-53 D53-4: margen de equivalencia de E[T]"),
}
NX, NY = 5, 4


# ---------------------------------------------------------------------------
# formato
# ---------------------------------------------------------------------------
def _s(x: float, dec: int) -> str:
    v = round(x, dec)
    if v == 0:
        v = 0.0
    return f"{v:+.{dec}f}".replace("-", "−")


def f_pct(x, dec=1):      # proporción relativa → "+24.6%"
    return _s(x * 100, dec) + "%"


def f_pp(x, dec=1):       # diferencia de proporciones → "+11.0 pp"
    return _s(x * 100, dec) + " pp"


def f_num(x, dec=2, signo=True):
    return _s(x, dec) if signo else f"{x:.{dec}f}"


def f_ic(ic, fmt, **kw):
    lo, hi = (fmt(v, **kw).replace(" pp", "").replace("%", "") for v in ic)
    return f"[{lo}, {hi}]"


def f_q(q):
    return f"{q:.3f}"


def margen(ic):
    """Extremo del IC más lejano al cero (ADR-59 §3)."""
    return max(abs(ic[0]), abs(ic[1]))


def fuerza(q):
    if q is None:
        return "sin contraste"
    if q <= 0.01:
        return "muy sólido"
    if q <= 0.05:
        return "sólido, con margen estrecho"
    if q <= 0.15:
        return "insuficiente tras corregir"
    return "no lo distinguimos del azar"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------------------
# el modelo: cifras con fuente y frases con nivel
# ---------------------------------------------------------------------------
class FaltaInsumo(Exception):
    def __init__(self, clave):
        self.clave = clave


class LecturaCambio(Exception):
    """Los datos ya no sostienen una frase preinscrita. No se imprime: decide un humano."""


def exige(cond: bool, msg: str):
    if not cond:
        raise LecturaCambio(msg)


class Modelo:
    NIVELES = ("A", "B", "C")

    def __init__(self, J: dict):
        self.J = J
        self.cifras: list[dict] = []

    def need(self, *claves):
        for k in claves:
            if self.J.get(k) is None:
                raise FaltaInsumo(k)

    # -- cifras ------------------------------------------------------------
    def c(self, texto: str, fuente: str, clave: str = "") -> str:
        """Una cifra en el texto. Siempre con fuente; el tooltip la muestra.
        `clave` la exporta como macro \\cifra<clave> para la guía LaTeX."""
        self.cifras.append({"t": texto, "f": fuente, "k": clave})
        return (f'<span class="cf" data-f="{esc(fuente)}" '
                f'data-tip="<b>fuente</b>{esc(esc(fuente))}">{esc(texto)}</span>')

    def regla(self, clave: str, texto: str) -> str:
        return self.c(texto, REGLAS[clave][1])

    # -- frases ------------------------------------------------------------
    def frase(self, nivel: str, html_: str, *, ic=True, nota_adenda: str = "") -> dict:
        assert nivel in self.NIVELES, nivel
        if nivel == "B" and not ic:
            raise ValueError("una frase B necesita intervalo (ADR-59 §2)")
        return {"tipo": "frase", "nivel": nivel, "html": html_,
                "adenda": nota_adenda}

    def nulo(self, html_: str) -> dict:
        return {"tipo": "frase", "nivel": "A", "nulo": True, "html": html_,
                "adenda": False}

    def nota(self, html_: str) -> dict:
        return {"tipo": "nota", "html": html_}

    def fig(self, fid: str, titulo: str, pie: str, datos) -> dict:
        return {"tipo": "fig", "id": fid, "titulo": titulo, "pie": pie,
                "datos": datos}

    def plegable(self, titulo: str, html_: str) -> dict:
        return {"tipo": "plegable", "titulo": titulo, "html": html_}


# ---------------------------------------------------------------------------
# lectura
# ---------------------------------------------------------------------------
def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _commit() -> dict:
    try:
        rev = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if rev.returncode:
            return {"hash": "sin git", "sucio": None}
        st = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain",
                             "--", "scripts", "src"],
                            capture_output=True, text=True, timeout=5)
        return {"hash": rev.stdout.strip(), "sucio": bool(st.stdout.strip())}
    except Exception:
        return {"hash": "sin git", "sucio": None}


def _zonas_parquet(ruta: Path):
    """Mapa 'dónde vive' del América de Jardine (se conserva de la versión
    anterior: mapa_zonas). Devuelve None si no hay parquet o polars."""
    if not ruta.exists():
        return None
    try:
        import numpy as np
        import polars as pl
    except ImportError:
        return None
    t = pl.read_parquet(ruta)
    t = t.filter((pl.col("team") == CLUB) & (pl.col("coach") == FOCO))
    m = np.zeros((NX, NY))
    if t.height:
        z = t["from_state"].to_numpy().astype(int) // 4
        for a, b in zip(z // NY, z % NY):
            if 0 <= a < NX and 0 <= b < NY:
                m[a, b] += 1
    tot = max(m.sum(), 1e-9)
    return {"m": (m / tot).round(5).tolist(), "n": int(m.sum())}


def recolecta(reports: Path, parquet: Path) -> tuple[dict, dict]:
    J, traza = {}, {"commit": _commit(), "insumos": [],
                    "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    for k, (nombre, cmd) in FUENTES.items():
        p = reports / nombre
        if p.exists():
            J[k] = json.loads(p.read_text(encoding="utf-8"))
            traza["insumos"].append({
                "archivo": nombre, "sha": _sha(p)[:12],
                "fecha": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})
        else:
            J[k] = None
            traza["insumos"].append({"archivo": nombre, "sha": None, "fecha": None,
                                     "comando": cmd})
    J["zonas"] = _zonas_parquet(parquet)
    return J, traza


# ---------------------------------------------------------------------------
# accesos
# ---------------------------------------------------------------------------
# Clave compuesta (club, entrenador): bugs #17 y #18. Una entrada sin `club` no
# se usa nunca (ni siquiera si el nombre coincide) y queda anotada aquí para
# avisar al final de la corrida.
SIN_CLUB: list[str] = []


def _del_club(e: dict, club: str, donde: str) -> bool:
    c = e.get("club")
    if c is None:
        if donde not in SIN_CLUB:
            SIN_CLUB.append(donde)
        return False
    return c == club


def unidad(J, k, club, coach):
    hallados = [u for u in J[k]["unidades"]
                if _del_club(u, club, f"{k} › unidades[{u.get('coach')}]")
                and u["coach"] == coach]
    if len(hallados) > 1:
        raise KeyError(f"{k}: {len(hallados)} unidades para {club} / {coach}")
    if not hallados:
        raise KeyError(f"{k}: sin unidad {club} / {coach}")
    return hallados[0]


def par(lista, club, a, b):
    hallados = [p for p in lista
                if _del_club(p, club, f"pares[{p.get('a')} / {p.get('b')}]")
                and {p["a"], p["b"]} == {a, b}]
    if len(hallados) > 1:
        raise KeyError(f"{len(hallados)} pares para {club}: {a} / {b}")
    if not hallados:
        raise KeyError(f"sin par {club}: {a} / {b}")
    return hallados[0], (hallados[0]["a"] == a)


def ape(n):
    return n.split()[-1]


def torneos_orden(J):
    return J["h4"]["parametros"]["torneos_orden"]


# ---------------------------------------------------------------------------
# marcador de predicciones
# ---------------------------------------------------------------------------
def predicciones_adr53(h4) -> list[dict]:
    """ADR-53 no dejó `predicciones` en su JSON. Se recalculan con los cuatro
    criterios escritos en 06_DECISIONS (ADR-53, tabla de predicciones)."""
    ft = h4["firma_temporal"]
    r_did = ft["did"]["posterior_mas_largo"] / ft["did"]["de"]
    r_cru = ft["crudo"]["posterior_mas_largo"] / ft["crudo"]["de"]
    cocca, _ = par(h4["pares"], "Atlas", "Diego Cocca I", "Diego Cocca II")
    neg_sig = cocca["did"]["E_T"]["rel"] < 0 and cocca["did"]["E_T"]["rechaza_fdr"]
    js, _ = par(h4["pares"], CLUB, "Andre Jardine", "Santiago Solari")
    d, c = js["did"]["E_T"]["rel"], js["crudo"]["E_T"]["rel"]
    return [
        {"adr": 53, "n": 1, "texto": "la firma temporal baja respecto al crudo",
         "cumple": r_did < r_cru},
        {"adr": 53, "n": 2, "texto": "Cocca I contra Cocca II deja de ser negativo y rechazado",
         "cumple": not neg_sig},
        {"adr": 53, "n": 3, "texto": "Jardine contra Solari conserva el signo y se reduce",
         "cumple": (d > 0) == (c > 0) and abs(d) < abs(c)},
        {"adr": 53, "n": 4, "texto": "ningún par demuestra equivalencia al 3%",
         "cumple": h4["control_negativo"]["n_equivalentes"] == 0},
    ]


def marcador(J) -> list[dict]:
    out = predicciones_adr53(J["h4"])
    for k, adr in (("pres", 54), ("bp", 55)):
        out += [{"adr": adr, "n": p["n"], "texto": p["texto"], "cumple": p["cumple"]}
                for p in J[k]["predicciones"]]
    out += [{"adr": p["adr"], "n": p["n"], "texto": p["texto"], "cumple": p["cumple"]}
            for p in J["ctx"]["predicciones"]]
    out += [{"adr": 58, "n": p["n"], "texto": p["texto"], "cumple": p["cumple"]}
            for p in J["jug"]["predicciones"]]
    return out


def viajan_marcador(ctx) -> tuple[int, int, list]:
    """ADR-57 P1 sobre los nueve técnicos de varios clubes FUERA del América
    (adenda 1, punto 3). El JSON cuenta también a Jardine y a Ortiz."""
    fuera = {k: v for k, v in ctx["viaja_marcador_M1"].items()
             if k not in ERAS_CLUB}
    return sum(fuera.values()), len(fuera), sorted(fuera.items())


# ---------------------------------------------------------------------------
# secciones
# ---------------------------------------------------------------------------
def sec01(M: Modelo):
    M.need("h4", "der")
    h4, der = M.J["h4"], M.J["der"]
    ft = h4["firma_temporal"]
    F = "did_h4_v1 › firma_temporal"
    serie = sorted(der["por_torneo"], key=lambda r: r["torneo_orden"])
    B = [
        M.frase("C", "Cada posesión se lee con tres preguntas: <b>dónde se juega</b>, "
                "<b>cuánto dura</b> y <b>con qué probabilidad termina en remate o gol</b>. "
                "Todo lo demás del informe son respuestas a esas tres preguntas."),
        M.fig("fig1", "Las tres preguntas de una posesión",
              "Esquema. La cancha está partida en 20 zonas; el equipo analizado ataca "
              "hacia la derecha.", None),
        M.frase("C", "El proveedor de datos cambió su forma de registrar eventos entre "
                "torneos: la cantidad de acciones por posesión se mueve para los " +
                M.c(f'{serie[0]["clubes"]} clubes', "deriva_proveedor › por_torneo.clubes") +
                " a la vez. Sin corregir, " + M.c(f'{ft["crudo"]["posterior_mas_largo"]} de '
                f'{ft["crudo"]["de"]}', F + ".crudo", "FirmaCru") +
                " pares que difieren dan al técnico más reciente las posesiones más largas; "
                "comparando cada era contra la liga del mismo torneo, " +
                M.c(f'{ft["did"]["posterior_mas_largo"]} de {ft["did"]["de"]}', F + ".did", "FirmaDid") +
                ". Por eso toda comparación del informe es contra la liga del mismo torneo, "
                "sin los partidos del club."),
        M.fig("fig1b", "Acciones por posesión en la liga, torneo a torneo (sin filtrar)",
              "Media de todos los clubes por torneo; la banda es ± una desviación estándar "
              "entre clubes. Fuente: deriva_proveedor › por_torneo.",
              [{"t": r["torneo"], "v": r["acc_por_posesion_cruda_media"],
                "sd": r["acc_por_posesion_cruda_sd_clubes"]} for r in serie]),
        M.plegable("Definiciones y la cadena de Markov", DEF_MARKOV),
    ]
    return B


def sec02(M: Modelo):
    M.need("h4", "met")
    J = M.J
    u = unidad(J, "h4", CLUB, FOCO)
    g = unidad(J, "met", CLUB, FOCO)["global"]
    lig = J["met"]["liga"]["media"]
    Fu = "did_h4_v1 › unidades[América, Jardine]"
    Fm = "metricas_v1 › unidades[América, Jardine] › global"
    pjs, _ = par(J["h4"]["pares"], CLUB, FOCO, "Santiago Solari")
    pjo, _ = par(J["h4"]["pares"], CLUB, FOCO, "Fernando Ortiz")
    es, eo = pjs["did"]["E_T"], pjo["did"]["E_T"]
    Fp = "did_h4_v1 › pares[América, {}] › did.E_T"
    ic_o_excluye = eo["ic95"][0] * eo["ic95"][1] > 0
    exige(u["rel_E_T_vs_liga_ic95"][0] > 0, "§2: la posesión de Jardine ya no está por encima de la liga")
    exige(es["rechaza_fdr"] and es["rel"] > 0, "§2: Jardine–Solari ya no difiere (A)")
    exige(not eo["rechaza_fdr"], "§2: Jardine–Ortiz ahora sobrevive a BH; ya no es un nulo")
    for k in ("prog_pases", "npxg_favor", "obv_favor", "field_tilt"):
        exige(g[k]["ic95"][0] > 0, f"§2: {k} ya no está por encima de la liga")

    B = [
        M.frase("B", "Bajo Jardine, las posesiones del América duraron " +
                M.c(f_pct(u["rel_E_T_vs_liga"]), Fu + " › rel_E_T_vs_liga", "PosJ") +
                " más que las de la liga en los mismos torneos " +
                M.c(f_ic(u["rel_E_T_vs_liga_ic95"], f_pct), Fu + " › rel_E_T_vs_liga_ic95", "PosJic") +
                ", medido en acciones por posesión."),
        M.frase("A", "Difieren de las del América de Solari: " +
                M.c(f_pct(es["rel"]), Fp.format("Jardine–Solari"), "SolJ") + " " +
                M.c(f_ic(es["ic95"], f_pct), Fp.format("Jardine–Solari") + ".ic95", "SolJic") +
                ", q = " + M.c(f_q(es["q"]), Fp.format("Jardine–Solari") + ".q", "SolJq") +
                f" ({fuerza(es['q'])})."),
        M.nulo("Contra el América de Ortiz: " +
               M.c(f_pct(eo["rel"]), Fp.format("Jardine–Ortiz"), "OrtJ") + " " +
               M.c(f_ic(eo["ic95"], f_pct), Fp.format("Jardine–Ortiz") + ".ic95", "OrtJic") +
               ", q = " + M.c(f_q(eo["q"]), Fp.format("Jardine–Ortiz") + ".q", "OrtJq") + ". " +
               ("El intervalo no toca el cero, pero la diferencia no sobrevive a la "
                "corrección por comparaciones múltiples; si existe, es menor a "
                if ic_o_excluye else "No detectamos una diferencia mayor a ") +
               M.c(f"{margen(eo['ic95']) * 100:.1f}%", Fp.format("Jardine–Ortiz") +
                   ".ic95 (extremo más lejano al cero)", "OrtJmargen") + "."),
        M.fig("fig3", "Pares del América: corregido contra crudo",
              "Duración de la posesión, diferencia relativa. Punto lleno: comparación "
              "contra la liga del mismo torneo. Aro: la resta cruda, sin corregir la deriva.",
              [{"par": f"{ape(p['a'])} – {ape(p['b'])}",
                "did": p["did"]["E_T"]["rel"], "did_ic": p["did"]["E_T"]["ic95"],
                "q": p["did"]["E_T"]["q"], "rech": p["did"]["E_T"]["rechaza_fdr"],
                "cru": p["crudo"]["E_T"]["rel"], "cru_ic": p["crudo"]["E_T"]["ic95"],
                "cru_rech": p["crudo"]["E_T"]["rechaza_fdr"]}
               for p in J["h4"]["pares"] if p["club"] == CLUB]),
        M.frase("B", "Progresión: " +
                M.c(f_num(g["prog_pases"]["dif"], 1), Fm + " › prog_pases.dif") +
                " pases progresivos por partido sobre la liga " +
                M.c(f_ic(g["prog_pases"]["ic95"], f_num, dec=1), Fm + " › prog_pases.ic95") + "."),
        M.frase("B", "Ocasiones: " +
                M.c(f_num(g["npxg_favor"]["dif"]), Fm + " › npxg_favor.dif") +
                " npxG por partido " +
                M.c(f_ic(g["npxg_favor"]["ic95"], f_num), Fm + " › npxg_favor.ic95") +
                " sobre una liga de " +
                M.c(f_num(lig["npxg_favor"], 2, signo=False), "metricas_v1 › liga.media.npxg_favor") +
                "; OBV a favor " +
                M.c(f_num(g["obv_favor"]["dif"]), Fm + " › obv_favor.dif") + " " +
                M.c(f_ic(g["obv_favor"]["ic95"], f_num), Fm + " › obv_favor.ic95") + "."),
        M.frase("B", "Dominio territorial: field tilt " +
                M.c(f_pp(g["field_tilt"]["dif"]), Fm + " › field_tilt.dif", "FtJ") + " " +
                M.c(f_ic(g["field_tilt"]["ic95"], f_pp), Fm + " › field_tilt.ic95", "FtJic") +
                " por encima de la liga."),
        M.fig("fig2", "Dónde vive el América de Jardine",
              "Porcentaje de las acciones de la cadena en cada zona. Orientación "
              "verificada (10_RESULTADOS §33.4).",
              J["zonas"] or {"falta": PARQUET_AMERICA}),
    ]
    return B


def sec03(M: Modelo):
    M.need("met", "pres")
    J = M.J
    g = unidad(J, "met", CLUB, FOCO)["global"]
    Fm = "metricas_v1 › unidades[América, Jardine] › global"
    pp = J["pres"]["pares"]
    jo, so = par(pp, CLUB, FOCO, "Fernando Ortiz")
    js, ss = par(pp, CLUB, FOCO, "Santiago Solari")
    os_, s3 = par(pp, CLUB, "Fernando Ortiz", "Santiago Solari")
    Fp = "did_presion_v1 › pares[América, {}] › contrastes.{}.did"

    def e(p, k, a_primero):
        d = p["contrastes"][k]["did"]
        s = 1 if a_primero else -1
        ic = sorted([s * d["ic95"][0], s * d["ic95"][1]])
        return {"t": s * d["theta"], "ic": ic, "q": d["q"], "r": d["rechaza"]}

    E2o, E2s, E2x = e(jo, "E2", so), e(js, "E2", ss), e(os_, "E2", s3)
    E4o, E4s = e(jo, "E4", so), e(js, "E4", ss)
    exige(g["npxg_contra"]["ic95"][1] < 0, "§3: el npxG concedido ya no está por debajo de la liga")
    exige(not E2o["r"] and not E2s["r"], "§3: una presión de Jardine ahora sobrevive a BH")
    exige(E2s["ic"][0] * E2s["ic"][1] > 0, "§3: el IC Jardine–Solari ya cruza el cero; cambia la redacción")
    exige(E2x["r"] and E2x["t"] > 0, "§3: Ortiz–Solari ya no difiere (A)")
    B = [
        M.frase("B", "Bajo Jardine, el América concedió " +
                M.c(f_num(g["npxg_contra"]["dif"]), Fm + " › npxg_contra.dif") +
                " npxG por partido respecto a la liga " +
                M.c(f_ic(g["npxg_contra"]["ic95"], f_num), Fm + " › npxg_contra.ic95") + "."),
        M.nulo("Nivel de presión (por acción del rival, E2) contra Ortiz: " +
               M.c(f_pp(E2o["t"]), Fp.format("Jardine–Ortiz", "E2"), "PresJO") + " " +
               M.c(f_ic(E2o["ic"], f_pp), Fp.format("Jardine–Ortiz", "E2") + ".ic95", "PresJOic") +
               ". No detectamos una diferencia de nivel de presión mayor a " +
               M.c(f"{margen(E2o['ic']) * 100:.1f} pp",
                   Fp.format("Jardine–Ortiz", "E2") + ".ic95 (extremo más lejano al cero)", "PresMargen") + "."),
        M.nulo("Contra Solari: " +
               M.c(f_pp(E2s["t"]), Fp.format("Jardine–Solari", "E2")) + " " +
               M.c(f_ic(E2s["ic"], f_pp), Fp.format("Jardine–Solari", "E2") + ".ic95") +
               ", q = " + M.c(f_q(E2s["q"]), Fp.format("Jardine–Solari", "E2") + ".q") +
               ". El intervalo no toca el cero, pero no sobrevive a la corrección; "
               "si existe, es menor a " +
               M.c(f"{margen(E2s['ic']) * 100:.1f} pp",
                   Fp.format("Jardine–Solari", "E2") + ".ic95 (extremo más lejano al cero)") + "."),
        M.frase("A", "Lo que el método sí detecta en el mismo club: el América de Ortiz "
                "presiona más que el de Solari, " +
                M.c(f_pp(E2x["t"]), Fp.format("Ortiz–Solari", "E2")) + " " +
                M.c(f_ic(E2x["ic"], f_pp), Fp.format("Ortiz–Solari", "E2") + ".ic95") +
                ", q = " + M.c(f_q(E2x["q"]), Fp.format("Ortiz–Solari", "E2") + ".q") +
                f" ({fuerza(E2x['q'])})."),
        M.fig("fig3b", "Presión en el América, por pareja",
              "E2: nivel de presión por acción del rival, en puntos porcentuales. "
              "Punto lleno: sobrevive a la corrección; aro: no.",
              [{"par": "Jardine – Ortiz", **E2o}, {"par": "Jardine – Solari", **E2s},
               {"par": "Ortiz – Solari", **E2x}]),
        M.frase("C", "Transiciones: sin tiempo en segundos, el informe usa un sustituto "
                "declarado, E4 (posesiones rivales de una sola acción en juego abierto). "
                "Jardine contra Ortiz " + M.c(f_pp(E4o["t"]), Fp.format("Jardine–Ortiz", "E4")) +
                "; contra Solari " + M.c(f_pp(E4s["t"]), Fp.format("Jardine–Solari", "E4")) +
                (". Ninguno sobrevive a la corrección." if not (E4o["r"] or E4s["r"])
                 else ". Ver la tabla de pares para el veredicto de cada uno.")),
        M.nota("Todas las cifras de presión de esta sección son <b>por acción del rival</b> "
               "(E2), no por posesión (15_REPORTE_HTML §8)."),
    ]
    return B


def sec04(M: Modelo):
    M.need("h4", "met")
    J = M.J
    u = unidad(J, "h4", CLUB, FOCO)
    m = unidad(J, "met", CLUB, FOCO)["por_torneo"]
    ts = [t for t in torneos_orden(J) if t in u["serie_por_torneo"]]
    serie = [{"t": t, "pos": u["serie_por_torneo"][t]["rel_E_T"],
              "n": u["serie_por_torneo"][t]["n_poss"],
              "ft": m[t]["field_tilt"]["percentil"] if t in m and not m[t]["parcial"] else None,
              "xg": m[t]["npxg_favor"]["percentil"] if t in m and not m[t]["parcial"] else None}
             for t in ts]
    F = "did_h4_v1 › unidades[América, Jardine] › serie_por_torneo"
    Fm = "metricas_v1 › unidades[América, Jardine] › por_torneo"
    pos_txt = ", ".join(M.c(f_pct(s["pos"]), f"{F}.{s['t']}.rel_E_T") for s in serie)
    n_sobre = sum(s["pos"] > 0 for s in serie)
    cierre = (". Todos por encima de la liga." if n_sobre == len(serie) else
              ". Por encima de la liga en " + M.c(f"{n_sobre} de {len(serie)}", F) + ".")
    ft = [s["ft"] for s in serie if s["ft"] is not None]
    comp = [s for s in serie if s["xg"] is not None]
    exige(len(comp) >= 2, "§4: menos de dos torneos completos en metricas_v1")
    xg = [s["xg"] for s in comp]
    ult = comp[-1]
    B = [
        M.frase("C", f"Posesión sobre la liga en los {M.c(str(len(serie)), F)} torneos, "
                "en orden: " + pos_txt + cierre,
                nota_adenda="ADR-59 la marcaba B; la serie por torneo no trae intervalo."),
        M.frase("C", "Field tilt entre el percentil " +
                M.c(f"{min(ft):.2f}", Fm + " › field_tilt.percentil (mín)") + " y el " +
                M.c(f"{max(ft):.2f}", Fm + " › field_tilt.percentil (máx)") +
                " de la liga en los torneos completos."),
        M.frase("C", "npxG a favor entre el percentil " +
                M.c(f"{min(xg[:-1]):.2f}", Fm + " › npxg_favor.percentil (mín, sin el último)") +
                " y el " + M.c(f"{max(xg[:-1]):.2f}", Fm + " › npxg_favor.percentil (máx)") +
                " en los torneos anteriores, y " +
                M.c(f"{ult['xg']:.2f}", f"{Fm}.{ult['t']}.npxg_favor.percentil") +
                " en " + ult["t"] + ". Es la evolución observada; el informe no le "
                "atribuye una causa."),
        M.fig("fig4", "Torneo a torneo, contra la liga",
              "Cambia la métrica con el selector. La línea punteada es la liga del "
              "mismo torneo.", serie),
    ]
    return B


CTX = {"localia": ("local", "visitante", "localía"),
       "marcador": ("perdiendo", "ganando", "marcador"),
       "momento": ("min>=60", "min<60", "minuto 60"),
       "rival": ("fuerte", "debil", "rival")}
MET = {"M1": ("acciones por posesión", "num"),
       "M2": ("P(remate) a favor", "pp"),
       "M3": ("presión del que defiende", "pp"),
       "M4": ("P(remate) concedido", "pp")}


def sec05(M: Modelo):
    M.need("ctx")
    ctx = M.J["ctx"]
    liga = []
    for c, (a, b, nom) in CTX.items():
        for mk, (mn, uni) in MET.items():
            va, vb = ctx["liga"][c][mk][a], ctx["liga"][c][mk][b]
            liga.append({"ctx": nom, "a": a, "b": b, "m": mn, "uni": uni,
                         "va": va, "vb": vb, "d": va - vb})
    bosque = {}
    for coach in ERAS_CLUB:
        u = unidad(M.J, "ctx", CLUB, coach)
        filas = []
        for c, (a, b, nom) in CTX.items():
            for mk, (mn, uni) in MET.items():
                d = u["contrastes"][f"{c}|{mk}"]
                filas.append({"ctx": nom, "m": mk, "mn": mn, "uni": uni,
                              "t": d["theta"], "ic": d["ic95"],
                              "q": d["q_casos"], "r": d["rechaza_casos"]})
        bosque[coach] = filas
    fj = bosque[FOCO]
    n_total = sum(len(v) for v in bosque.values())
    n_rech = sum(f["r"] for v in bosque.values() for f in v)
    excl = [f for f in fj if f["ic"][0] * f["ic"][1] > 0]
    F = "contexto_v1 › unidades[América, *] › contrastes"

    def fx(f):
        return f_num(f["t"], 2) if f["uni"] == "num" else f_pp(f["t"])

    exige(not any(f["r"] for f in fj), "§5: un contraste de Jardine ahora sobrevive a BH")
    excl_txt = "; ".join(
        f'{f["ctx"]} · {f["mn"]} ' +
        M.c(fx(f), f"contexto_v1 › unidades[América, Jardine] › contrastes.{f['ctx']}|{f['m']}.theta")
        for f in excl)
    B = [
        M.frase("C", "Lo que ajusta la liga entera: perdiendo contra ganando, en casa contra "
                "fuera, antes y después del minuto 60, y ante rivales fuertes o débiles. "
                "La tabla muestra los dos valores de cada contexto.", nota_adenda="ADR-59 la marcaba B; contexto_v1 › liga no trae intervalo."),
        M.fig("tabla5", "Lo que ajusta la liga", "Fuente: contexto_v1 › liga. Sin intervalo en "
              "el JSON: se muestra como descriptivo (adenda 1).", liga),
        M.nulo("El América ajusta al contexto como la liga: " +
               M.c(f"{n_rech} de {n_total}", F + " › rechaza_casos (tres eras × 16)", "CtxRech") +
               " contrastes sobreviven a la corrección. " +
               (f"Bajo Jardine, {M.c(str(len(excl)), F + ' (IC que excluye el cero)')} "
                "intervalos excluyen el cero antes de corregir y ninguno sobrevive: " +
                excl_txt + "." if excl else "")),
        M.fig("fig5", "Bosque de θ: cuánto ajusta cada era más allá de la liga",
              "θ = ajuste de la era menos ajuste de la liga en el mismo contexto. "
              "Aro: el intervalo excluye el cero antes de corregir, pero no sobrevive. "
              "Cada nulo se lee por su extremo más lejano.", bosque),
    ]
    return B


def sec06(M: Modelo):
    M.need("jug")
    jug = M.J["jug"]
    u = unidad(M.J, "jug", CLUB, FOCO)
    ts = [t for t in torneos_orden(M.J) if t in u["A"]]
    A = [{"t": t, **{k: u["A"][t].get(k) for k in
          ("percentil_continuidad", "percentil_n80", "n80", "continuidad", "parcial",
           "jugadores_distintos")}} for t in ts]
    completos = [a for a in A if not a["parcial"]]
    lim_c, lim_n = REGLAS["cont_inferior"][0], REGLAS["n80_mediana"][0]
    n_bajo = sum(a["percentil_continuidad"] <= lim_c for a in completos)
    n_alto = sum(a["percentil_n80"] > lim_n for a in completos)
    top = sorted(u["B"], key=lambda b: -b["minutos"])[:5]
    C = u["C"]
    tl = jug["liga"]["Tactical"]
    Fa = "jugadores_v1 › unidades[América, Jardine] › A"
    exige(not C["M2"]["rechaza_casos"] and not C["FT"]["rechaza_casos"],
          "§6: el cambio tras el primer cambio ahora sobrevive a BH")
    exige(C["M2"]["ic95"][0] < 0 < C["M2"]["ic95"][1] and C["FT"]["ic95"][0] < 0 < C["FT"]["ic95"][1],
          "§6: un IC tras el primer cambio ya no cruza el cero; cambia la redacción")
    Fc = "jugadores_v1 › unidades[América, Jardine] › C"
    B = [
        M.frase("C", "Rotación: la continuidad del once quedó en el " +
                M.regla("cont_inferior", "15%") + " inferior de la liga en " +
                M.c(f"{n_bajo} de {len(completos)}", Fa + " › percentil_continuidad", "RotJ") +
                " torneos, y el número de jugadores que suman el 80% de los minutos (N80) "
                "quedó por encima de la " + M.regla("n80_mediana", "mediana") +
                " de la liga en " + M.c(f"{n_alto} de {len(completos)}", Fa + " › percentil_n80") +
                ". Hay partidos fuera de estos datos (otras competiciones) que pueden "
                "estar detrás de la rotación; no los medimos.", nota_adenda="El umbral del N80 (mediana) lo fija la adenda; ADR-58 no lo fijaba."),
        M.fig("fig6", "Continuidad del once y N80, percentil en la liga",
              "Cada anillo es un torneo. Continuidad baja = más cambios en el once.", A),
        M.frase("C", "Roles: los cinco jugadores con más minutos, con su posición más "
                "frecuente y dónde intervienen. Toca uno para ver su mapa."),
        M.fig("roles", "Los cinco con más minutos", "Fuente: jugadores_v1 › B. Sin nombres: "
              "el JSON solo trae el identificador del jugador.",
              [{"id": b["player_id"], "pos": b["posicion_modal"], "min": b["minutos"],
                "acc": b["acciones"],
                "z": [b["zonas"][ix * NY:(ix + 1) * NY] for ix in range(NX)]} for b in top]),
        M.nulo("Tras sus primeros cambios, el equipo no se movió de forma detectable: "
               "remate " + M.c(f_pp(C["M2"]["theta"]), Fc + " › M2.theta") + " " +
               M.c(f_ic(C["M2"]["ic95"], f_pp), Fc + " › M2.ic95") + "; field tilt " +
               M.c(f_pp(C["FT"]["theta"]), Fc + " › FT.theta") + " " +
               M.c(f_ic(C["FT"]["ic95"], f_pp), Fc + " › FT.ic95") +
               ". No detectamos un cambio mayor a " +
               M.c(f"{margen(C['M2']['ic95']) * 100:.1f} pp", Fc + " › M2.ic95 (extremo)") +
               " en remate ni a " +
               M.c(f"{margen(C['FT']['ic95']) * 100:.1f} pp", Fc + " › FT.ic95 (extremo)") +
               " en field tilt."),
        M.frase("C", "En la liga, tras el primer cambio cuando el equipo va perdiendo: "
                "remate " + M.c(f_pp(tl["M2"]["perdiendo"][0]),
                                "jugadores_v1 › liga.Tactical.M2.perdiendo[0]") +
                " y field tilt " + M.c(f_pp(tl["FT"]["perdiendo"][0]),
                                       "jugadores_v1 › liga.Tactical.FT.perdiendo[0]") + ".",
                nota_adenda="ADR-59 la marcaba B; el JSON trae [delta, n], sin intervalo."),
    ]
    return B


def sec07(M: Modelo):
    M.need("bp")
    bp = M.J["bp"]
    lg, mo = bp["liga"], bp["modelo"]
    u = unidad(M.J, "bp", CLUB, FOCO)
    Fl = "balon_parado_v2 › liga"
    Fu = "balon_parado_v2 › unidades[América, Jardine]"
    of, de = u["C1_of"], u["C1_def"]
    exige(not (of["rechaza"] or of["rechaza_casos"] or de["rechaza"] or de["rechaza_casos"]),
          "§7: el América ahora se separa de la liga en córners")
    exige(mo["delta_auc_ic95_percentil"][0] > 0, "§7: ΔAUC ya no excluye el cero")
    tipos = [("corner", "córner"), ("tiro_libre", "tiro libre indirecto"), ("banda", "saque de banda")]
    B = [
        M.frase("C", "El embudo de la liga: tras un córner, la secuencia termina en remate "
                "con probabilidad " + M.c(f"{lg['P_S_secuencia']['corner']:.3f}",
                                          Fl + " › P_S_secuencia.corner") +
                "; tras un tiro libre indirecto, " + M.c(f"{lg['P_S_secuencia']['tiro_libre']:.3f}",
                                               Fl + " › P_S_secuencia.tiro_libre") +
                "; tras un saque de banda, " + M.c(f"{lg['P_S_secuencia']['banda']:.3f}",
                                                   Fl + " › P_S_secuencia.banda") +
                ". En gol, el córner llega a " + M.c(f"{lg['P_G_secuencia']['corner']:.3f}",
                                                     Fl + " › P_G_secuencia.corner") + ".",
                nota_adenda="ADR-59 la marcaba B; el embudo de la liga no trae intervalo."),
        M.fig("fig7", "Embudo del balón parado en la liga",
              "Cambia entre remate y gol con el selector.",
              [{"k": k, "n": n, "s": lg["P_S_secuencia"][k], "g": lg["P_G_secuencia"][k]}
               for k, n in tipos]),
        M.frase("B", "Añadir la geometría del remate (portería libre, defensores) mejora "
                "la discriminación del modelo de xG en " +
                M.c(f"{mo['delta_auc']:+.3f}", "balon_parado_v2 › modelo.delta_auc", "Dauc") + " de AUC " +
                M.c(f"[{mo['delta_auc_ic95_percentil'][0]:+.3f}, "
                    f"{mo['delta_auc_ic95_percentil'][1]:+.3f}]",
                    "balon_parado_v2 › modelo.delta_auc_ic95_percentil") +
                ". La portería queda libre en " +
                M.c(f"{lg['goal_open_medio']['corner']:.3f}", Fl + " › goal_open_medio.corner") +
                " de los remates de córner contra " +
                M.c(f"{lg['goal_open_medio']['juego_abierto']:.3f}",
                    Fl + " › goal_open_medio.juego_abierto") + " en juego abierto."),
        M.fig("fig7b", "Qué pesa en el xG de un remate",
              "Coeficientes estandarizados del modelo base, con IC 95%. A la izquierda "
              "del cero, menos xG.",
              [{"k": k, "b": mo["beta_base_estandarizado"][k],
                "ic": mo["beta_base_ic95"][k]} for k in ("dist_meta", "angulo", "cabeza")]),
        M.nulo("El América de Jardine no se separa de la liga en córners. A favor: " +
               M.c(f_pp(of["did"]), Fu + " › C1_of.did") + " " +
               M.c(f_ic(of["ic95"], f_pp), Fu + " › C1_of.ic95") + "; en contra: " +
               M.c(f_pp(de["did"]), Fu + " › C1_def.did") + " " +
               M.c(f_ic(de["ic95"], f_pp), Fu + " › C1_def.ic95") +
               ". No detectamos una diferencia mayor a " +
               M.c(f"{max(margen(of['ic95']), margen(de['ic95'])) * 100:.1f} pp",
                   Fu + " › C1_of/C1_def.ic95 (extremo)") + "."),
        M.fig("remates", "Dónde remata y dónde le rematan",
              "Remates tras córner por zona del área. Fuente: balon_parado_v2 › "
              "unidades › descriptivos.",
              {"of": u["descriptivos"]["mapa_remates_of"],
               "def": u["descriptivos"]["mapa_remates_def"]}),
    ]
    return B


def sec08(M: Modelo):
    M.need("h4", "met", "jug", "ctx")
    J = M.J
    eras = [(CLUB, FOCO), FUERA[0], (CLUB, "Fernando Ortiz"), FUERA[1]]
    filas = []
    lim = REGLAS["cont_inferior"][0]
    for club, coach in eras:
        h = unidad(J, "h4", club, coach)
        g = unidad(J, "met", club, coach)["global"]
        a = [v for v in unidad(J, "jug", club, coach)["A"].values() if not v["parcial"]]
        filas.append({
            "era": f"{ape(coach)} · {club}", "club": club, "coach": coach,
            "pos": h["rel_E_T_vs_liga"], "pos_ic": h["rel_E_T_vs_liga_ic95"],
            "ft": g["field_tilt"]["dif"], "ft_ic": g["field_tilt"]["ic95"],
            "xg": g["npxg_favor"]["dif"], "xg_ic": g["npxg_favor"]["ic95"],
            "cont": sum(v["percentil_continuidad"] <= lim for v in a), "cont_n": len(a)})
    ja, sl_, oa, om = filas
    exige(all(r["pos_ic"][0] > 0 and r["ft_ic"][0] > 0 for r in (ja, oa)),
          "§8: en el América los dos ya no comparten posesión larga y dominio territorial")
    exige(sl_["pos"] < 0 and sl_["ft"] < 0 and sl_["xg"] < 0,
          "§8: el perfil de Jardine en San Luis ya no se invierte en las tres métricas")
    exige(om["pos_ic"][0] > 0 and om["ft_ic"][0] <= 0,
          "§8: Ortiz en Monterrey ya no conserva la posesión sin el dominio territorial")
    k, n, lista = viajan_marcador(J["ctx"])
    exige(k < 6, "§8: la predicción de ADR-57 ahora se cumple; cambia la redacción")
    pj = J["ctx"]["predicciones"][-1]
    sl = filas[1]
    B = [
        M.nota("La tabla junta las cuatro eras. Las tres primeras columnas son mediciones "
               "contra la liga del mismo torneo, con intervalo (nivel B); la última es "
               "descriptiva (nivel C)."),
        M.fig("fig8", "El mismo técnico en otro club", "Toca una celda para ver el intervalo "
              "y la fuente.", filas),
        M.frase("C", "En el América, los dos técnicos muestran el mismo perfil: posesión "
                "larga y dominio territorial."),
        M.frase("C", "Fuera del América, el perfil de Jardine se invierte en las tres "
                "métricas (posesión " +
                M.c(f_pct(sl["pos"]), "did_h4_v1 › unidades[San Luis, Jardine] › rel_E_T_vs_liga") +
                ", field tilt " +
                M.c(f_pp(sl["ft"]), "metricas_v1 › unidades[San Luis, Jardine] › global.field_tilt.dif") +
                "). Ortiz conserva la posesión larga en Monterrey y pierde casi todo el "
                "dominio territorial."),
        M.frase("C", "Lo que viaja depende del técnico y de la métrica. El dominio "
                "territorial es compatible con que sea más del contexto América que de "
                "quien lo dirige. La comparación no separa plantel, presupuesto ni "
                "calendario, que cambian con el club; y con dos técnicos no hay regla."),
        M.frase("C", "Entre los técnicos con varios clubes fuera del América, " +
                M.c(f"{k} de {n}", "contexto_v1 › viaja_marcador_M1 (sin Jardine ni Ortiz)", "Viajan") +
                " mantienen el signo de su ajuste al marcador de un club a otro. "
                "La predicción preinscrita pedía al menos seis y no se cumplió.",
                nota_adenda="Conteo sin Jardine ni Ortiz, como en 06_DECISIONS."),
        M.fig("viajan", "¿Viaja el ajuste al marcador?",
              "Técnicos con eras en varios clubes (ADR-57), métrica M1.",
              [{"coach": c, "mismo": v} for c, v in lista]),
        M.nota("El JSON registra la predicción con los once técnicos, incluidos Jardine y "
               "Ortiz: " + M.c(f"{pj['valor'][0]} de {pj['valor'][1]}",
                               "contexto_v1 › predicciones[ADR-57, 1].valor") +
               ". Con cualquiera de los dos conteos la predicción falla."),
    ]
    return B


def sec09(M: Modelo):
    M.need("h4", "pres", "bp", "ctx", "jug")
    h4, pr = M.J["h4"], M.J["pres"]
    mk = marcador(M.J)
    ok = sum(p["cumple"] for p in mk)
    por_adr = {}
    for p in mk:
        a = por_adr.setdefault(p["adr"], [0, 0])
        a[0] += p["cumple"]
        a[1] += 1
    Fh, Fp = "did_h4_v1", "did_presion_v1"
    resumen = ", ".join(f"ADR-{a} {M.c(f'{v[0]}/{v[1]}', 'marcador › ADR-' + str(a))}"
                        for a, v in sorted(por_adr.items()))
    B = [
        M.frase("C", "Corregir la deriva cambia el veredicto. En duración de posesión, los "
                "pares que difieren pasan de " + M.c(str(h4["n_rechazados_crudo"]),
                                                     Fh + " › n_rechazados_crudo") +
                " a " + M.c(str(h4["n_rechazados_did"]), Fh + " › n_rechazados_did") + " y " +
                M.c(str(h4["n_cambian_signo_por_correccion"]),
                    Fh + " › n_cambian_signo_por_correccion") +
                " cambian de signo. En presión, de " +
                M.c(str(pr["n_rechaza_crudo"]), Fp + " › n_rechaza_crudo") + " a " +
                M.c(str(pr["n_rechaza_did"]), Fp + " › n_rechaza_did") + " contrastes, con " +
                M.c(str(pr["n_cambian_veredicto"]), Fp + " › n_cambian_veredicto") +
                " cambios de veredicto."),
        M.fig("fig9b", "Crudo contra corregido, en conteos", "", [
            {"k": "Pares que difieren en duración", "cru": h4["n_rechazados_crudo"],
             "did": h4["n_rechazados_did"], "de": h4["n_pares"]},
            {"k": "Contrastes de presión que difieren", "cru": pr["n_rechaza_crudo"],
             "did": pr["n_rechaza_did"], "de": pr["m_etapa1"]}]),
        M.frase("C", "Marcador de predicciones escritas antes de medir: " +
                M.c(f"{ok} de {len(mk)}", "marcador (predicciones de los JSON + ADR-53 recalculada)", "Marcador") +
                " se cumplieron (" + resumen + "). Los fallos se muestran en la figura."),
        M.fig("fig9", "Predicciones preinscritas", "Punto lleno: se cumplió. Aro: falló. "
              "Toca cada una para leerla.", mk),
        M.fig("bugs", "Anexo · errores silenciosos encontrados", "",
              {"falta": "catálogo de errores (02_STATE_OF_PLAY §8 o equivalente)"}),
    ]
    return B


def sec10(M: Modelo):
    return [
        M.frase("C", "Lo que el marco no captura:"),
        M.nota(LIMITES),
        M.frase("C", "La simulación de posesiones (componente 06, opcional) no se incluye: "
                "la cadena de Markov no reproduce la distribución de longitudes, y simular "
                "desde ella arrastraría ese sesgo (ADR-21)."),
        M.nota("Nada de este informe es causal. Describe cómo jugaron los equipos bajo "
               "cada técnico, contra la liga del mismo torneo; no mide rendimiento ni "
               "intención."),
    ]


SECCIONES = [
    ("s1", "01", "5.6", "Cómo leer este informe", sec01),
    ("s2", "02", "5.1 ofensiva", "El América de Jardine con el balón", sec02),
    ("s3", "03", "5.1 defensiva", "El América de Jardine sin el balón", sec03),
    ("s4", "04", "5.2 consistencia", "¿Se sostiene en el tiempo?", sec04),
    ("s5", "05", "5.2 variabilidad", "¿Ajusta al contexto?", sec05),
    ("s6", "06", "5.3", "El plantel", sec06),
    ("s7", "07", "5.4", "Balón parado", sec07),
    ("s8", "08", "diferenciador", "¿Qué es de Jardine y qué del América?", sec08),
    ("s9", "09", "credibilidad", "¿El método distingue de verdad?", sec09),
    ("s10", "10", "5.6", "Framework y límites", sec10),
]

DEF_MARKOV = (
    "<p><b>Posesión</b>: la cadena de acciones de un equipo desde que recupera el balón "
    "hasta que lo pierde, sale o remata. <b>Acción</b>: pase, conducción o remate. "
    "<b>Fase</b>: juego abierto, transición, reanudación o balón parado. "
    "<b>Estado</b>: zona × fase (20 × 4).</p>"
    "<p><b>Cadena</b>: cada acción mueve la posesión de un estado a otro con "
    "probabilidad <i>Q<sub>ij</sub></i>, o la termina en remate, gol o pérdida con "
    "probabilidad <i>R<sub>ik</sub></i>. Con la matriz fundamental "
    "<i>N = (I − Q)<sup>−1</sup></i>, la duración esperada es <i>E[T] = N·1</i> y la "
    "probabilidad de terminar en remate o gol es <i>B = N·R</i>.</p>"
    "<p><b>Comparación</b>: θ = (era − liga del mismo torneo). En pares del mismo club, "
    "diferencia en diferencias. Intervalos por bootstrap por partido; corrección de "
    "Benjamini–Hochberg al 5% dentro de cada familia declarada antes de medir.</p>")

LIMITES = (
    "La distribución de longitudes de posesión no es la de una cadena de Markov "
    "(tampoco en balón parado, ADR-55 P5). · Sin tiempo en segundos: transiciones y "
    "contragolpes solo por sustituto. · Sin datos posicionales 360: la organización "
    "defensiva se aproxima. · Hay competiciones fuera de los datos. · Las fronteras de "
    "cada era tienen un margen de ±1 partido. · Ninguna afirmación es causal.")


# ---------------------------------------------------------------------------
# ensamblado
# ---------------------------------------------------------------------------
def construye(J: dict, traza: dict) -> tuple[dict, Modelo]:
    M = Modelo(J)
    secs = []
    for sid, num, comp, tit, fn in SECCIONES:
        try:
            bloques = fn(M)
            secs.append({"id": sid, "num": num, "comp": comp, "tit": tit,
                         "bloques": bloques})
        except LecturaCambio as e:
            sys.exit(f"LECTURA PREINSCRITA ROTA en {sid}: {e}. Revisar ADR-59 antes de publicar.")
        except FaltaInsumo as e:
            nombre, cmd = FUENTES[e.clave]
            secs.append({"id": sid, "num": num, "comp": comp, "tit": tit,
                         "falta": {"archivo": nombre, "comando": cmd}})
    return {"secciones": secs, "traza": traza, "reglas": REGLAS}, M


def escribe_tex(M: Modelo, ruta: Path):
    """Las cifras con clave, como macros para la guía LaTeX: la guía tampoco
    teclea números. Ej.: \\cifraPosJ."""
    def tex(s):
        return (s.replace("\\", r"\textbackslash{}").replace("%", r"\%")
                .replace("−", "$-$").replace("&", r"\&").replace("_", r"\_")
                .replace("#", r"\#").replace("›", r"$\rightarrow$"))
    lin = ["% generado por 12_reporte_html.py — no editar a mano"]
    vistas = set()
    for c in M.cifras:
        if c["k"] and c["k"] not in vistas:
            vistas.add(c["k"])
            lin.append(f"\\newcommand{{\\cifra{c['k']}}}{{\\textbf{{{tex(c['t'])}}}}}"
                       f" % {tex(c['f'])}")
    ruta.write_text("\n".join(lin) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--parquet", default=str(RAIZ / PARQUET_AMERICA))
    ap.add_argument("--out", default="reporte.html")
    ap.add_argument("--modelo", default=None, help="vuelca el modelo a JSON (tests)")
    ap.add_argument("--tex", default=None, help="macros de cifras para la guía LaTeX")
    args = ap.parse_args()

    J, traza = recolecta(Path(args.reports), Path(args.parquet))
    datos, M = construye(J, traza)
    pagina = HTML.replace("__DATOS__", json.dumps(datos, ensure_ascii=False)
                          .replace("</", "<\\/"))

    malas = revisa(pagina)
    if malas:
        for frag, pat, motivo in malas[:20]:
            print(f"  PROHIBIDA ({motivo}): …{frag}…", file=sys.stderr)
        sys.exit(f"{len(malas)} frases prohibidas por ADR-59 §3. No se escribe nada.")

    salida = Path(args.out)
    salida.write_text(pagina, encoding="utf-8")
    if args.modelo:
        Path(args.modelo).write_text(json.dumps(
            {"datos": datos, "cifras": M.cifras}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    if args.tex:
        escribe_tex(M, Path(args.tex))
    if SIN_CLUB:
        print(f"AVISO: {len(SIN_CLUB)} entradas sin `club` descartadas: "
              + "; ".join(SIN_CLUB[:5]), file=sys.stderr)
    faltan = [s["id"] for s in datos["secciones"] if "falta" in s]
    print(f"escrito: {salida.resolve()}  ({salida.stat().st_size / 1024:.0f} KB)")
    print(f"cifras con fuente: {len(M.cifras)} · secciones sin insumo: {faltan or 'ninguna'}")
    print(f"commit: {traza['commit']['hash']}"
          + (" (con cambios sin commitear)" if traza["commit"]["sucio"] else ""))


HTML = r"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>El América de Jardine</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#06060a;
  /* Vidrio de CHROME (nav, tooltip, pildoras): translucido de verdad.
     Vidrio de CONTENIDO (tarjetas): mas opaco. Es la regla de iOS 26 --
     el vidrio es la capa de control, el contenido se queda solido y legible. */
  --card:rgba(255,255,255,.055); --card2:rgba(255,255,255,.032);
  --chrome:rgba(14,14,20,.62);
  --brd:rgba(255,255,255,.11); --brd2:rgba(255,255,255,.07);
  /* borde especular: linea clara arriba, sombra abajo. Es lo que hace que una
     superficie parezca vidrio y no un rectangulo gris. */
  --rim:inset 0 1px 0 rgba(255,255,255,.12),inset 0 -1px 0 rgba(0,0,0,.22);
  /* CONTRASTE. Los tres grises anteriores (98/5a) bajaban de 3:1 sobre el
     fondo y todas las notas del reporte estaban escritas con el mas oscuro. */
  --tx:#f5f5f7; --tx1:#f5f5f7; --tx2:#b9b9c4; --tx3:#95959f;
  --a1:#0a84ff; --a2:#64d2ff; --ro:#ff453a; --ok:#30d158; --am:#ffd60a;
  /* Pareja de comparacion, UNICA para todo el reporte: el foco lleva el color
     del club, el rival lleva plata neutra. Antes cada figura elegia el suyo y
     la seccion 5 pintaba al America de azul. */
  --foco:var(--a1); --riv:#c9cfda; --neg:#ff7a70;
  --ap:#38383c; --linea:#4a7d61;
  --r-lg:26px; --r-md:20px; --r-sm:14px;
  --muelle:cubic-bezier(.34,1.4,.64,1);
  --sans:-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',Roboto,
    'Helvetica Neue',sans-serif;
  --mono:ui-monospace,'SF Mono','JetBrains Mono',Menlo,'Cascadia Mono',monospace;
  --serif:'Iowan Old Style','Palatino Linotype',Palatino,Georgia,serif;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--tx);font-family:var(--sans);
 -webkit-font-smoothing:antialiased;overflow-x:hidden}
.wrap{max-width:1120px;margin:0 auto;padding:0 1.5rem}
#aura{position:fixed;inset:0;pointer-events:none;z-index:0;
 transition:background 1.1s cubic-bezier(.16,1,.3,1)}
.wrap,header,nav{position:relative;z-index:1}
svg{display:block;width:100%;height:auto}

/* ---------- tooltip global (sustituye a <title>, que tarda 1s) ---------- */
#tip{position:fixed;z-index:99;pointer-events:none;opacity:0;
 transform:translate(-50%,-118%);transition:opacity .13s;
 background:rgba(22,22,28,.94);border:1px solid var(--brd);
 border-radius:12px;padding:.55rem .8rem;font-size:.78rem;font-weight:400;
 line-height:1.45;max-width:280px;backdrop-filter:blur(24px);
 box-shadow:0 12px 40px rgba(0,0,0,.55)}
#tip b{display:block;font-size:.72rem;font-family:var(--mono);
 letter-spacing:.08em;text-transform:uppercase;color:var(--a2);
 margin-bottom:.2rem;font-weight:600}
#tip.on{opacity:1}
[data-tip]{cursor:help}

/* ---------- portada ---------- */
header{padding:6.5rem 0 1.6rem}
.kicker{display:inline-flex;align-items:center;gap:.6rem;font-size:.66rem;
 font-weight:700;letter-spacing:.24em;text-transform:uppercase;color:var(--a1);
 border:1px solid var(--brd);border-radius:999px;padding:.42rem 1rem;
 background:var(--card);backdrop-filter:blur(20px);margin-bottom:1.8rem;
 font-family:var(--mono)}
.dot{width:6px;height:6px;border-radius:50%;background:var(--a1);
 animation:latido 2.2s ease-in-out infinite}
@keyframes latido{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.8)}}
h1{font-size:clamp(2.8rem,8vw,6rem);font-weight:800;letter-spacing:-.058em;
 line-height:.92}
h1 em{font-family:var(--serif);font-style:italic;font-weight:400;
 letter-spacing:-.02em;background:linear-gradient(120deg,var(--a1),var(--a2));
 -webkit-background-clip:text;-webkit-text-fill-color:transparent}
header p{margin-top:1.5rem;font-size:1.22rem;font-weight:250;color:var(--tx2);
 line-height:1.5;max-width:34ch}

/* ---------- barra de control ---------- */
nav{position:sticky;top:0;z-index:40;background:rgba(6,6,10,.72);
 backdrop-filter:blur(34px) saturate(180%);
 -webkit-backdrop-filter:blur(34px) saturate(180%);
 border-bottom:1px solid var(--brd2);padding:.7rem 0;margin-top:2rem}
.navin{max-width:1120px;margin:0 auto;padding:0 1.5rem;display:flex;gap:.7rem;
 flex-wrap:wrap;align-items:center}
/* segmentado tipo iOS: la pastilla se desliza */
.seg{position:relative;display:flex;background:rgba(255,255,255,.06);
 border-radius:12px;padding:3px;gap:2px}
.seg .pill{position:absolute;top:3px;bottom:3px;border-radius:9px;
 background:rgba(255,255,255,.13);
 transition:left .34s cubic-bezier(.16,1,.3,1),width .34s cubic-bezier(.16,1,.3,1)}
.seg button{position:relative;z-index:1;background:none;border:none;
 color:var(--tx2);font-family:var(--sans);font-size:.83rem;font-weight:600;
 padding:.42rem .95rem;border-radius:9px;cursor:pointer;white-space:nowrap;
 transition:color .25s}
.seg button.on{color:var(--tx)}
select{appearance:none;background:var(--card);border:1px solid var(--brd);
 border-radius:12px;color:var(--tx);font-size:.88rem;font-weight:600;
 padding:.55rem 2.1rem .55rem .9rem;cursor:pointer;font-family:var(--sans);
 transition:border-color .2s;
 background-image:linear-gradient(45deg,transparent 50%,var(--tx2) 50%),
  linear-gradient(135deg,var(--tx2) 50%,transparent 50%);
 background-position:calc(100% - 17px) 55%,calc(100% - 12px) 55%;
 background-size:5px 5px,5px 5px;background-repeat:no-repeat}
select:hover,select:focus{outline:none;border-color:var(--a1)}
option{background:#111117;color:var(--tx)}
.swap{background:var(--card);border:1px solid var(--brd);border-radius:12px;
 color:var(--tx2);width:34px;height:34px;cursor:pointer;font-size:.95rem;
 transition:transform .3s cubic-bezier(.16,1,.3,1),color .2s,border-color .2s}
.swap:hover{color:var(--tx);border-color:var(--a1);transform:rotate(180deg)}

/* ---------- secciones ---------- */
section{padding:5rem 0 0}
.eyebrow{font-family:var(--mono);font-size:.66rem;font-weight:700;
 letter-spacing:.26em;text-transform:uppercase;color:var(--a1);margin-bottom:.9rem}
h2{font-size:clamp(1.9rem,3.6vw,2.9rem);font-weight:700;letter-spacing:-.04em;
 line-height:1.08;margin-bottom:.9rem}
.lead{font-size:1.06rem;font-weight:250;color:var(--tx2);line-height:1.6;
 max-width:56ch;margin-bottom:2rem}

.grid{display:grid;gap:1rem}
.g2{grid-template-columns:repeat(auto-fit,minmax(310px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(215px,1fr))}
.gm{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.duo{grid-template-columns:1.55fr 1fr;align-items:start}
@media(max-width:900px){.duo{grid-template-columns:1fr}}
.pega{position:sticky;top:4.8rem}
@media(max-width:900px){.pega{position:static}}

.card{background:var(--card);border:1px solid var(--brd);border-radius:var(--r-lg);
 padding:1.5rem;backdrop-filter:blur(26px) saturate(165%);
 transition:transform .32s cubic-bezier(.16,1,.3,1),border-color .32s}
.card.flat{background:var(--card2);border-color:var(--brd2)}
.card:hover{border-color:rgba(255,255,255,.17)}
.card.lift:hover{transform:translateY(-3px)}
.c-lab{font-family:var(--mono);font-size:.62rem;font-weight:600;
 letter-spacing:.17em;text-transform:uppercase;color:var(--tx2)}
.c-val{font-family:var(--mono);font-size:2.5rem;font-weight:700;
 letter-spacing:-.05em;margin-top:.45rem;line-height:1;
 font-variant-numeric:tabular-nums}
.c-pie{font-size:.83rem;font-weight:300;color:var(--tx2);margin-top:.4rem;
 line-height:1.45}

/* ---------- anillo tipo actividad ---------- */
.anillo{display:flex;flex-direction:column;align-items:center;gap:.15rem}
.anillo svg{max-width:180px;margin:0 auto}
.a-num{font-family:var(--mono);font-weight:700;letter-spacing:-.04em;
 font-variant-numeric:tabular-nums}
.a-tit{font-family:var(--mono);font-size:.6rem;font-weight:600;
 letter-spacing:.18em;text-transform:uppercase;color:var(--tx2);
 text-align:center;margin-top:.7rem}
.a-sub{font-size:.79rem;font-weight:300;color:var(--tx3);text-align:center;
 margin-top:.2rem}

/* ---------- etiqueta de veredicto ---------- */
.chipd{display:inline-flex;align-items:center;gap:.4rem;border-radius:999px;
 padding:.28rem .7rem;font-family:var(--mono);font-size:.72rem;font-weight:700;
 letter-spacing:.02em;margin-top:.75rem;font-variant-numeric:tabular-nums}
.chipd.ok{background:rgba(48,209,88,.13);color:var(--ok);
 border:1px solid rgba(48,209,88,.28)}
.chipd.no{background:rgba(255,255,255,.05);color:var(--tx2);
 border:1px solid var(--brd2)}
.chipd.dn{background:rgba(255,69,58,.12);color:#ff8a80;
 border:1px solid rgba(255,69,58,.26)}

.chips{display:flex;flex-wrap:wrap;gap:.5rem}
.chip{font-size:.82rem;font-weight:500;background:var(--card);
 border:1px solid var(--brd);border-radius:999px;padding:.42rem 1rem;
 backdrop-filter:blur(16px);transition:background .2s,transform .2s}
.chip:hover{background:rgba(255,255,255,.09);transform:translateY(-1px)}
.chip span{color:var(--tx2);font-weight:300}

.eq{font-family:var(--mono);font-size:.62rem;font-weight:600;letter-spacing:.17em;
 text-transform:uppercase;color:var(--tx2);margin-bottom:.6rem}
.pie{font-size:.89rem;font-weight:250;color:var(--tx2);line-height:1.7;
 max-width:62ch;margin-top:1rem}
.aviso{background:rgba(255,214,10,.07);border:1px solid rgba(255,214,10,.22);
 border-radius:var(--r-sm);padding:.9rem 1.2rem;margin-top:1.2rem;font-size:.87rem;
 color:#ffe27a;font-weight:300;line-height:1.55}
.vacio{background:var(--card2);border:1px dashed var(--brd);border-radius:var(--r-md);
 padding:1.5rem;color:var(--tx2);font-weight:300;font-size:.93rem;line-height:1.6}
.vacio code{display:block;margin-top:.8rem;background:rgba(0,0,0,.45);
 border-radius:10px;padding:.85rem 1rem;color:var(--a2);font-family:var(--mono);
 font-size:.76rem;overflow-x:auto;white-space:pre}

/* ---------- lista de zonas / jugadores, tipo ajustes de iOS ---------- */
.lista{display:flex;flex-direction:column}
.item{display:flex;align-items:center;gap:.85rem;padding:.72rem .25rem;
 border-bottom:1px solid var(--brd2);cursor:pointer;
 transition:background .2s;border-radius:10px}
.item:last-child{border-bottom:none}
.item:hover,.item.on{background:rgba(255,255,255,.055)}
.it-tx{flex:1;min-width:0}
.it-nom{font-size:.87rem;font-weight:600;letter-spacing:-.01em;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.it-sub{font-size:.72rem;font-weight:300;color:var(--tx3);margin-top:.12rem}
.it-bar{width:104px;height:7px;border-radius:4px;background:rgba(255,255,255,.07);
 overflow:hidden;flex-shrink:0;display:flex}
.it-bar i{display:block;height:100%;border-radius:4px;width:0;
 transition:width .9s cubic-bezier(.16,1,.3,1)}
.it-val{font-family:var(--mono);font-size:.78rem;font-weight:700;
 min-width:52px;text-align:right;font-variant-numeric:tabular-nums;
 flex-shrink:0}

/* ---------- cuadro de referencia de la nube de puntos ---------- */
.ejex{margin-bottom:.9rem;font-size:.81rem;font-weight:300;color:var(--tx2);
 line-height:1.5}
.ejex b{display:block;font-size:.83rem;font-weight:700;color:var(--tx);
 margin-bottom:.15rem;letter-spacing:-.01em}
.refgrid{display:grid;grid-template-columns:1fr;gap:1rem}
@media(min-width:1100px){.refgrid{grid-template-columns:1fr 1fr}}
.quad{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
.qc{background:rgba(255,255,255,.035);border:1px solid var(--brd2);
 border-radius:var(--r-sm);padding:.8rem .9rem}
.q-pos{font-family:var(--mono);font-size:.58rem;font-weight:600;
 letter-spacing:.15em;text-transform:uppercase;color:var(--a1);opacity:.85}
.q-tit{font-size:.85rem;font-weight:700;letter-spacing:-.01em;margin:.25rem 0 .3rem}
.q-tx{font-size:.75rem;font-weight:300;color:var(--tx2);line-height:1.45}
@media(max-width:520px){.quad{grid-template-columns:1fr}}

.halo-flood{flood-color:var(--a1);flood-opacity:.5}
.celda{transition:opacity .3s ease}
.celda:hover{opacity:.85;cursor:help}
.celda.dim{opacity:.22}
.pt{cursor:pointer;transition:opacity .25s}

details{background:var(--card2);border:1px solid var(--brd2);border-radius:var(--r-md);
 padding:1.2rem 1.5rem;margin:5rem 0 7rem;backdrop-filter:blur(20px)}
summary{cursor:pointer;font-weight:600;color:var(--tx2);font-size:.93rem;
 list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"+ ";color:var(--a1)}
details[open] summary::before{content:"- "}
details p{margin-top:1rem;font-size:.89rem;font-weight:300;color:var(--tx2);
 line-height:1.7}
details p b{color:var(--tx);font-weight:600}

.rev{opacity:0;transform:translateY(26px);
 transition:opacity .75s cubic-bezier(.16,1,.3,1),
   transform .75s cubic-bezier(.16,1,.3,1)}
.rev.on{opacity:1;transform:none}
@media(prefers-reduced-motion:reduce){
 .rev{opacity:1;transform:none;transition:none}
 *{animation-duration:.001s!important}
}

/* ======================================================================
   AJUSTES DE LEGIBILIDAD Y COMPONENTES NUEVOS
   Van al final a proposito: son reglas de la misma especificidad que las de
   arriba, asi que ganan por orden y el bloque original queda intacto y
   comparable.
   ====================================================================== */

/* ---------- tipografia: todo lo secundario sube un escalon ---------- */
/* Regla: nada por debajo de .8rem lleva texto que haga falta leer. Las
   etiquetas en versalitas pueden ser menores porque son de una palabra. */
.c-lab,.eq{font-size:.72rem;letter-spacing:.14em;color:var(--tx2)}
.c-pie{font-size:.9rem;font-weight:400;color:var(--tx2);line-height:1.55}
.it-nom{font-size:.94rem}
.it-sub{font-size:.8rem;color:var(--tx2);font-weight:400}
.it-val{font-size:.88rem;min-width:58px}
.a-tit{font-size:.68rem}
.a-sub{font-size:.86rem;color:var(--tx2);font-weight:400}
.q-tx{font-size:.83rem;color:var(--tx2);font-weight:400}
.q-tit{font-size:.92rem}
.q-pos{font-size:.64rem;opacity:1}
.pie{font-size:.94rem;font-weight:400;color:var(--tx2)}
.lead{font-size:1.12rem;font-weight:300;color:var(--tx2)}
.ejex{font-size:.88rem;font-weight:400;color:var(--tx2)}
#tip{font-size:.86rem;max-width:320px;padding:.7rem .95rem}
#tip b{font-size:.68rem;color:var(--a2)}
.vacio{font-size:.98rem;font-weight:400}
.vacio code{font-size:.82rem}
details p{font-size:.95rem;font-weight:400;color:var(--tx2)}
summary{font-size:1rem;color:var(--tx)}

/* `.nota` sustituye a los diez bloques de estilo en linea que repetian
   `font-size:.76rem;color:var(--tx3)`. Un solo sitio donde ajustar el
   tamano de toda la letra pequena del reporte. */
.nota{font-size:.88rem;font-weight:400;color:var(--tx2);line-height:1.65;
 margin-top:.8rem;max-width:66ch}
.nota b{color:var(--tx1);font-weight:600}
.nota+.nota{margin-top:.5rem}

/* ---------- vidrio ---------- */
.card{box-shadow:var(--rim);
 background:linear-gradient(rgba(255,255,255,.028),rgba(255,255,255,0)),var(--card)}
nav{background:var(--chrome)}
.seg,.chip,select,.swap{box-shadow:var(--rim)}
.seg button{font-size:.88rem}
.seg .pill{box-shadow:0 2px 10px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.18)}
/* Si el sistema pide menos transparencia, el vidrio se apaga entero: el
   desenfoque es decoracion, la legibilidad no. */
@media(prefers-reduced-transparency:reduce){
 .card,nav,#tip,.chip{backdrop-filter:none;-webkit-backdrop-filter:none;
  background:#14141b}
}
:focus-visible{outline:2px solid var(--a2);outline-offset:3px;border-radius:8px}

/* ---------- rejilla de comparacion: DOS COLUMNAS IGUALES ---------- */
/* `.duo` es 1.55fr/1fr y esta pensada para figura + barra lateral. Al usarla
   para dos canchas del mismo tipo, la de la derecha salia un 36% mas chica y
   la comparacion visual quedaba falseada: la misma mancha parecia menor. */
.par{grid-template-columns:1fr 1fr;align-items:start;gap:1.1rem}
@media(max-width:820px){.par{grid-template-columns:1fr}}
.panel{display:flex;flex-direction:column;gap:.55rem}
.mapcap{display:flex;align-items:center;gap:.5rem;font-size:.85rem;
 font-weight:600;letter-spacing:-.01em;color:var(--tx)}
.mapcap i{width:10px;height:10px;border-radius:3px;flex-shrink:0;
 box-shadow:inset 0 0 0 1px rgba(255,255,255,.35)}
.mapcap s{text-decoration:none;font-weight:400;color:var(--tx2);font-size:.8rem}

/* ---------- leyenda de color ---------- */
.leyenda{display:flex;flex-wrap:wrap;gap:.5rem .95rem;align-items:center;
 margin-top:.85rem;font-size:.83rem;color:var(--tx2);font-weight:400}
.leg{display:inline-flex;align-items:center;gap:.42rem;white-space:nowrap}
.leg i{width:11px;height:11px;border-radius:3.5px;display:inline-block;
 box-shadow:inset 0 0 0 1px rgba(255,255,255,.3)}
.rampa{display:inline-flex;align-items:center;gap:.45rem}
.rampa u{text-decoration:none;width:76px;height:11px;border-radius:4px;
 display:inline-block;box-shadow:inset 0 0 0 1px rgba(255,255,255,.14)}

/* ---------- guia de lectura ---------- */
.guia{background:var(--card2);border:1px solid var(--brd);
 border-radius:var(--r-lg);padding:1.3rem 1.6rem;margin:0;
 backdrop-filter:blur(20px);box-shadow:var(--rim)}
.guia summary{font-weight:700;color:var(--tx);letter-spacing:-.01em}
.guia[open] summary{margin-bottom:1.1rem}
.guia .paso{display:flex;gap:.9rem;padding:.8rem 0;
 border-top:1px solid var(--brd2)}
.guia .paso:first-of-type{border-top:none}
.num{flex-shrink:0;width:26px;height:26px;border-radius:9px;display:grid;
 place-items:center;background:var(--a1);color:#0b0b0e;font-family:var(--mono);
 font-size:.76rem;font-weight:700}
.paso h4{font-size:.95rem;font-weight:700;letter-spacing:-.01em;
 margin-bottom:.22rem}
.paso p{font-size:.89rem;font-weight:400;color:var(--tx2);line-height:1.6;
 margin:0;max-width:68ch}

/* ---------- termino con definicion ---------- */
.term{border-bottom:1px dashed rgba(255,255,255,.35);cursor:help;
 color:var(--tx1);font-weight:500}

/* ---------- lectura en una frase, arriba de cada figura ---------- */
.titular{font-size:1.06rem;font-weight:500;line-height:1.55;color:var(--tx);
 letter-spacing:-.012em;margin:.2rem 0 1rem;max-width:62ch}
.titular b{color:var(--a1);font-weight:700}
.titular .gris{color:var(--tx2);font-weight:400}

/* ---------- boton de ayuda en la barra ---------- */
.ayuda{background:var(--card);border:1px solid var(--brd);border-radius:12px;
 color:var(--tx2);height:34px;padding:0 .85rem;cursor:pointer;font-size:.83rem;
 font-weight:600;font-family:var(--sans);box-shadow:var(--rim);
 transition:color .2s,border-color .2s}
.ayuda:hover,.ayuda.on{color:var(--tx);border-color:var(--a1)}
.navlab{font-size:.78rem;font-weight:600;color:var(--tx3);
 letter-spacing:.02em;margin-left:.25rem}

/* ---------- dos canchas lado a lado ---------- */
.duocampo{display:grid;grid-template-columns:1fr 1fr;gap:1.1rem;align-items:start}
@media(max-width:900px){.duocampo{grid-template-columns:1fr}}
.campo-tit{display:flex;align-items:center;gap:.5rem;font-size:.9rem;
 font-weight:700;letter-spacing:-.01em;margin-bottom:.5rem;color:var(--tx)}
.campo-tit i{width:11px;height:11px;border-radius:3.5px;flex-shrink:0;
 box-shadow:inset 0 0 0 1px rgba(255,255,255,.35)}
.campo-tit s{text-decoration:none;font-weight:400;color:var(--tx3);
 font-size:.79rem;margin-left:auto;font-family:var(--mono)}

/* ---------- fichas de la secuencia ---------- */
.tira{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center;margin-top:.9rem;
 min-height:34px}
.fx{display:inline-flex;align-items:center;gap:.3rem;padding:.28rem .6rem;
 border-radius:10px;background:var(--card2);border:1px solid var(--brd2);
 font-size:.78rem;font-weight:600;color:var(--tx2);white-space:nowrap;
 animation:pop .22s var(--muelle)}
.fx.on{background:color-mix(in srgb,var(--a1) 22%,transparent);
 border-color:var(--a1);color:var(--tx)}
.fx.fin{background:var(--a1);color:#0b0b0e;border-color:transparent;
 font-family:var(--mono);letter-spacing:.06em}
.fx.fin.mal{background:var(--neg)}
.flecha{color:var(--tx3);font-size:.7rem}
@keyframes pop{from{opacity:0;transform:translateY(4px) scale(.9)}
 to{opacity:1;transform:none}}

/* ---------- sección interactiva ---------- */
.sim{display:grid;grid-template-columns:1.45fr 1fr;gap:1.4rem;align-items:start}
@media(max-width:860px){.sim{grid-template-columns:1fr}}
/* Cifras grandes SIN caja: el contraste guia el ojo en vez de competir con la
   cancha. Las cajas con borde de la version anterior pesaban tanto como la
   figura principal. */
.cifra{margin-bottom:1.15rem}
.cifra u{text-decoration:none;display:block;font-family:var(--mono);
 font-size:.68rem;letter-spacing:.16em;color:var(--tx3);margin-bottom:.1rem}
.cifra b{display:block;font-family:var(--mono);font-size:2.6rem;font-weight:700;
 letter-spacing:-.04em;line-height:1;color:var(--tx)}
.cifra b.sm{font-size:1.7rem}
.cifra i{font-style:normal;display:block;font-size:.84rem;color:var(--tx2);
 margin-top:.28rem;line-height:1.45}
.celda-cl{cursor:pointer}
.celda-cl:hover rect{stroke-opacity:.85!important}
.modo{display:inline-flex;background:var(--card2);border:1px solid var(--brd);
 border-radius:12px;padding:3px;gap:2px;margin-bottom:.9rem}
.modo button{background:none;border:none;color:var(--tx2);height:30px;
 padding:0 .85rem;border-radius:9px;cursor:pointer;font-size:.83rem;
 font-weight:600;font-family:var(--sans)}
.modo button.on{background:var(--a1);color:#0b0b0e}
.desg{margin-top:.9rem}
.desg .fila{display:flex;align-items:center;gap:.6rem;margin-bottom:.42rem;
 font-size:.86rem}
.desg .fila span:first-child{min-width:112px;color:var(--tx2)}
.desg .bar{flex:1;height:8px;background:var(--card2);border-radius:4px;
 overflow:hidden}
.desg .bar i{display:block;height:100%;border-radius:4px}
.desg .fila b{font-family:var(--mono);font-size:.86rem;min-width:46px;
 text-align:right}
.btns{display:flex;gap:.55rem;flex-wrap:wrap;margin:.9rem 0}
.btn{background:var(--card);border:1px solid var(--brd);border-radius:12px;
 color:var(--tx);height:38px;padding:0 1rem;cursor:pointer;font-size:.88rem;
 font-weight:600;font-family:var(--sans);box-shadow:var(--rim);
 transition:border-color .2s,transform .1s}
.btn:hover{border-color:var(--a1)}
.btn:active{transform:scale(.97)}
.btn.pri{background:var(--a1);color:#0b0b0e;border-color:transparent}
.btn:disabled{opacity:.45;cursor:default}
.marc{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem;margin-top:.9rem}
.marc>div{background:var(--card2);border:1px solid var(--brd2);border-radius:14px;
 padding:.75rem .9rem}
.marc b{display:block;font-family:var(--mono);font-size:1.35rem;font-weight:700;
 letter-spacing:-.02em;line-height:1.1}
.marc s{text-decoration:none;display:block;font-size:.74rem;color:var(--tx3);
 font-family:var(--mono);letter-spacing:.1em;margin-bottom:.15rem}
.marc i{font-style:normal;font-size:.76rem;color:var(--tx2)}
.bola{transition:cx .18s linear,cy .18s linear}
.regla{font-size:.9rem;color:var(--tx2);line-height:1.6;margin-top:.8rem;
 max-width:64ch}
.regla b{color:var(--tx1)}

/* ---------- tooltip fijado con el dedo ---------- */
/* En movil no hay `mouseover`: sin esto, todo el detalle de una casilla queda
   inalcanzable en el telefono. */
#tip.fijo{pointer-events:auto}
.celda,.pt,[data-tip]{-webkit-tap-highlight-color:transparent}

/* ======================================================================
   H7 · ADR-59. Todo en un solo tono. Los tokens de color de arriba se
   reasignan aquí; ninguna figura escribe un color a mano. La distinción
   foco/comparación se hace por luminosidad y por relleno (lleno contra aro),
   no por matiz.
   ====================================================================== */
:root{
  --a1:#f2f2f4; --a2:#c9c9cf; --ro:#8e8e96; --ok:#f2f2f4; --am:#c9c9cf;
  --foco:var(--a1); --riv:#8e8e96; --neg:#5d5d64;
  --ap:#2a2a2f; --linea:#56565d;
  --cesped1:#1b1b20; --cesped2:#111114;
  --mono-bg:rgba(255,255,255,.06);
}
.aviso{background:var(--mono-bg);border-color:var(--brd);color:var(--tx2)}
.chipd.ok{background:rgba(255,255,255,.12);color:var(--tx);border-color:var(--brd)}
.chipd.dn{background:transparent;color:var(--tx2);border:1px dashed var(--brd)}
#tip b{color:var(--tx2)}
.dot{background:var(--tx2)}
h1 em{background:linear-gradient(120deg,#fff,#9a9aa2);-webkit-background-clip:text}

/* barra de secciones: el segmentado de iOS, ahora como índice */
.navin{flex-wrap:nowrap}
#segSec{overflow-x:auto;scrollbar-width:none;max-width:100%}
#segSec::-webkit-scrollbar{display:none}
#segSec button{font-family:var(--mono);padding:.42rem .7rem}
.navtit{font-size:.83rem;font-weight:600;color:var(--tx2);white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis;min-width:0}
@media(max-width:700px){.navtit{display:none}}

/* trazabilidad */
.traza{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1.6rem}
.traza .chip{font-family:var(--mono);font-size:.74rem}
.traza .chip.falta{border-style:dashed;color:var(--tx2)}

/* frases con nivel */
.fr{font-size:1.04rem;line-height:1.62;color:var(--tx);max-width:66ch;
 margin:.9rem 0;display:flex;gap:.7rem;align-items:baseline}
.fr .tx{flex:1;min-width:0}
.fr b{font-weight:650}
.nv{flex-shrink:0;display:inline-grid;place-items:center;min-width:28px;height:22px;
 padding:0 .4rem;border-radius:7px;font-family:var(--mono);font-size:.74rem;
 font-weight:700;letter-spacing:.04em;position:relative;top:-1px}
.nv-A{background:var(--a1);color:#0b0b0e}
.nv-B{border:1.5px solid var(--a1);color:var(--a1)}
.nv-C{border:1.5px dashed var(--tx3);color:var(--tx2)}
.fr.nulo .nv::after{content:"· nulo";margin-left:.3rem;font-weight:500}
.fr.nulo .nv{display:inline-flex;align-items:center;white-space:nowrap}
.fr.nulo .tx{color:var(--tx2)}
.adenda{display:inline-block;margin-left:.4rem;font-family:var(--mono);font-size:.7rem;
 color:var(--tx2);border:1px dashed var(--brd);border-radius:6px;padding:0 .35rem;
 vertical-align:1px}
.cf{font-family:var(--mono);font-variant-numeric:tabular-nums;font-weight:600;
 font-size:.95em;border-bottom:1px dotted rgba(255,255,255,.35);white-space:nowrap}

/* figuras */
.fig{margin:1.4rem 0 1.8rem}
.fig .card{padding:1.4rem}
.fig-tit{font-size:1.02rem;font-weight:700;letter-spacing:-.015em;margin-bottom:.25rem}
.fig-top{display:flex;align-items:center;justify-content:space-between;gap:.8rem;
 flex-wrap:wrap;margin-bottom:.8rem}
.fig .seg{display:inline-flex;margin-bottom:.8rem;max-width:100%;overflow-x:auto}
.fig .seg button{font-size:.8rem;padding:.36rem .8rem}
.g2f{grid-template-columns:repeat(auto-fit,minmax(360px,1fr))}
@media(max-width:520px){.g2f{grid-template-columns:1fr}}
.lienzo{min-height:40px;overflow-x:auto}
@media(max-width:700px){.lienzo svg[data-bosque],.lienzo svg[data-linea]{min-width:620px}
 .g2f .lienzo svg[data-bosque],.g2f svg[data-bosque]{min-width:440px}
 .g2f .card{overflow-x:auto}}

table.t5{width:100%;border-collapse:collapse;font-size:.86rem}
.t5 th{font-family:var(--mono);font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;
 color:var(--tx2);font-weight:600;text-align:left;padding:.5rem .6rem;
 border-bottom:1px solid var(--brd)}
.t5 td{padding:.5rem .6rem;border-bottom:1px solid var(--brd2);color:var(--tx)}
.t5 td.n{font-family:var(--mono);text-align:right;font-variant-numeric:tabular-nums}
.t5 tr:hover td{background:rgba(255,255,255,.035)}
.tabla-scroll{overflow-x:auto}
.celdaic{display:flex;flex-direction:column;gap:.2rem;cursor:help}
.celdaic b{font-family:var(--mono);font-size:.95rem}

.puntos{display:flex;flex-direction:column;gap:.9rem}
.grupo-adr{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap}
.grupo-adr u{text-decoration:none;font-family:var(--mono);font-size:.78rem;
 color:var(--tx2);min-width:74px}
.pto{width:22px;height:22px;border-radius:50%;border:2px solid var(--a1);cursor:help}
.pto.si{background:var(--a1)}
.pto.no{background:transparent;border-style:solid;border-color:var(--tx3)}
.marcador-total{font-family:var(--mono);font-size:2.6rem;font-weight:700;
 letter-spacing:-.04em;line-height:1}

.esquema{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}
@media(max-width:760px){.esquema{grid-template-columns:1fr}}
.esquema .card{padding:1.1rem}
.esquema h4{font-size:.95rem;margin:.6rem 0 .2rem}
.esquema p{font-size:.86rem;color:var(--tx2);line-height:1.5}

.plegable{margin:1.2rem 0 0;padding:1rem 1.3rem}
.plegable p{max-width:70ch}
section{scroll-margin-top:4.5rem}
footer{padding:4rem 0 6rem;color:var(--tx2);font-size:.88rem}
</style></head><body>
<div id="aura"></div>
<div id="tip"></div>

<header class="wrap">
  <div class="kicker"><span class="dot"></span><span>Liga MX · fase regular</span></div>
  <h1>El América<br><em>de Jardine</em></h1>
  <p>Cómo jugó un equipo bajo un entrenador, y qué de eso viaja con él a otro club.</p>
  <div class="traza" id="traza"></div>
</header>

<nav><div class="navin">
  <div class="seg" id="segSec"><div class="pill"></div></div>
  <span class="navtit" id="navtit"></span>
  <button class="ayuda" id="btnGuia" style="margin-left:auto">¿Cómo se lee?</button>
</div></nav>

<div class="wrap">
  <details class="guia" id="guia" open style="margin-top:2.4rem"><summary>Empieza por aquí: los tres niveles</summary>
  <div class="paso"><div class="num">A</div><div>
   <h4>Probado</h4>
   <p>Un contraste escrito antes de medir, con intervalo por remuestreo, que sigue en pie
   después de corregir por haber hecho muchas comparaciones. Se dice «difiere» y va con su q.</p></div></div>
  <div class="paso"><div class="num">B</div><div>
   <h4>Medido</h4>
   <p>Una diferencia contra la liga del mismo torneo, con su intervalo, fuera de una
   familia de contrastes. Se dice «por encima» o «por debajo de la liga».</p></div></div>
  <div class="paso"><div class="num">C</div><div>
   <h4>Descriptivo</h4>
   <p>Percentiles, perfiles y comparaciones entre clubes. Sin intervalo y sin lenguaje de hallazgo.</p></div></div>
  <div class="paso"><div class="num">·</div><div>
   <h4>Un nulo no es «son iguales»</h4>
   <p>Cuando no detectamos una diferencia, decimos el tamaño máximo que los datos permiten
   descartar: el extremo del intervalo más lejano al cero.</p></div></div>
  <div class="paso"><div class="num">↗</div><div>
   <h4>Toca cualquier cifra</h4>
   <p>Cada número subrayado muestra de qué archivo y de qué campo sale. Las figuras
   responden al cursor y al dedo.</p></div></div>
  </details>
  <main id="informe"></main>
  <footer id="pie"></footer>
</div>

<script>
const D=__DATOS__;
const $=i=>document.getElementById(i);
const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");
const NX=5,NY=4,L=120,A=80,cw=L/NX,ch=A/NY,W_MAPA=470;
const C_FOCO="var(--a1)",C_RIV="var(--riv)",C_NEG="var(--neg)";
const TERCIO=["propio","propio","medio","rival","rival"];
const FRANJA=["banda izquierda","centro-izquierda","centro-derecha","banda derecha"];
const NIVEL={
 A:"<b>A · probado</b>Contraste preinscrito, intervalo por bootstrap y corrección BH dentro de su familia.",
 B:"<b>B · medido</b>Diferencia contra la liga del mismo torneo, con intervalo; sin familia.",
 C:"<b>C · descriptivo</b>Percentiles, perfiles o comparaciones sin intervalo."};
const ADENDA=m=>`<b>adenda 1 de ADR-59</b>${esc(m)}`;
const fmtS=(v,d)=>{const r=(+v).toFixed(d);if(+r===0)return (0).toFixed(d);return (v>0?"+":"")+r.replace("-","−");};
const pct=(v,d=1)=>fmtS(v*100,d)+"%";
const ppt=(v,d=1)=>fmtS(v*100,d)+" pp";

/* ================= tooltip (hover y toque) ================= */
const tip=$("tip");
document.addEventListener("mouseover",e=>{
 const t=e.target.closest("[data-tip]");
 if(!t)return;tip.innerHTML=t.dataset.tip;tip.classList.add("on");});
document.addEventListener("mouseout",e=>{
 if(e.target.closest("[data-tip]")&&!tip.classList.contains("fijo"))tip.classList.remove("on");});
document.addEventListener("mousemove",e=>{
 if(tip.classList.contains("fijo"))return;
 tip.style.left=e.clientX+"px";tip.style.top=e.clientY+"px";});
document.addEventListener("click",e=>{
 const t=e.target.closest("[data-tip]");
 if(!t){tip.classList.remove("on","fijo");return;}
 tip.innerHTML=t.dataset.tip;tip.classList.add("on","fijo");
 const r=t.getBoundingClientRect();
 tip.style.left=(r.left+r.width/2)+"px";tip.style.top=(r.top+r.height/2)+"px";});

/* ================= piezas conservadas ================= */
const SW=(c,t,hueco)=>`<span class="leg"><i style="background:${hueco?"transparent":c};${hueco?`box-shadow:inset 0 0 0 2px ${c}`:""}"></i>${t}</span>`;
const leyenda=(...xs)=>`<div class="leyenda">${xs.filter(Boolean).join("")}</div>`;
const rampa=(c,lo,hi)=>`<span class="rampa">${lo}<u style="background:${c};
 background:linear-gradient(90deg,color-mix(in srgb,${c} 12%,transparent),${c})"></u>${hi}</span>`;
function sube(el,to,dec){
 if(typeof requestAnimationFrame!=="function"){el.textContent=(+to).toFixed(dec);return;}
 const t0=performance.now(),dur=780;
 const paso=t=>{const p=Math.min((t-t0)/dur,1),e=1-Math.pow(1-p,3);
  el.textContent=(to*e).toFixed(dec);if(p<1)requestAnimationFrame(paso);};
 requestAnimationFrame(paso);
}
function animaNumeros(raiz){
 raiz.querySelectorAll("[data-num]").forEach(el=>sube(el,+el.dataset.num,+el.dataset.dec));
 raiz.querySelectorAll(".it-bar i").forEach(b=>{b.style.width=b.dataset.w+"%";});
}
/* restos mayores: los porcentajes de las 20 casillas suman 100 exacto */
function enteros100(vals){
 const cr=vals.map(v=>100*v),base=cr.map(x=>Math.floor(x));
 const falta=100-base.reduce((a,b)=>a+b,0);
 const orden=cr.map((x,i)=>[x-base[i],i]).sort((a,b)=>b[0]-a[0]);
 for(let k=0;k<Math.max(0,falta);k++)base[orden[k%orden.length][1]]++;
 return base;
}
function pitch(inner,w=W_MAPA){
 const h=w*A/L,s=w/L;
 const ln='stroke="var(--linea)" stroke-width="1.2" fill="none" opacity=".9"';
 let g=`<svg viewBox="0 0 ${w} ${h+34}" data-cancha="1">
  <defs><linearGradient id="cs" x1="0" y1="0" x2="0" y2="1">
   <stop offset="0%" stop-color="var(--cesped1)"/><stop offset="100%" stop-color="var(--cesped2)"/>
  </linearGradient></defs>
  <rect width="${w}" height="${h}" rx="14" fill="url(#cs)"/>`;
 for(let k=0;k<10;k+=2)g+=`<rect x="${k*w/10}" width="${w/10}" height="${h}" fill="#fff" opacity=".018"/>`;
 g+=`<rect x="${2*s}" y="${2*s}" width="${w-4*s}" height="${h-4*s}" rx="4" ${ln}/>
  <line x1="${w/2}" y1="${2*s}" x2="${w/2}" y2="${h-2*s}" ${ln}/>
  <circle cx="${w/2}" cy="${h/2}" r="${9.15*s}" ${ln}/>
  <rect x="${2*s}" y="${(A/2-20.15)*s}" width="${14.5*s}" height="${40.3*s}" ${ln}/>
  <rect x="${w-16.5*s}" y="${(A/2-20.15)*s}" width="${14.5*s}" height="${40.3*s}" ${ln}/>`;
 g+=inner(s,w,h);
 g+=`<line x1="${w*.44}" y1="${h+15}" x2="${w*.56}" y2="${h+15}" stroke="var(--tx2)" stroke-width="1.3"/>
  <path d="M${w*.56} ${h+15} l-5.5 -3.6 v7.2 z" fill="var(--tx2)"/>
  <text x="4" y="${h+19}" fill="var(--tx3)" font-size="11">portería propia</text>
  <text x="${w-4}" y="${h+19}" fill="var(--tx3)" font-size="11" text-anchor="end">portería rival</text>
  <text x="${w/2}" y="${h+30}" fill="var(--tx2)" font-size="10.5" text-anchor="middle"
   font-family="var(--mono)" letter-spacing="1.5">ATAQUE</text>`;
 return g+`</svg>`;
}
/* vmax compartido cuando dos mapas se comparan (15 §4.3) */
function mapaSVG(m,c,tag,vmax){
 const plano=[];for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++)plano.push(m[ix][iy]);
 const tot=plano.reduce((a,b)=>a+b,0)||1,ent=enteros100(plano.map(v=>v/tot));
 return pitch((s)=>{
  const vm=vmax||Math.max(...plano,1e-9);let g="";
  for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++){
   const v=Math.min(1,m[ix][iy]/vm),x=ix*cw*s,y=iy*ch*s,p=ent[ix*NY+iy];
   const tt=`<b>${esc(FRANJA[iy])}, tercio ${esc(TERCIO[ix])}</b>${(m[ix][iy]/tot*100).toFixed(1)}% ${esc(tag||"")}`;
   g+=`<g class="celda" data-tip="${tt}"><rect x="${x+2.5}" y="${y+2.5}" width="${cw*s-5}" height="${ch*s-5}" rx="8"
    fill="${c}" fill-opacity="${(.06+.8*v).toFixed(2)}" stroke="#fff"
    stroke-opacity="${(.14+.32*v).toFixed(2)}" stroke-width="1.2"/>
    <text x="${x+cw*s/2}" y="${y+ch*s/2+4.5}" fill="${v>.55?"#0b0b0e":"#fff"}" font-size="12.5"
    font-weight="700" text-anchor="middle" pointer-events="none" font-family="var(--mono)"
    class="pctz">${p}%</text></g>`;
  }
  return g;});
}
function anillo(v,tit,sub,dec=2,marca){
 const R=54,ini=-.4,fin=.4,C=2*Math.PI*R,largo=C*(fin-ini);
 const arco=t=>{const a=(ini+(fin-ini)*Math.max(0,Math.min(1,t)))*2*Math.PI;return[70+R*Math.sin(a),70-R*Math.cos(a)];};
 const[ax,ay]=arco(0),[bx,by]=arco(1);
 const len=v===null?0:largo*Math.max(0,Math.min(1,v));
 const d=`M${ax.toFixed(1)} ${ay.toFixed(1)} A${R} ${R} 0 1 1 ${bx.toFixed(1)} ${by.toFixed(1)}`;
 let mk="";
 if(marca!==undefined){const[mx,my]=arco(marca);
  mk=`<circle cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="4.6" fill="var(--bg)" stroke="var(--tx2)" stroke-width="2"/>`;}
 return `<div class="anillo" data-tip="<b>${esc(tit)}</b>${esc(sub)}"><svg viewBox="0 0 140 130">
  <path d="${d}" fill="none" stroke="rgba(255,255,255,.075)" stroke-width="13" stroke-linecap="round"/>
  <path d="${d}" fill="none" stroke="var(--a1)" stroke-width="13" stroke-linecap="round"
   stroke-dasharray="${len.toFixed(1)} ${(C*2).toFixed(0)}"/>${mk}
  <text x="70" y="76" text-anchor="middle" class="a-num" fill="var(--tx)" font-size="26"
   ${v===null?"":`data-num="${v}" data-dec="${dec}"`}>${v===null?"—":"0"}</text>
 </svg><div class="a-tit">${esc(tit)}</div><div class="a-sub">${esc(sub)}</div></div>`;
}

/* ================= segmentado genérico ================= */
const ESTADO={};
function seg(fid,ops){
 const on=ESTADO[fid]??ops[0][0];
 return `<div class="seg" data-seg="${fid}"><div class="pill"></div>${ops.map(([k,t])=>
  `<button data-k="${esc(k)}" class="${k===on?"on":""}">${esc(t)}</button>`).join("")}</div>`;
}
function colocaPill(sg){
 const b=sg.querySelector("button.on"),p=sg.querySelector(".pill");
 if(b&&p){p.style.left=b.offsetLeft+"px";p.style.width=b.offsetWidth+"px";}
}

/* ================= bosque (forest plot) genérico ================= */
/* filas: [{etq, sub, marcas:[{v, ic, lleno, nombre}]}]; fmt da el texto del eje */
function bosque(filas,fmt,opt={}){
 const W=opt.W||840,fh=opt.fh||58,H=fh*filas.length+48,x0=opt.x0||230,x1=W-(opt.xr||70);
 const todos=filas.flatMap(f=>f.marcas.flatMap(m=>[m.ic[0],m.ic[1],m.v])).concat([opt.ref??0]);
 let lo=Math.min(...todos),hi=Math.max(...todos);const mg=(hi-lo)*.1||.01;lo-=mg;hi+=mg;
 const X=v=>x0+(v-lo)/(hi-lo)*(x1-x0),z=X(opt.ref??0);
 let g=`<svg viewBox="0 0 ${W} ${H}" data-bosque="1">
  <line x1="${z.toFixed(1)}" y1="18" x2="${z.toFixed(1)}" y2="${H-26}" stroke="#fff"
   stroke-opacity=".28" stroke-width="1.3" stroke-dasharray="4 4"/>
  <text x="${z.toFixed(1)}" y="12" text-anchor="middle" fill="var(--tx3)" font-size="10"
   font-family="var(--mono)" letter-spacing="1">${esc(opt.refTxt||"SIN DIFERENCIA")}</text>`;
 filas.forEach((f,i)=>{
  const y=36+i*fh,n=f.marcas.length;
  g+=`<text x="0" y="${y+4}" fill="var(--tx)" font-size="12.5" font-weight="600">${esc(f.etq)}</text>`;
  if(f.sub)g+=`<text x="0" y="${y+20}" fill="var(--tx3)" font-size="11" font-family="var(--mono)">${esc(f.sub)}</text>`;
  f.marcas.forEach((m,j)=>{
   const yy=y+(j-(n-1)/2)*14,col=m.lleno?"var(--a1)":"var(--tx2)";
   const tt=`<b>${esc(f.etq)}${m.nombre?" · "+esc(m.nombre):""}</b>${fmt(m.v)} [${fmt(m.ic[0])}, ${fmt(m.ic[1])}]`+
    (m.q!==undefined&&m.q!==null?`<br>q = ${(+m.q).toFixed(3)}`:"")+(m.nota?`<br>${esc(m.nota)}`:"");
   g+=`<g data-tip="${tt}" class="marca">
    <rect x="${x0-6}" y="${yy-8}" width="${x1-x0+12}" height="16" fill="transparent"/>
    <line x1="${X(m.ic[0]).toFixed(1)}" y1="${yy}" x2="${X(m.ic[1]).toFixed(1)}" y2="${yy}"
     stroke="${col}" stroke-width="5" stroke-linecap="round" opacity=".45"/>
    <circle cx="${X(m.v).toFixed(1)}" cy="${yy}" r="6" fill="${m.lleno?col:"var(--bg)"}"
     stroke="${col}" stroke-width="2.2" data-lleno="${m.lleno?1:0}"/></g>`;
  });
  const u=f.marcas[0];
  g+=`<text x="${W}" y="${y+4}" text-anchor="end" fill="var(--tx)" font-size="12"
   font-weight="700" font-family="var(--mono)">${fmt(u.v)}</text>`;
 });
 g+=`<text x="${x0}" y="${H-8}" fill="var(--tx3)" font-size="10" font-family="var(--mono)">${fmt(lo)}</text>
  <text x="${x1}" y="${H-8}" text-anchor="end" fill="var(--tx3)" font-size="10" font-family="var(--mono)">${fmt(hi)}</text>`;
 return g+`</svg>`;
}

/* ================= línea por torneo ================= */
function linea(puntos,fmt,opt={}){
 const W=840,H=280,x0=58,x1=W-24,y0=24,y1=H-46;
 const vs=puntos.filter(p=>p.v!==null).flatMap(p=>p.sd!==undefined?[p.v-p.sd,p.v+p.sd]:[p.v]).concat(opt.ref!==undefined?[opt.ref]:[]);
 let lo=opt.lo??Math.min(...vs),hi=opt.hi??Math.max(...vs);const mg=(hi-lo)*.08||.01;
 if(opt.lo===undefined)lo-=mg;if(opt.hi===undefined)hi+=mg;
 const X=i=>x0+(puntos.length<2?.5:i/(puntos.length-1))*(x1-x0),Y=v=>y1-(v-lo)/(hi-lo)*(y1-y0);
 let g=`<svg viewBox="0 0 ${W} ${H}" data-linea="1">`;
 [lo,(lo+hi)/2,hi].forEach(t=>{g+=`<line x1="${x0}" x2="${x1}" y1="${Y(t)}" y2="${Y(t)}" stroke="#fff" stroke-opacity=".06"/>
  <text x="${x0-8}" y="${Y(t)+4}" text-anchor="end" fill="var(--tx3)" font-size="10" font-family="var(--mono)">${fmt(t)}</text>`;});
 if(opt.ref!==undefined)g+=`<line x1="${x0}" x2="${x1}" y1="${Y(opt.ref)}" y2="${Y(opt.ref)}" stroke="#fff"
  stroke-opacity=".4" stroke-dasharray="5 5"/><text x="${x1}" y="${Y(opt.ref)-6}" text-anchor="end"
  fill="var(--tx2)" font-size="10" font-family="var(--mono)">${esc(opt.refTxt||"liga")}</text>`;
 const ok=puntos.map((p,i)=>[p,i]).filter(([p])=>p.v!==null);
 if(ok.some(([p])=>p.sd!==undefined)){
  const arr=ok.map(([p,i])=>`${X(i)},${Y(p.v+p.sd)}`).join(" "),
        abj=ok.slice().reverse().map(([p,i])=>`${X(i)},${Y(p.v-p.sd)}`).join(" ");
  g+=`<polygon points="${arr} ${abj}" fill="var(--a1)" opacity=".08"/>`;}
 g+=`<polyline points="${ok.map(([p,i])=>`${X(i)},${Y(p.v)}`).join(" ")}" fill="none" stroke="var(--a1)" stroke-width="2.2"/>`;
 puntos.forEach((p,i)=>{
  g+=`<text x="${X(i)}" y="${H-22}" text-anchor="middle" fill="var(--tx2)" font-size="11" font-family="var(--mono)">${esc(p.t)}</text>`;
  if(p.v===null)return;
  g+=`<g data-tip="<b>${esc(p.t)}</b>${esc(p.tip||fmt(p.v))}"><circle cx="${X(i)}" cy="${Y(p.v)}" r="12" fill="transparent"/>
   <circle cx="${X(i)}" cy="${Y(p.v)}" r="5.5" fill="var(--a1)"/></g>`;});
 return g+`</svg>`;
}

/* ================= barras horizontales ================= */
function barras(filas,fmt,max){
 const m=max||Math.max(...filas.map(f=>f.v),1e-9);
 return `<div class="lista">${filas.map(f=>`<div class="item" data-tip="<b>${esc(f.etq)}</b>${esc(f.tip||fmt(f.v))}">
  <div class="it-tx"><div class="it-nom">${esc(f.etq)}</div>${f.sub?`<div class="it-sub">${esc(f.sub)}</div>`:""}</div>
  <div class="it-bar"><i style="background:var(--a1);width:${(100*f.v/m).toFixed(1)}%" data-w="${(100*f.v/m).toFixed(1)}"></i></div>
  <div class="it-val">${fmt(f.v)}</div></div>`).join("")}</div>`;
}
const vacio=(txt,cmd)=>`<div class="vacio">${txt}${cmd?`<code>${esc(cmd)}</code>`:""}</div>`;

/* ================= figuras ================= */
const FIG={
 fig1(){
  const mini=pitch((s)=>{let g="";for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++)
   g+=`<rect x="${ix*cw*s+2}" y="${iy*ch*s+2}" width="${cw*s-4}" height="${ch*s-4}" rx="5"
    fill="var(--a1)" fill-opacity="${ix===3&&iy===1?.8:.05}" stroke="#fff" stroke-opacity=".15"/>`;return g;},300);
  const cad=`<svg viewBox="0 0 300 120">${[0,1,2,3,4,5].map(i=>`<circle cx="${30+i*44}" cy="60" r="10"
   fill="var(--a1)" opacity="${.35+i*.1}"/>`).join("")}${[0,1,2,3,4].map(i=>`<line x1="${40+i*44}" x2="${64+i*44}"
   y1="60" y2="60" stroke="var(--tx2)" stroke-width="1.5"/>`).join("")}
   <text x="150" y="104" text-anchor="middle" fill="var(--tx2)" font-size="12">una acción = un paso</text></svg>`;
  const fin=`<svg viewBox="0 0 300 120"><circle cx="40" cy="60" r="12" fill="var(--a1)"/>
   <path d="M52 60 C120 60 150 22 220 22" fill="none" stroke="var(--a1)" stroke-width="2"/>
   <path d="M52 60 C120 60 150 98 220 98" fill="none" stroke="var(--tx3)" stroke-width="2" stroke-dasharray="4 4"/>
   <rect x="222" y="8" width="70" height="28" rx="8" fill="var(--a1)"/><text x="257" y="27" text-anchor="middle"
   fill="#0b0b0e" font-size="12" font-weight="700">remate</text>
   <rect x="222" y="84" width="70" height="28" rx="8" fill="none" stroke="var(--tx3)"/><text x="257" y="103"
   text-anchor="middle" fill="var(--tx2)" font-size="12">pérdida</text></svg>`;
  return `<div class="esquema">
   <div class="card flat" data-tip="<b>Dónde</b>En qué zonas de la cancha pasan las acciones de la posesión.">${mini}<h4>¿Dónde se juega?</h4><p>Zona de cada acción, con el ataque hacia la derecha.</p></div>
   <div class="card flat" data-tip="<b>Cuánto dura</b>Acciones encadenadas antes de que termine la posesión.">${cad}<h4>¿Cuánto dura?</h4><p>Acciones por posesión, contadas igual para todos los equipos.</p></div>
   <div class="card flat" data-tip="<b>Cómo termina</b>Probabilidad de que la posesión acabe en remate o en gol.">${fin}<h4>¿Cómo termina?</h4><p>Probabilidad de remate y de gol al final de la cadena.</p></div></div>`;
 },
 fig1b(d){
  return linea(d.map(p=>({t:p.t,v:p.v,sd:p.sd,tip:`${p.v.toFixed(2)} acciones por posesión (± ${p.sd.toFixed(2)} entre clubes)`})),v=>v.toFixed(1));
 },
 fig2(d){
  if(d.falta)return vacio("Falta el parquet de transiciones del América; el mapa se pinta al generarlo en la máquina del proyecto.",d.falta);
  return mapaSVG(d.m,C_FOCO,"de las acciones del América de Jardine")+
   leyenda(rampa(C_FOCO,"pocas acciones","muchas"),"Los porcentajes suman 100.");
 },
 fig3(d,fid){
  const modo=ESTADO[fid]??"did";
  const filas=d.map(p=>({etq:p.par,sub:`q = ${p.q.toFixed(3)}`,marcas:[
   ...(modo!=="cru"?[{v:p.did,ic:p.did_ic,lleno:true,nombre:"corregido",q:p.q,nota:p.rech?"sobrevive a la corrección":"no sobrevive a la corrección"}]:[]),
   ...(modo!=="did"?[{v:p.cru,ic:p.cru_ic,lleno:false,nombre:"crudo",nota:"resta directa, con la deriva dentro"}]:[])]}));
  return seg(fid,[["did","corregido"],["cru","crudo"],["ambos","los dos"]])+
   bosque(filas,v=>pct(v))+leyenda(SW(C_FOCO,"contra la liga del mismo torneo"),SW("var(--tx2)","resta cruda",true));
 },
 fig3b(d){
  return bosque(d.map(p=>({etq:p.par,sub:`q = ${p.q.toFixed(3)}`,marcas:[{v:p.t,ic:p.ic,lleno:p.r,q:p.q,
   nota:p.r?"sobrevive a la corrección":"no sobrevive a la corrección"}]})),v=>ppt(v))+
   leyenda(SW(C_FOCO,"sobrevive"),SW("var(--tx2)","no sobrevive",true));
 },
 fig4(d,fid){
  const m=ESTADO[fid]??"pos";
  const sel=seg(fid,[["pos","posesión"],["ft","field tilt"],["xg","npxG a favor"]]);
  if(m==="pos")return sel+linea(d.map(p=>({t:p.t,v:p.pos,tip:`${pct(p.pos)} sobre la liga · ${p.n} posesiones`})),v=>pct(v,0),{ref:0,refTxt:"liga del torneo"});
  const k=m;return sel+linea(d.map(p=>({t:p.t,v:p[k],tip:p[k]===null?"torneo parcial":`percentil ${(+p[k]).toFixed(2)}`})),
   v=>v.toFixed(2),{lo:0,hi:1,ref:.5,refTxt:"mediana de la liga"});
 },
 tabla5(d){
  const f=(v,u)=>u==="num"?v.toFixed(2):(v*100).toFixed(1)+"%";
  const fd=(v,u)=>u==="num"?fmtS(v,2):ppt(v);
  return `<div class="tabla-scroll"><table class="t5"><thead><tr><th>contexto</th><th>métrica</th>
   <th style="text-align:right">A</th><th style="text-align:right">B</th><th style="text-align:right">A − B</th></tr></thead><tbody>
   ${d.map(r=>`<tr><td>${esc(r.ctx)}</td><td>${esc(r.m)}</td>
    <td class="n" data-tip="<b>${esc(r.a)}</b>${f(r.va,r.uni)}">${f(r.va,r.uni)}</td>
    <td class="n" data-tip="<b>${esc(r.b)}</b>${f(r.vb,r.uni)}">${f(r.vb,r.uni)}</td>
    <td class="n">${fd(r.d,r.uni)}</td></tr>`).join("")}</tbody></table></div>
   <div class="nota">A y B: <b>local / visitante</b>, <b>perdiendo / ganando</b>, <b>desde el minuto 60 / antes</b>, <b>rival fuerte / débil</b>.</div>`;
 },
 fig5(d,fid){
  const tecs=Object.keys(d),on=ESTADO[fid]??tecs[0];
  const sel=seg(fid,tecs.map(t=>[t,t.split(" ").pop()]));
  const filas=d[on],mets=[...new Set(filas.map(f=>f.m))];
  return sel+`<div class="grid g2f">${mets.map(mk=>{
   const fs=filas.filter(f=>f.m===mk),u=fs[0].uni,fmt=u==="num"?(v=>fmtS(v,2)):(v=>ppt(v));
   return `<div class="card flat"><div class="eq">${esc(mk)} · ${esc(fs[0].mn)}</div>${bosque(fs.map(f=>{
    const ex=f.ic[0]*f.ic[1]>0;
    return {etq:f.ctx,marcas:[{v:f.t,ic:f.ic,lleno:f.r,q:f.q,
     nota:f.r?"sobrevive a la corrección":ex?"excluye el cero antes de corregir; no sobrevive":"el intervalo cruza el cero"}]};}),
    fmt,{W:440,x0:96,xr:62,fh:44})}</div>`;}).join("")}</div>`+
   leyenda(SW(C_FOCO,"sobrevive a la corrección"),SW("var(--tx2)","no sobrevive",true));
 },
 fig6(d,fid){
  const m=ESTADO[fid]??"cont";
  const sel=seg(fid,[["cont","continuidad del once"],["n80","N80"]]);
  const lim=m==="cont"?D.reglas.cont_inferior[0]:D.reglas.n80_mediana[0];
  return sel+`<div class="grid g3" style="margin-top:1rem">${d.map(a=>{
   const v=a.parcial?null:(m==="cont"?a.percentil_continuidad:a.percentil_n80);
   const sub=a.parcial?"torneo parcial":m==="cont"?`${(a.continuidad*100).toFixed(0)}% del once se repite`:`N80 = ${a.n80} jugadores`;
   return anillo(v,a.t,sub,2,lim);}).join("")}</div>`+
   leyenda(SW(C_FOCO,"percentil en la liga del mismo torneo"),
    `<span class="leg">marca: ${m==="cont"?Math.round(lim*100)+"% inferior":"mediana"}</span>`);
 },
 roles(d,fid){
  const on=ESTADO[fid]??String(d[0].id),j=d.find(x=>String(x.id)===on)||d[0];
  const mx=Math.max(...d.map(x=>x.min));
  return `<div class="grid duo"><div class="lista">${d.map(x=>`<div class="item ${String(x.id)===String(j.id)?"on":""}" data-jug="${x.id}" data-fig="${fid}">
   <div class="it-tx"><div class="it-nom">${esc(x.pos)}</div><div class="it-sub">jugador ${x.id} · ${x.acc} acciones</div></div>
   <div class="it-bar"><i style="background:var(--a1);width:${(100*x.min/mx).toFixed(1)}%" data-w="${(100*x.min/mx).toFixed(1)}"></i></div>
   <div class="it-val">${Math.round(x.min)}′</div></div>`).join("")}</div>
   <div class="panel"><div class="mapcap"><i style="background:var(--a1)"></i>${esc(j.pos)}<s>jugador ${j.id}</s></div>
   ${mapaSVG(j.z,C_FOCO,"de sus acciones")}</div></div>`;
 },
 fig7(d,fid){
  const m=ESTADO[fid]??"s";
  return seg(fid,[["s","termina en remate"],["g","termina en gol"]])+
   barras(d.map(x=>({etq:x.n,v:x[m],tip:`${(x[m]*100).toFixed(1)}% de las secuencias`})),v=>(v*100).toFixed(1)+"%");
 },
 fig7b(d){
  const nom={dist_meta:"distancia a la portería",angulo:"ángulo de tiro",cabeza:"remate de cabeza"};
  return bosque(d.map(x=>({etq:nom[x.k]||x.k,marcas:[{v:x.b,ic:x.ic,lleno:x.ic[0]*x.ic[1]>0,
   nota:"coeficiente estandarizado: una desviación estándar de la variable (o cabeza contra pie), a igualdad del resto"}]})),v=>fmtS(v,2));
 },
 remates(d,fid){
  const m=ESTADO[fid]??"of",z=d[m];
  const nom={area_chica:"área chica",area_central:"área, zona central",area_lateral:"área, costados",fuera_del_area:"fuera del área"};
  const tot=Object.values(z).reduce((a,b)=>a+b.n,0)||1;
  return seg(fid,[["of","a favor"],["def","en contra"]])+
   barras(Object.entries(z).map(([k,v])=>({etq:nom[k]||k,sub:`xG acumulado ${v.xg.toFixed(1)}`,v:v.n,
    tip:`${v.n} remates (${(100*v.n/tot).toFixed(0)}%), xG ${v.xg.toFixed(2)}`})),v=>String(v));
 },
 fig8(d){
  const cel=(v,ic,fmt,niv)=>`<div class="celdaic" data-tip="<b>nivel ${niv}</b>${fmt(v)} [${fmt(ic[0])}, ${fmt(ic[1])}]">
   <b>${fmt(v)}</b>${mini(v,ic)}</div>`;
  return `<div class="tabla-scroll"><table class="t5"><thead><tr><th>era</th>
   <th><span class="nv nv-B">B</span> posesión</th><th><span class="nv nv-B">B</span> field tilt</th>
   <th><span class="nv nv-B">B</span> npxG a favor</th><th><span class="nv nv-C">C</span> once en el ${Math.round(D.reglas.cont_inferior[0]*100)}% inferior</th></tr></thead><tbody>
   ${d.map(r=>`<tr><td><b>${esc(r.era)}</b></td><td>${cel(r.pos,r.pos_ic,v=>pct(v),"B")}</td>
    <td>${cel(r.ft,r.ft_ic,v=>ppt(v),"B")}</td><td>${cel(r.xg,r.xg_ic,v=>fmtS(v,2),"B")}</td>
    <td class="n" data-tip="<b>nivel C</b>torneos completos con la continuidad en el 15% inferior">${r.cont} de ${r.cont_n}</td></tr>`).join("")}
   </tbody></table></div>`;
 },
 viajan(d){
  return `<div class="chips">${d.map(x=>`<span class="chip" data-tip="<b>${esc(x.coach)}</b>${x.mismo?"mismo signo en sus clubes":"el signo cambia de un club a otro"}"
   style="${x.mismo?"background:var(--a1);color:#0b0b0e":""}">${esc(x.coach)} <span style="${x.mismo?"color:#0b0b0e":""}">${x.mismo?"· mismo signo":"· cambia"}</span></span>`).join("")}</div>`;
 },
 fig9b(d){
  return `<div class="grid g2">${d.map(x=>`<div class="card flat"><div class="eq">${esc(x.k)}</div>
   ${barras([{etq:"crudo",v:x.cru,tip:`${x.cru} de ${x.de}`},{etq:"corregido",v:x.did,tip:`${x.did} de ${x.de}`}],v=>String(v),x.de)}
   <div class="nota">de ${x.de}</div></div>`).join("")}</div>`;
 },
 fig9(d){
  const ok=d.filter(p=>p.cumple).length,grupos={};
  d.forEach(p=>(grupos[p.adr]=grupos[p.adr]||[]).push(p));
  return `<div class="grid duo"><div class="puntos">${Object.entries(grupos).map(([a,ps])=>
   `<div class="grupo-adr"><u>ADR-${a}</u>${ps.map(p=>`<span class="pto ${p.cumple?"si":"no"}"
    data-tip="<b>ADR-${a} · predicción ${p.n}</b>${esc(p.texto)}<br>${p.cumple?"se cumplió":"falló"}"></span>`).join("")}</div>`).join("")}</div>
   <div class="cifra"><u>SE CUMPLIERON</u><b class="marcador-total"><span data-num="${ok}" data-dec="0">0</span> / ${d.length}</b>
   <i>Las que fallaron se quedan a la vista.</i></div></div>`;
 },
 bugs(d){return vacio(`Pendiente: falta la fuente del catálogo en el paquete de insumos.`,d.falta);},
};
function mini(v,ic){
 const lo=Math.min(ic[0],0,v),hi=Math.max(ic[1],0,v),X=t=>4+(t-lo)/((hi-lo)||1)*112;
 return `<svg viewBox="0 0 120 14" style="max-width:120px"><line x1="${X(0)}" x2="${X(0)}" y1="1" y2="13" stroke="#fff" stroke-opacity=".35"/>
  <line x1="${X(ic[0])}" x2="${X(ic[1])}" y1="7" y2="7" stroke="var(--a1)" stroke-width="4" stroke-linecap="round" opacity=".5"/>
  <circle cx="${X(v)}" cy="7" r="3.5" fill="var(--a1)"/></svg>`;
}

/* ================= bloques y secciones ================= */
const FIGDATOS={};
function pintaFig(fid){
 const el=document.querySelector(`[data-fig-id="${fid}"] .lienzo`);if(!el)return;
 const {id,datos}=FIGDATOS[fid];
 el.innerHTML=FIG[id]?FIG[id](datos,fid):vacio("figura sin dibujar: "+esc(id));
 el.querySelectorAll("[data-seg]").forEach(sg=>{colocaPill(sg);
  sg.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{
   ESTADO[sg.dataset.seg]=b.dataset.k;pintaFig(sg.dataset.seg);}));});
 el.querySelectorAll("[data-jug]").forEach(it=>it.addEventListener("click",()=>{
  ESTADO[it.dataset.fig]=it.dataset.jug;pintaFig(it.dataset.fig);}));
 animaNumeros(el);
}
function bloque(b,sid,i){
 if(b.tipo==="frase"){
  const ad=b.adenda?`<span class="adenda" data-tip="${esc(ADENDA(b.adenda))}">adenda 1</span>`:"";
  return `<p class="fr${b.nulo?" nulo":""}" data-nivel="${b.nivel}"><span class="nv nv-${b.nivel}" data-tip="${esc(NIVEL[b.nivel])}">${b.nivel}</span><span class="tx">${b.html}${ad}</span></p>`;}
 if(b.tipo==="nota")return `<div class="nota">${b.html}</div>`;
 if(b.tipo==="plegable")return `<details class="plegable"><summary>${esc(b.titulo)}</summary>${b.html}</details>`;
 if(b.tipo==="fig"){
  const fid=`${sid}-${b.id}`;FIGDATOS[fid]={id:b.id,datos:b.datos};
  return `<div class="fig" data-fig-id="${fid}" data-fig="${b.id}"><div class="card">
   <div class="fig-tit">${esc(b.titulo)}</div>${b.pie?`<div class="nota" style="margin-top:.1rem;margin-bottom:.9rem">${esc(b.pie)}</div>`:""}
   <div class="lienzo"></div></div></div>`;}
 return "";
}
function seccion(s){
 const cuerpo=s.falta?vacio(`Falta <b>${esc(s.falta.archivo)}</b>. Esta sección no se pinta sin él.`,s.falta.comando)
  :s.bloques.map((b,i)=>bloque(b,s.id,i)).join("");
 return `<section id="${s.id}" class="rev"><div class="eyebrow">${s.num} · componente ${esc(s.comp)}</div>
  <h2>${esc(s.tit)}</h2>${cuerpo}</section>`;
}
function traza(){
 const t=D.traza,c=t.commit;
 $("traza").innerHTML=`<span class="chip" data-tip="<b>código</b>commit con el que se generó esta página">commit ${esc(c.hash)}${c.sucio?" · con cambios":""}</span>`+
  t.insumos.map(x=>x.sha?`<span class="chip" data-tip="<b>${esc(x.archivo)}</b>sha256 ${esc(x.sha)}… · corrida del ${esc(x.fecha)}">${esc(x.archivo.replace(".json",""))} <span>${esc(x.fecha)}</span></span>`
   :`<span class="chip falta" data-tip="<b>falta</b>${esc(x.comando)}">${esc(x.archivo.replace(".json",""))} <span>falta</span></span>`).join("");
 $("pie").innerHTML=`Generado ${esc(t.generado)}. Los JSON de reports/ no se versionan: la huella de cada uno está arriba.`;
}
function nav(){
 const sg=$("segSec");
 sg.innerHTML=`<div class="pill"></div>`+D.secciones.map((s,i)=>`<button data-s="${s.id}" class="${i?"":"on"}" title="${esc(s.tit)}">${s.num}</button>`).join("");
 $("navtit").textContent=D.secciones[0].tit;
 const marca=id=>{sg.querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.s===id));
  const s=D.secciones.find(x=>x.id===id);if(s)$("navtit").textContent=s.tit;colocaPill(sg);};
 sg.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{
  const el=$(b.dataset.s);if(el&&el.scrollIntoView)el.scrollIntoView({behavior:"smooth",block:"start"});marca(b.dataset.s);}));
 const secs=document.querySelectorAll("#informe section");
 if(typeof IntersectionObserver==="function"){
  const vis=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)e.target.classList.add("on");}),{threshold:.08});
  const esp=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)marca(e.target.id);}),{rootMargin:"-45% 0px -50% 0px"});
  secs.forEach(s=>{vis.observe(s);esp.observe(s);});
 }else secs.forEach(s=>s.classList.add("on"));
 colocaPill(sg);
}
function arranca(){
 traza();
 $("informe").innerHTML=D.secciones.map(seccion).join("");
 Object.keys(FIGDATOS).forEach(pintaFig);
 nav();
 $("btnGuia").onclick=()=>{const g=$("guia");g.open=true;g.scrollIntoView({behavior:"smooth",block:"start"});};
}
arranca();
</script></body></html>"""

if __name__ == "__main__":
    main()
