#!/usr/bin/env python3
"""
12_reporte_html.py — el informe final (H7), en tres actos y cinco historias.

QUÉ PRODUCE
-----------
Un solo `reporte.html`, autocontenido (ADR-38): datos embebidos, figuras en SVG
dibujadas por JavaScript, sin CDN ni fuentes remotas. Se abre con doble clic.

CÓMO ESTÁ HECHO
---------------
1. `recolecta()` lee los siete JSON de `reports/`.
2. `historias()` arma las cinco historias de ADR-59 adenda 2 §2: las eras de
   cada técnico (igualdad EXACTA sobre `coach`) y su era principal (la de más
   partidos). Si existe, lee el parquet de transiciones de la era principal
   para el mapa de zonas.
3. `Modelo` guarda cada cifra con su fuente (JSON › ruta) y cada frase con su
   nivel (A probado, B medido, C descriptivo) y su capa (1 frase, 2 figura,
   3 en un partido, 4 cómo lo medimos). Todos los modelos escriben en un
   mismo registro de cifras.
4. La prosa se escribe aquí, con plantillas fijas que valen para las cinco
   historias (adenda 2 §3). Las lecturas preinscritas de ADR-59 solo valen
   para Jardine y conservan sus guardas: si se rompen, no se escribe nada.
5. Antes de escribir, la salida entera pasa por `frases_prohibidas.revisa()`.

Estructura: ADR-59 §4 reordenada por `docs/preinscritos/ADR-59_ADENDA_2.md`
(portada, acto 1 común, actos 2 y 3 por historia, cierre común). No lee
`reports/barrido/` (adenda 2 §2).

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
    "rel":  ("relevos_v1.json",       "python scripts/42_relevos.py"),
    "est":  ("estilos_v1.json",       "python scripts/43_mapa_estilos.py"),
    "pla":  ("placebo_v1.json",       "python scripts/44_placebo_T.py"),
    "prog": ("progresion_v1.json",    "python scripts/45_progresion.py"),
    "sup":  ("supervivencia_v1.json", "python scripts/45_progresion.py"),
}

# Las cinco historias (adenda 2 §2). El orden es el del selector.
HISTORIAS = [
    ("jardine", "Andre Jardine"),
    ("larcamon", "Nicolas Larcamon"),
    ("ambriz", "Ignacio Ambriz"),
    ("herrera", "Miguel Herrera"),
    ("ortiz", "Fernando Ortiz"),
]
JARDINE = "jardine"
CLUB_J = "América"
FOCO = "Andre Jardine"
ERAS_CLUB = ["Andre Jardine", "Fernando Ortiz", "Santiago Solari"]
FUERA = [("Atlético San Luis", "Andre Jardine"), ("Monterrey", "Fernando Ortiz")]

# Nombres para mostrar. Las claves son los valores del JSON y NO se tocan.
NOMBRE = {
    "Andre Jardine": "André Jardine", "Nicolas Larcamon": "Nicolás Larcamón",
    "Domenec Torrent": "Domènec Torrent", "Benat San Jose": "Beñat San José",
    "Benjamin Mora": "Benjamín Mora", "Martin Anselmi": "Martín Anselmi",
    "Martin Demichelis": "Martín Demichelis", "Sebastian Abreu": "Sebastián Abreu",
    "Victor Manuel Vucetich": "Víctor Manuel Vucetich",
}
APELLIDO = {"Benat San Jose": "San José", "Diego Cocca I": "Cocca I",
            "Diego Cocca II": "Cocca II", "Juan Carlos Osorio": "Osorio",
            "Victor Manuel Vucetich": "Vucetich", "Antonio Mohamed": "Mohamed"}
SIN_ARTICULO = {"Tigres UANL"}

POS = {
    "Goalkeeper": "portero", "Right Back": "lateral derecho", "Left Back": "lateral izquierdo",
    "Right Wing Back": "carrilero derecho", "Left Wing Back": "carrilero izquierdo",
    "Center Back": "central", "Right Center Back": "central por derecha",
    "Left Center Back": "central por izquierda",
    "Center Defensive Midfield": "contención", "Right Defensive Midfield": "contención por derecha",
    "Left Defensive Midfield": "contención por izquierda",
    "Center Midfield": "medio centro", "Right Center Midfield": "interior derecho",
    "Left Center Midfield": "interior izquierdo", "Right Midfield": "volante derecho",
    "Left Midfield": "volante izquierdo", "Center Attacking Midfield": "mediapunta",
    "Right Attacking Midfield": "mediapunta por derecha",
    "Left Attacking Midfield": "mediapunta por izquierda",
    "Right Wing": "extremo derecho", "Left Wing": "extremo izquierdo",
    "Center Forward": "centro delantero", "Right Center Forward": "delantero por derecha",
    "Left Center Forward": "delantero por izquierda", "Striker": "delantero",
    "Secondary Striker": "segundo delantero",
}

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


def m_pct(x):
    return f"{x * 100:.1f}%"


def m_pp(x):
    return f"{x * 100:.1f} pp"


def m_num(x, dec=2):
    return f"{x:.{dec}f}"


def margen(ic):
    """Extremo del IC más lejano al cero (ADR-59 §3)."""
    return max(abs(ic[0]), abs(ic[1]))


def direccion(ic):
    """+1 si el IC está por encima del cero, −1 si por debajo, 0 si lo cruza."""
    return 1 if ic[0] > 0 else -1 if ic[1] < 0 else 0


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


def nom(c: str) -> str:
    return NOMBRE.get(c, c)


def ape(c: str) -> str:
    return APELLIDO.get(c) or nom(c).split()[-1]


def del_(club: str) -> str:
    return ("de " if club in SIN_ARTICULO else "del ") + club


def el_(club: str) -> str:
    return club if club in SIN_ARTICULO else "el " + club


def en_(club: str) -> str:
    return "en " + el_(club)


def pos(p: str) -> str:
    return POS.get(p, p)


# ---------------------------------------------------------------------------
# el modelo: cifras con fuente y frases con nivel y capa
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

    def __init__(self, J: dict, registro: list | None = None, *, exporta=True, hid="comun"):
        self.J = J
        self.cifras: list[dict] = registro if registro is not None else []
        self.exporta = exporta   # solo Jardine y el acto 1 exportan macros LaTeX
        self.hid = hid

    def need(self, *claves):
        for k in claves:
            if self.J.get(k) is None:
                raise FaltaInsumo(k)

    # -- cifras ------------------------------------------------------------
    def c(self, texto: str, fuente: str, clave: str = "") -> str:
        """Una cifra en el texto. Siempre con fuente; el tooltip la muestra.
        `clave` la exporta como macro \\cifra<clave> para la guía LaTeX."""
        self.cifras.append({"t": texto, "f": fuente, "k": clave if self.exporta else "",
                            "h": self.hid})
        return (f'<span class="cf" data-f="{esc(fuente)}" '
                f'data-tip="<b>fuente</b>{esc(esc(fuente))}">{esc(texto)}</span>')

    def cita(self, texto: str, fuente: str) -> str:
        """Texto largo copiado del JSON (una regla, una lista). Cuenta como cifra."""
        self.cifras.append({"t": texto, "f": fuente, "k": "", "h": self.hid})
        return (f'<span class="cf cita" data-f="{esc(fuente)}" '
                f'data-tip="<b>fuente</b>{esc(esc(fuente))}">{esc(texto)}</span>')

    def ic(self, ic, fmt, fuente: str, clave: str = "", **kw) -> str:
        """Intervalo: se oculta en el modo sencillo (adenda 2 §7)."""
        return '<span class="tec"> ' + self.c(f_ic(ic, fmt, **kw), fuente, clave) + "</span>"

    def q(self, q, fuente: str, clave: str = "") -> str:
        """q con su lectura: el número es técnico, la lectura se ve siempre."""
        return ('<span class="tec">, q = ' + self.c(f_q(q), fuente, clave) + "</span>"
                f" ({fuerza(q)})")

    def regla(self, clave: str, texto: str) -> str:
        return self.c(texto, REGLAS[clave][1])

    # -- bloques -----------------------------------------------------------
    def frase(self, nivel: str, html_: str, *, ic=True, nota_adenda: str = "",
              adenda: int = 1, portada: int | None = None) -> dict:
        assert nivel in self.NIVELES, nivel
        if nivel == "B" and not ic:
            raise ValueError("una frase B necesita intervalo (ADR-59 §2)")
        return {"tipo": "frase", "capa": 1, "nivel": nivel, "html": html_,
                "adenda": nota_adenda, "n_adenda": adenda, "portada": portada}

    def nulo(self, html_: str, portada: int | None = None) -> dict:
        return {"tipo": "frase", "capa": 1, "nivel": "A", "nulo": True, "html": html_,
                "adenda": False, "portada": portada}

    def nota(self, html_: str) -> dict:
        return {"tipo": "nota", "html": html_}

    def fig(self, fid: str, titulo: str, pie: str, datos) -> dict:
        return {"tipo": "fig", "capa": 2, "id": fid, "titulo": titulo, "pie": pie,
                "datos": datos}

    def ejemplo(self, html_: str) -> dict:
        return {"tipo": "ejemplo", "capa": 3, "html": html_}

    def plegable(self, titulo: str, html_: str, capa: int | None = 4) -> dict:
        return {"tipo": "plegable", "capa": capa, "titulo": titulo, "html": html_}

    def hueco(self, capa: int, html_: str) -> dict:
        """Una capa que falta, declarada con su motivo (adenda 2 §5)."""
        return {"tipo": "hueco", "capa": capa, "html": html_}


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


class ZonasIlegibles(Exception):
    """El parquet de una era EXISTE y no se pudo usar. No es un hueco: es un
    error de entorno o de datos, y la página no se escribe (h2_32)."""


def _zonas_parquet(ruta: Path, club: str, coach: str):
    """Mapa 'dónde vive' de una era. Filtra por equipo Y por técnico.

    - Si el parquet NO existe, el mapa se declara como faltante (hueco legítimo:
      tests, humo, una máquina sin datos).
    - Si EXISTE y no se puede leer (sin polars, archivo roto, columnas que no
      están) o no deja ninguna fila para la era, se aborta. Antes esto salía
      como `zonas FALTA` con código 0: un error silencioso más.
    """
    if not ruta.exists():
        return {"falta": str(ruta)}
    try:
        import numpy as np
        import polars as pl
    except ImportError as e:
        raise ZonasIlegibles(f"{ruta} existe, pero este Python no tiene polars/numpy "
                             f"({e}). ¿Está activo .venv?") from e
    try:
        t = pl.read_parquet(ruta, columns=["team", "coach", "from_state"])
    except Exception as e:
        raise ZonasIlegibles(f"{ruta} existe, pero no se pudo leer: {e}") from e
    t = t.filter((pl.col("team") == club) & (pl.col("coach") == coach))
    if not t.height:
        raise ZonasIlegibles(f"{ruta}: 0 filas con team = {club!r} y coach = {coach!r}; "
                             "el nombre del club o del técnico no coincide con el del JSON")
    m = np.zeros((NX, NY))
    z = t["from_state"].to_numpy().astype(int) // 4
    fuera = 0
    for a, b in zip(z // NY, z % NY):
        if 0 <= a < NX and 0 <= b < NY:
            m[a, b] += 1
        else:
            fuera += 1
    tot = max(m.sum(), 1e-9)
    return {"m": (m / tot).round(5).tolist(), "n": int(m.sum()), "fuera": fuera}


def recolecta(reports: Path, datos: Path) -> tuple[dict, dict]:
    """`datos` es la raíz bajo la que viven `data/processed_api_<club>/`. Si no
    existe, los mapas de zonas se declaran como faltantes."""
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
    J["_datos"] = Path(datos)
    J["zonas"] = {}
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


def unidad_o_none(J, k, club, coach):
    try:
        return unidad(J, k, club, coach)
    except KeyError as e:
        if "unidades para" in str(e):
            raise
        return None


def par(lista, club, a, b):
    hallados = [p for p in lista
                if _del_club(p, club, f"pares[{p.get('a')} / {p.get('b')}]")
                and {p["a"], p["b"]} == {a, b}]
    if len(hallados) > 1:
        raise KeyError(f"{len(hallados)} pares para {club}: {a} / {b}")
    if not hallados:
        raise KeyError(f"sin par {club}: {a} / {b}")
    return hallados[0], (hallados[0]["a"] == a)


def pares_de(lista, clubes) -> list[dict]:
    return [p for p in lista
            if any(_del_club(p, c, f"pares[{p.get('a')} / {p.get('b')}]") for c in clubes)]


def torneos_orden(J):
    if J.get("h4"):
        return J["h4"]["parametros"]["torneos_orden"]
    if J.get("met"):
        return J["met"]["parametros"]["torneos"]
    return []


def primer_torneo(J, club, coach) -> int:
    """Índice del primer torneo de una era, para decir 'antes' o 'después'."""
    orden = torneos_orden(J)
    for k, campo in (("h4", "torneos"), ("met", "por_torneo"), ("jug", "A")):
        if J.get(k):
            u = unidad_o_none(J, k, club, coach)
            if u is not None and u.get(campo):
                ts = list(u[campo])
                return min(orden.index(t) for t in ts if t in orden)
    return 10 ** 6


# ---------------------------------------------------------------------------
# las cinco historias (adenda 2 §2)
# ---------------------------------------------------------------------------
def historia(J, hid: str, coach: str) -> dict:
    """Eras del técnico por igualdad EXACTA de `coach`, ordenadas en el tiempo;
    la principal es la de más partidos (empate: la más antigua)."""
    fuente = next((k for k in ("met", "jug", "ctx", "bp") if J.get(k)), None)
    eras = []
    if fuente:
        for u in J[fuente]["unidades"]:
            if u.get("coach") == coach and u.get("club"):
                eras.append({"club": u["club"], "n": u["n_partidos"], "slug": u.get("slug"),
                             "t0": primer_torneo(J, u["club"], coach)})
    eras.sort(key=lambda e: e["t0"])
    principal = max(eras, key=lambda e: (e["n"], -e["t0"]))["club"] if eras else None
    return {"id": hid, "coach": coach, "nombre": nom(coach), "eras": eras,
            "principal": principal, "clubes": [e["club"] for e in eras],
            "fuente_eras": fuente}


def zonas_de(J, club, coach):
    k = (club, coach)
    if k not in J["zonas"]:
        indir = None
        if J.get("h4"):
            u = unidad_o_none(J, "h4", club, coach)
            indir = u.get("indir") if u else None
        if indir is None:
            slug = next((e["slug"] for e in (J.get("met") or {}).get("unidades", [])
                         if e.get("club") == club and e.get("coach") == coach), None)
            indir = f"data/processed_api_{slug}"
        J["zonas"][k] = _zonas_parquet(J["_datos"] / indir / "transitions.parquet", club, coach)
    return J["zonas"][k]


# ---------------------------------------------------------------------------
# plantillas de redacción (adenda 2 §3)
# ---------------------------------------------------------------------------
def cola_B(M: Modelo, ic, fuente: str, fmt_m) -> str:
    s = direccion(ic)
    if s > 0:
        return " por encima de la liga"
    if s < 0:
        return " por debajo de la liga"
    return ("; no se separa de la liga: si hay diferencia, es menor a " +
            M.c(fmt_m(margen(ic)), fuente + ".ic95 (extremo más lejano al cero)"))


def frase_contraste(M: Modelo, etiqueta: str, t, ic, q, rechaza, fmt, fmt_m, fuente,
                    claves=("", "", "", ""), portada=None) -> dict:
    """Nivel A: 'difiere' si sobrevive a BH; nulo con margen si no."""
    k_t, k_ic, k_q, k_m = claves
    base = (etiqueta + " " + M.c(fmt(t), fuente, k_t) +
            M.ic(ic, fmt, fuente + ".ic95", k_ic) + M.q(q, fuente + ".q", k_q))
    if rechaza:
        return M.frase("A", base + ". Difiere.", portada=portada)
    excluye = ic[0] * ic[1] > 0
    return M.nulo(base + ". " + (
        "El intervalo no toca el cero, pero la diferencia no sobrevive a la corrección; "
        "si existe, es menor a " if excluye else "No detectamos una diferencia mayor a ") +
        M.c(fmt_m(margen(ic)), fuente + ".ic95 (extremo más lejano al cero)", k_m) + ".",
        portada=portada)


def cuando(J, H, otro, club) -> str:
    return "antes" if primer_torneo(J, club, otro) < primer_torneo(J, club, H["coach"]) else "después"


def plegable_fuente(M: Modelo, titulo: str, partes: list[str], fuentes: list[str]) -> dict:
    cuerpo = "".join(f"<p>{p}</p>" for p in partes)
    cuerpo += "<p><b>Archivo y campo</b>: " + " · ".join(M.cita(f, f) for f in fuentes) + "</p>"
    return M.plegable(titulo, cuerpo)


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
    js, _ = par(h4["pares"], CLUB_J, "Andre Jardine", "Santiago Solari")
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
    if J.get("rel"):
        out += [{"adr": 60, "n": p["n"], "texto": p["texto"], "cumple": p["cumple"]}
                for p in J["rel"]["predicciones"]]
    if J.get("prog"):
        out += [{"adr": 61, "n": p["n"], "texto": p["texto"], "cumple": p["cumple"]}
                for p in J["prog"]["predicciones"]]
    return out


def viajan_marcador(ctx) -> tuple[int, int, list]:
    """ADR-57 P1 sobre los nueve técnicos de varios clubes FUERA del América
    (adenda 1, punto 3). El JSON cuenta también a Jardine y a Ortiz."""
    fuera = {k: v for k, v in ctx["viaja_marcador_M1"].items()
             if k not in ERAS_CLUB}
    return sum(fuera.values()), len(fuera), sorted(fuera.items())


# ---------------------------------------------------------------------------
# ACTO 1 · el marco (común)
# ---------------------------------------------------------------------------
def a1_posesion(M: Modelo):
    return [
        M.frase("C", "Cada posesión se lee con tres preguntas: <b>dónde se juega</b>, "
                "<b>cuánto dura</b> y <b>con qué probabilidad termina en remate o gol</b>. "
                "Todo lo demás del informe son respuestas a esas tres preguntas."),
        M.fig("fig1", "Las tres preguntas de una posesión",
              "Esquema. La cancha está partida en 20 zonas; el equipo analizado ataca "
              "hacia la derecha.", None),
        M.plegable("Definiciones", DEF_POSESION, capa=None),
    ]


def a1_cadena(M: Modelo):
    return [
        M.frase("C", "La posesión se mueve de estado en estado. Un estado es una zona de la "
                "cancha junto con la fase del juego. Mientras la posesión sigue viva, pasa "
                "entre estados <b>transitorios</b>; cuando termina en remate, gol o pérdida, "
                "cae en un estado <b>absorbente</b> del que ya no sale."),
        *a1_clases(M),
        M.fig("cadena", "Transitorios y absorbentes",
              "Esquema: cuatro estados vivos que se pasan el balón y tres salidas sin "
              "regreso.", None),
        M.plegable("La matriz de la cadena", DEF_MARKOV, capa=None),
    ]


def a1_clases(M: Modelo):
    """ADR-61 §0 (D61-0): la fase es la del origen de la posesión y no cambia, así
    que la cadena se parte en cuatro bloques. Hasta h2_34 aquí se decía que todos
    los estados vivos se comunicaban: era falso."""
    sup = M.J.get("sup")
    if not sup:
        return [M.hueco(1, "La estructura de clases de la cadena sale de <b>supervivencia_v1.json</b> (" +
                        esc(FUENTES["sup"][1]) + ").")]
    f = sup["fase"]
    F = "supervivencia_v1 › fase"
    return [
        M.frase("C", "Una posesión conserva la fase con la que empezó: de " +
                M.c(f"{f['n']:,}".replace(",", " "), F + " › n") + " pasos entre estados vivos de la "
                "liga, " + M.c(str(f["cambian"]), F + " › cambian") + " cambian de fase. Por eso la "
                "cadena se parte en cuatro bloques que no se comunican; dentro de cada bloque, las "
                "zonas sí. Cada final es una clase cerrada: la distribución estacionaria de la cadena "
                "completa es trivial (todo acaba en un final) y lo que interesa es dónde vive una "
                "posesión <i>mientras sigue viva</i>, la distribución cuasi-estacionaria."),
        M.nota("Corrección (ADR-61 §0): hasta la versión anterior esta frase decía que todos los "
               "estados vivos se comunicaban entre sí. No es así, porque la fase describe cómo empezó "
               "la posesión. Nada de lo medido cambia; solo esta frase."),
    ]


FASE_ES = {"open": "juego abierto", "transition": "transición",
           "restart": "reinicio (saque de banda o de meta)", "set_piece": "balón parado"}
FRANJA_Y = ["banda izquierda", "centro-izquierda", "centro-derecha", "banda derecha"]
COLUMNA_X = ["cerca de su portería", "en su mitad", "en el medio", "en campo rival",
             "en la franja del área rival"]


def zona_txt(z: int) -> str:
    ix, iy = divmod(int(z), 4)
    return f"{FRANJA_Y[iy]}, {COLUMNA_X[ix]}"


def matriz(v):
    return [[v[ix * 4 + iy] for iy in range(4)] for ix in range(5)]


def a1_viva(M: Modelo):
    M.need("sup")
    l = M.J["sup"]["liga_16"]
    F = "supervivencia_v1 › liga_16"
    pi = l["pi"]
    zm = max(range(len(pi)), key=lambda i: pi[i])
    lb = l["lambda_bloques"]
    fmax = max(lb, key=lambda k: lb[k])
    return [
        M.frase("C", "Si una posesión de juego abierto sobrevive muchas acciones, deja de importar "
                "dónde empezó: se reparte siempre igual sobre la cancha. En la liga del torneo " +
                M.c(l["torneo"], F + " › torneo") + " (el de más posesiones, " +
                M.c(f"{l['n_poss']:,}".replace(",", " "), F + " › n_poss") + "), esa distribución "
                "se concentra en " + M.c(zona_txt(zm), F + " › pi (zona de más masa)") + ", con " +
                M.c(m_pct(pi[zm]), F + " › pi") + ". A una posesión así le quedan, en promedio, " +
                M.c(m_num(l["vida"], 1), F + " › vida") + " acciones."),
        M.fig("viva", "Dónde vive una posesión viva, paso a paso",
              "Juego abierto, liga completa. Al empezar, las posesiones están donde arrancan; paso "
              "a paso se acomodan en la distribución cuasi-estacionaria, que ya no cambia.",
              {"frames": l["frames"], "pi": pi, "torneo": l["torneo"]}),
        M.frase("C", "Los cuatro bloques no terminan al mismo ritmo: el que más tarda en terminar "
                "es el de " + M.c(FASE_ES.get(fmax, fmax), F + " › lambda_bloques") + ", con λ₁ = " +
                M.c(m_num(lb[fmax], 3), F + f" › lambda_bloques.{fmax}") + ". A la larga, la "
                "cuasi-estacionaria de la cadena completa vive en ese bloque."),
        M.plegable("La cuenta", "<p>π es el vector propio izquierdo de <i>Q</i> del bloque de juego "
                   "abierto con el valor propio más grande, λ₁ (Perron–Frobenius): π<i>Q</i> = λ₁π. "
                   "Se verifica iterando: cada paso multiplica la distribución por <i>Q</i> y la "
                   "renormaliza, desde donde empiezan las posesiones. Las acciones que le quedan a una posesión "
                   "que ya duró mucho son 1/(1 − λ₁); no es la duración media, que se mide desde "
                   "el inicio (ADR-61 §3).</p>", capa=None),
    ]


def a1_estimacion(M: Modelo):
    return [
        M.frase("C", "Una zona poco visitada da probabilidades ruidosas. Por eso cada "
                "probabilidad se encoge hacia la de los rivales de la liga: con muchos "
                "datos manda el equipo, con pocos manda la liga. Las magnitudes que se "
                "publican van sin encoger; el encogimiento solo se usa para decidir si una "
                "diferencia es real (ADR-22)."),
        M.fig("estimacion", "Del conteo a la probabilidad",
              "Esquema, sin datos: la barra de la izquierda es lo observado, la de en medio "
              "la referencia de la liga, la de la derecha lo que se usa para el contraste.",
              None),
    ]


def a1_confianza(M: Modelo):
    return [
        M.frase("C", "Cada frase del informe lleva un color. <b>Verde</b>: probado (un "
                "contraste escrito antes de medir que sobrevive a la corrección por muchas "
                "comparaciones). <b>Ámbar</b>: medido contra la liga del mismo torneo, con "
                "intervalo. <b>Gris</b>: descriptivo. Una frase lleva un solo color."),
        M.fig("semaforo", "El semáforo", "Un nulo va en verde: es un contraste probado que "
              "no encontró diferencia, y dice hasta qué tamaño la descarta.", None),
    ]


def a1_deriva(M: Modelo):
    M.need("h4", "der")
    h4, der = M.J["h4"], M.J["der"]
    ft = h4["firma_temporal"]
    F = "did_h4_v1 › firma_temporal"
    serie = sorted(der["por_torneo"], key=lambda r: r["torneo_orden"])
    return [
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
    ]


def a1_simular(M: Modelo):
    return [
        M.frase("C", "La simulación de posesiones (componente 06, opcional) no se incluye: "
                "la cadena de Markov no reproduce la distribución de longitudes, y simular "
                "desde ella arrastraría ese sesgo (ADR-21)."),
        *a1_curva(M),
    ]


def a1_curva(M: Modelo):
    sup = M.J.get("sup")
    if not sup:
        return [M.hueco(2, "La curva de supervivencia observada contra la de la cadena sale de "
                        "<b>supervivencia_v1.json</b> (" + esc(FUENTES["sup"][1]) + ").")]
    sv = sup["supervivencia"]
    F = "supervivencia_v1 › supervivencia"
    t = next(x for x in sv["por_torneo"] if x["torneo"] == sv["torneo_figura"])
    return [
        M.frase("C", "Torneo por torneo, para no mezclar la deriva del proveedor: la proporción de "
                "posesiones que siguen vivas tras " + M.c("12", "ADR-61 §4 (k fijado de antemano)") +
                " acciones queda por encima de la que predice la cadena en " +
                M.c(f"{sv['encima_12']} de {sv['de']}", F + " › encima_12") + " torneos, y por debajo "
                "tras " + M.c("5", "ADR-61 §4 (k fijado de antemano)") + " en " +
                M.c(f"{sv['debajo_5']} de {sv['de']}", F + " › debajo_5") + ". Hay más posesiones "
                "muy largas y menos medianas de las que la cadena espera."),
        M.fig("superv", "Posesiones que siguen vivas, observadas contra la cadena",
              "Torneo con más posesiones. Proporción de posesiones que superan cada número de "
              "acciones, entre las de al menos dos (el filtro de la cadena).",
              {"t": t["torneo"], "obs": t["S_obs"], "mod": t["S_mod"], "ks": t["ks"]}),
    ]


# ---------------------------------------------------------------------------
# ACTO 2 · cómo juega (por historia; era principal)
# ---------------------------------------------------------------------------
def s21(M: Modelo, H):
    M.need("h4")
    J, c, club = M.J, H["coach"], H["principal"]
    u = unidad(J, "h4", club, c)
    Fu = f"did_h4_v1 › unidades[{club}, {ape(c)}]"
    r, ic = u["rel_E_T_vs_liga"], u["rel_E_T_vs_liga_ic95"]
    if H["id"] == JARDINE:
        exige(ic[0] > 0, "2.1: la posesión de Jardine ya no está por encima de la liga")
    val = M.c(f_pct(r), Fu + " › rel_E_T_vs_liga", "PosJ")
    ivl = M.ic(ic, f_pct, Fu + " › rel_E_T_vs_liga_ic95", "PosJic")
    base = f"Bajo {ape(c)}, las posesiones {del_(club)} "
    s = direccion(ic)
    if s > 0:
        txt = (base + "duraron " + val + " más que las de la liga en los mismos torneos" +
               ivl + ", medido en acciones por posesión.")
    elif s < 0:
        txt = (base + "fueron más cortas que las de la liga en los mismos torneos: " + val +
               ivl + ", medido en acciones por posesión.")
    else:
        txt = (base + "no se separan de la liga en los mismos torneos: " + val + ivl +
               "; si hay diferencia, es menor a " +
               M.c(m_pct(margen(ic)), Fu + " › rel_E_T_vs_liga_ic95 (extremo más lejano al cero)") + ".")
    filas = []
    for e in H["eras"]:
        uu = unidad_o_none(J, "h4", e["club"], c)
        if uu:
            filas.append({"era": e["club"], "n": e["n"], "v": uu["rel_E_T_vs_liga"],
                          "ic": uu["rel_E_T_vs_liga_ic95"], "principal": e["club"] == club})
    B = [
        M.frase("B", txt, portada=1),
        M.fig("eras_pos", f"Duración de la posesión contra la liga, en cada club de {ape(c)}",
              "Diferencia relativa con su intervalo. La era principal va primero en el texto.",
              filas),
        M.fig("fig2", f"Dónde vive {el_(club)} de {ape(c)}",
              "Porcentaje de las acciones de la cadena en cada zona.", zonas_de(J, club, c)),
        *s21_viva(M, H),
        M.ejemplo("Una posesión " + del_(club) + f" de {ape(c)} tuvo de media " +
                  M.c(m_num(u["E_T"], 1), Fu + " › E_T") + " acciones; la de la liga en los "
                  "mismos torneos, " + M.c(m_num(u["E_T_base"], 1), Fu + " › E_T_base") + "."),
        plegable_fuente(M, "Cómo lo medimos", [
            "Duración esperada de la posesión, <i>E[T] = N·1</i>, en acciones, con la matriz "
            "fundamental de la cadena (primer acto).",
            "Se compara contra la liga del mismo torneo, sin los partidos del club. El "
            "intervalo sale de " + M.c(str(u["replicas_validas"]), Fu + " › replicas_validas") +
            " réplicas bootstrap por partido. Nivel B: no pertenece a una familia corregida."],
            [Fu + " › rel_E_T_vs_liga", Fu + " › rel_E_T_vs_liga_ic95"]),
    ]
    return B


def era_prog(J, H):
    e = next((x for x in J["prog"]["eras"] if x.get("hid") == H["id"]), None)
    if e is None:
        return None
    if e["club"] != H["principal"] or e["coach"] != H["coach"]:
        sys.exit(f"progresion_v1: la era de {H['id']} es {e['club']} y la página dice {H['principal']}")
    return e


def s21_viva(M: Modelo, H):
    if not M.J.get("prog"):
        return [M.nota("Dónde vive una posesión viva de esta era sale de <b>progresion_v1.json</b> (" +
                       esc(FUENTES["prog"][1]) + ").")]
    e = era_prog(M.J, H)
    cq = e["cuasi"] if e else None
    if not cq or not cq["evaluable"]:
        return [M.nota("La distribución cuasi-estacionaria de esta era no es evaluable: el bloque de "
                       "juego abierto no conecta todas las zonas (ADR-61 §3).")]
    F = f"progresion_v1 › eras[{H['id']}].cuasi"
    a, b = cq["era"], cq["base"]
    za = max(range(20), key=lambda i: a["pi"][i])
    zb = max(range(20), key=lambda i: b["pi"][i])
    return [
        M.frase("C", f"En juego abierto, una posesión larga {del_(H['principal'])} de {ape(H['coach'])} "
                "se concentra en " + M.c(zona_txt(za), F + ".era.pi (zona de más masa)") + " (" +
                M.c(m_pct(a["pi"][za]), F + ".era.pi") + "); en la liga de los mismos torneos, en " +
                M.c(zona_txt(zb), F + ".base.pi (zona de más masa)") + " (" +
                M.c(m_pct(b["pi"][zb]), F + ".base.pi") + "). A esas posesiones les quedan en promedio " +
                M.c(m_num(a["vida"], 1), F + ".era.vida") + " acciones; en la liga, " +
                M.c(m_num(b["vida"], 1), F + ".base.vida") + "."),
        M.fig("viva_era", "Dónde vive una posesión viva: la era y la liga",
              "Distribución cuasi-estacionaria del bloque de juego abierto. Misma escala en las dos "
              "canchas.", {"era": matriz(a["pi"]), "base": matriz(b["pi"]),
                           "etq": [f"{H['principal']} · {ape(H['coach'])}", "liga, mismos torneos"]}),
    ]


def s22(M: Modelo, H):
    M.need("prog")
    J, c, club = M.J, H["coach"], H["principal"]
    P = J["prog"]
    e = era_prog(J, H)
    if e is None:
        return [M.hueco(1, f"progresion_v1.json no trae la era principal de {ape(c)}.")]
    Fe = f"progresion_v1 › eras[{H['id']}]"
    B = []
    L, T = e["L"], e["tau"]
    if L["evaluable"]:
        B.append(frase_contraste(
            M, f"Con {ape(c)}, una posesión {del_(club)} que empieza fuera de la franja del área "
            "llega a ella antes de terminar con probabilidad " + M.c(m_pct(L["era"]), Fe + " › L.era") +
            "; la liga de los mismos torneos, desde los mismos puntos de partida, " +
            M.c(m_pct(L["base"]), Fe + " › L.base") + ". Diferencia relativa:",
            L["rel"], L["ic95_rel"], L["q"], L["rechaza"], f_pct, m_pct, Fe + " › L.rel"))
    else:
        B.append(M.hueco(1, "La probabilidad de llegar no es evaluable para esta era: " +
                         M.c(str(L["replicas_no_finitas"]), Fe + " › L.replicas_no_finitas") +
                         " réplicas sin llegadas (ADR-61 §2)."))
    if T["evaluable"]:
        B.append(frase_contraste(
            M, "Cuando llega, tarda " + M.c(m_num(T["era"], 1), Fe + " › tau.era") + " acciones; la "
            "liga, " + M.c(m_num(T["base"], 1), Fe + " › tau.base") + ". Diferencia relativa:",
            T["rel"], T["ic95_rel"], T["q"], T["rechaza"], f_pct, m_pct, Fe + " › tau.rel"))
    else:
        B.append(M.hueco(1, "El tiempo hasta llegar no es evaluable para esta era: " +
                         M.c(str(T["replicas_no_finitas"]), Fe + " › tau.replicas_no_finitas") +
                         " réplicas sin llegadas (ADR-61 §2)."))
    filas = []
    for x in P["eras"]:
        fila = {"etq": f"{x['club']} · {ape(x['coach'])}", "mia": x["hid"] == H["id"]}
        for k in ("L", "tau"):
            y = x[k]
            fila[k] = ({"v": y["rel"], "ic": y["ic95_rel"], "q": y["q"], "r": y["rechaza"]}
                       if y["evaluable"] else None)
        filas.append(fila)
    B.append(M.fig("prog", "Llegar a la franja del área: las cinco eras principales",
                   "Diferencia relativa contra la liga de los mismos torneos, con su intervalo. Punto "
                   "lleno: sobrevive a la corrección.", filas))
    j = e.get("jugada")
    if j:
        B.append(M.ejemplo("Una posesión real, elegida por regla y no por ser vistosa (la que tarda en "
                           "llegar lo más parecido a la media redondeada, " +
                           M.c(str(j["objetivo"]), Fe + " › jugada.objetivo") + "): el " +
                           M.c(j["fecha"], Fe + " › jugada.fecha") + ", " + el_(club) + " llegó a la "
                           "franja del área en " + M.c(str(j["acciones"]), Fe + " › jugada.acciones") +
                           " acciones, en " + M.c(FASE_ES.get(j["fase"], j["fase"]), Fe + " › jugada.fase") + "."))
        B.append(M.fig("jugada", "La posesión, zona por zona",
                       "Cada punto es una acción; el número es su orden. Toca un punto para ver quién "
                       "la hizo.", j))
    else:
        B.append(M.hueco(3, "No hay jugada de ejemplo: el tiempo hasta llegar no se pudo calcular."))
    s3 = e["sens_ix3"]
    fam = P["familia"]
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        "<b>Franja del área</b>: " + M.cita(P["parametros"]["franja"], "progresion_v1 › parametros.franja") + ".",
        "<b>Estimandos</b>: <i>L</i> = probabilidad de llegar a la franja antes de que la posesión "
        "termine, y τ = acciones hasta llegar, entre las que llegan. Solo cuentan las posesiones que "
        "empiezan fuera de la franja, y la liga se evalúa desde los puntos de partida de la era.",
        "<b>Comparación</b>: diferencia en logaritmos contra la liga sin el club, en los mismos torneos "
        "y con su misma mezcla. Intervalo basic con " + M.c(str(L["replicas_validas"]), Fe + " › L.replicas_validas") +
        " réplicas bootstrap por partido (en la duración de la posesión, arriba, el remuestreo es por posesión).",
        "<b>Familia</b>: " + M.c(str(fam["m"]), "progresion_v1 › familia.m") + " contrastes (cinco eras × "
        "dos estimandos), BH al 5%; rechazan " + M.c(str(fam["n_rechazados"]), "progresion_v1 › familia.n_rechazados") + ".",
        "<b>Sensibilidad</b> (nivel C, fuera de la familia): con las dos últimas columnas como franja, "
        "la era llega con probabilidad " + M.c(m_pct(s3["era"]), Fe + " › sens_ix3.era") + " y la liga " +
        M.c(m_pct(s3["base"]), Fe + " › sens_ix3.base") + "."],
        [Fe + " › L", Fe + " › tau", "progresion_v1 › familia"]))
    p4 = next((p for p in P["predicciones"] if p["n"] == 4), None)
    if p4 and p4.get("puntos"):
        B.append(M.fig("p4", "Llegar no es durar: la llegada contra la duración (P4)",
                       "Cada punto es una era principal: diferencia de llegada (vertical) contra "
                       "diferencia de duración de ADR-53 (horizontal).",
                       {**p4, "puntos": [{**q, "nom": ape(dict(HISTORIAS)[q["hid"]])} for q in p4["puntos"]]}))
    return B


METRICAS_B = [  # clave, prefijo de la frase, título corto, unidad, fmt, fmt del margen
    ("prog_pases", "Progresión: ", "pases progresivos", "pases progresivos por partido",
     lambda v: f_num(v, 1), lambda v: m_num(v, 1)),
    ("npxg_favor", "Ocasiones (la liga genera {liga} npxG sin penales por partido): ", "npxG a favor",
     "npxG por partido", f_num, m_num),
    ("obv_favor", "Valor de las acciones: ", "OBV a favor", "OBV a favor por partido", f_num, m_num),
    ("field_tilt", "Dominio territorial: field tilt ", "field tilt", "", f_pp, m_pp),
]


def s23(M: Modelo, H):
    M.need("met")
    J, c, club = M.J, H["coach"], H["principal"]
    g = unidad(J, "met", club, c)["global"]
    Fm = f"metricas_v1 › unidades[{club}, {ape(c)}] › global"
    if H["id"] == JARDINE:
        for k in ("prog_pases", "npxg_favor", "obv_favor", "field_tilt"):
            exige(g[k]["ic95"][0] > 0, f"2.3: {k} ya no está por encima de la liga")
    B, tarjetas = [], []
    for k, etq, corto, uni, fmt, fm in METRICAS_B:
        d = g[k]
        claves = ("FtJ", "FtJic") if k == "field_tilt" else ("", "")
        if "{liga}" in etq:
            etq = etq.format(liga=M.c(f_num(J["met"]["liga"]["media"]["npxg_favor"], 2, signo=False),
                                      "metricas_v1 › liga.media.npxg_favor"))
        txt = (etq + M.c(fmt(d["dif"]), f"{Fm} › {k}.dif", claves[0]) +
               (f" {uni}" if uni else "") + M.ic(d["ic95"], fmt, f"{Fm} › {k}.ic95", claves[1]) +
               cola_B(M, d["ic95"], f"{Fm} › {k}", fm))
        B.append(M.frase("B", txt + ".", portada=2 if k == "field_tilt" else None))
        tarjetas.append({"k": k, "t": corto, "v": d["dif"], "ic": d["ic95"],
                         "u": "pp" if k == "field_tilt" else "num"})
    x, f = g["npxg_favor"], g["field_tilt"]
    B += [
        M.fig("tarjetas", "Con el balón, contra la liga del mismo torneo",
              "Cada tarjeta: la diferencia con la liga y su intervalo. La línea vertical "
              "es la liga.", tarjetas),
        M.ejemplo(f"En un partido típico, {el_(club)} de {ape(c)} generó " +
                  M.c(m_num(x["era"]), f"{Fm} › npxg_favor.era") + " npxG sin penales; la liga, " +
                  M.c(m_num(x["liga"]), f"{Fm} › npxg_favor.liga") + ". Su parte de las acciones "
                  "en el último tercio fue " + M.c(f"{f['era'] * 100:.0f}%", f"{Fm} › field_tilt.era") +
                  ", contra " + M.c(f"{f['liga'] * 100:.0f}%", f"{Fm} › field_tilt.liga") +
                  " de la liga."),
    ]
    rg = J["met"].get("reglas", {})
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        M.cita(rg.get("D59P-1", "—"), "metricas_v1 › reglas.D59P-1"),
        M.cita(rg.get("D59P-3", "—"), "metricas_v1 › reglas.D59P-3"),
        M.cita(rg.get("D59P-5", "—"), "metricas_v1 › reglas.D59P-5"),
        "Comparación: " + M.cita(rg.get("D59P-comparacion", "—"), "metricas_v1 › reglas.D59P-comparacion") +
        ". Incertidumbre: " + M.cita(rg.get("D59P-incertidumbre", "—"), "metricas_v1 › reglas.D59P-incertidumbre") +
        ". Nivel B."],
        [f"{Fm} › <métrica>.dif", f"{Fm} › <métrica>.ic95"]))
    return B


def s24(M: Modelo, H):
    M.need("met")
    J, c, club = M.J, H["coach"], H["principal"]
    g = unidad(J, "met", club, c)["global"]
    Fm = f"metricas_v1 › unidades[{club}, {ape(c)}] › global"
    d = g["npxg_contra"]
    if H["id"] == JARDINE:
        exige(d["ic95"][1] < 0, "2.4: el npxG concedido ya no está por debajo de la liga")
    B = [M.frase("B", f"Bajo {ape(c)}, {el_(club)} concedió " +
                 M.c(f_num(d["dif"]), Fm + " › npxg_contra.dif") +
                 " npxG por partido" +
                 M.ic(d["ic95"], f_num, Fm + " › npxg_contra.ic95") +
                 cola_B(M, d["ic95"], Fm + " › npxg_contra", m_num) + ".", portada=3)]
    conc = []
    for e in H["eras"]:
        uu = unidad_o_none(J, "met", e["club"], c)
        if uu:
            conc.append({"era": e["club"], "n": e["n"], "v": uu["global"]["npxg_contra"]["dif"],
                         "ic": uu["global"]["npxg_contra"]["ic95"], "principal": e["club"] == club})
    figs = [M.fig("concedido", f"npxG concedido contra la liga, en cada club de {ape(c)}",
                  "Por debajo del cero: concede menos que la liga.", conc)]

    # presión (ADR-54): solo en los clubes que midió
    pres = J.get("pres")
    if pres is None:
        B.append(M.hueco(1, "Presión: falta <b>did_presion_v1.json</b> (" +
                         esc(FUENTES["pres"][1]) + ")."))
    else:
        medidos = set(pres["parametros"]["clubes"])
        clubes = [e["club"] for e in H["eras"] if e["slug"] in medidos]
        if not clubes:
            B.append(M.hueco(1, "Presión: ADR-54 la midió en seis clubes (" +
                             M.cita(", ".join(pres["parametros"]["clubes"]),
                                    "did_presion_v1 › parametros.clubes") +
                             f"); ninguna era de {ape(c)} está en ellos."))
        else:
            B += presion(M, H, pres, clubes, figs)
    B += figs
    B.append(M.ejemplo(f"En un partido típico, {el_(club)} de {ape(c)} concedió " +
                       M.c(m_num(d["era"]), Fm + " › npxg_contra.era") +
                       " npxG sin penales; la liga, " +
                       M.c(m_num(d["liga"]), Fm + " › npxg_contra.liga") + "."))
    partes = ["npxG concedido: la suma del xG sin penales del rival, contra la liga del mismo "
              "torneo (nivel B)."]
    if pres is not None:
        rp = pres.get("reglas_preinscritas", {})
        partes += ["Presión, E2: probabilidad de que una acción del rival se haga bajo "
                   "presión, <b>por acción del rival</b>, no por posesión (15_REPORTE_HTML §8). "
                   "Diferencia en diferencias entre dos eras del mismo club, cada una contra "
                   "la liga del mismo torneo.",
                   "Familia: " + M.cita(rp.get("D54-1", "—"), "did_presion_v1 › reglas_preinscritas.D54-1") +
                   ". " + M.cita(rp.get("D54-3", "—"), "did_presion_v1 › reglas_preinscritas.D54-3") + "."]
    B.append(plegable_fuente(M, "Cómo lo medimos", partes,
                             [Fm + " › npxg_contra", "did_presion_v1 › pares[] › contrastes.E2.did"]))
    return B


def presion(M: Modelo, H, pres, clubes, figs) -> list:
    c = H["coach"]
    ps = pares_de(pres["pares"], clubes)
    fr, ctrl, bosque_, e4 = [], [], [], []
    guard = {}
    for p in ps:
        a, b, club = p["a"], p["b"], p["club"]
        d = p["contrastes"]["E2"]["did"]
        F = f"did_presion_v1 › pares[{club}, {ape(a)}–{ape(b)}] › contrastes.E2.did"
        bosque_.append({"par": f"{ape(a)} – {ape(b)}", "club": club, "t": d["theta"],
                        "ic": d["ic95"], "q": d["q"], "r": d["rechaza"]})
        guard[(club, a, b)] = d
        con = c in (a, b)
        if con:
            otro = b if a == c else a
            claves = (("PresJO", "PresJOic", "", "PresMargen")
                      if H["id"] == JARDINE and club == CLUB_J and otro == "Fernando Ortiz"
                      else ("", "", "", ""))
            etq = (f"Presión (E2, por acción del rival), {ape(a)} frente a {ape(b)} "
                   f"{en_(club)} ({ape(otro)} llegó {cuando(M.J, H, otro, club)}):")
            fr.append(frase_contraste(M, etq, d["theta"], d["ic95"], d["q"], d["rechaza"],
                                      f_pp, m_pp, F, claves))
            if "E4" in p["contrastes"]:
                e4.append((f"{ape(a)} frente a {ape(b)}", p["contrastes"]["E4"]["did"],
                           f"did_presion_v1 › pares[{club}, {ape(a)}–{ape(b)}] › contrastes.E4.did"))
        elif d["rechaza"]:
            ctrl.append(M.frase("A", f"Lo que el método sí detecta en el mismo club: {en_(club)}, "
                              f"{ape(a)} frente a {ape(b)}, " +
                              M.c(f_pp(d["theta"]), F) + M.ic(d["ic95"], f_pp, F + ".ic95") +
                              M.q(d["q"], F + ".q") + ". Difiere."))
    fr += ctrl
    if H["id"] == JARDINE:
        jo = guard.get((CLUB_J, FOCO, "Fernando Ortiz"))
        js = guard.get((CLUB_J, FOCO, "Santiago Solari"))
        ox = guard.get((CLUB_J, "Fernando Ortiz", "Santiago Solari"))
        exige(jo is not None and js is not None and ox is not None,
              "2.4: faltan pares de presión del América")
        exige(not jo["rechaza"] and not js["rechaza"], "2.4: una presión de Jardine ahora sobrevive a BH")
        exige(js["ic95"][0] * js["ic95"][1] > 0, "2.4: el IC Jardine–Solari ya cruza el cero; cambia la redacción")
        exige(ox["rechaza"] and ox["theta"] > 0, "2.4: Ortiz–Solari ya no difiere (A)")
    if e4:
        sob = [t for t, d, _ in e4 if d["rechaza"]]
        fr.append(M.frase("C", "Transiciones: sin tiempo en segundos, el informe usa un "
                          "sustituto declarado, E4 (posesiones rivales de una sola acción en "
                          "juego abierto). " + "; ".join(
                              f"{t} " + M.c(f_pp(d["theta"]), F) for t, d, F in e4) +
                          (". Ninguno sobrevive a la corrección." if not sob else
                           ". Sobreviven a la corrección: " + ", ".join(sob) + ".")))
    figs.append(M.fig("fig3b", "Presión en los clubes de la historia, por pareja",
                      "E2: nivel de presión por acción del rival, en puntos porcentuales. "
                      "Punto lleno: sobrevive a la corrección; aro: no.", bosque_))
    return fr


def s25(M: Modelo, H):
    M.need("h4", "met")
    J, c, club = M.J, H["coach"], H["principal"]
    u = unidad(J, "h4", club, c)
    m = unidad(J, "met", club, c)["por_torneo"]
    ts = [t for t in torneos_orden(J) if t in u["serie_por_torneo"]]
    serie = [{"t": t, "pos": u["serie_por_torneo"][t]["rel_E_T"],
              "n": u["serie_por_torneo"][t]["n_poss"],
              "ft": m[t]["field_tilt"]["percentil"] if t in m and not m[t]["parcial"] else None,
              "xg": m[t]["npxg_favor"]["percentil"] if t in m and not m[t]["parcial"] else None}
             for t in ts]
    F = f"did_h4_v1 › unidades[{club}, {ape(c)}] › serie_por_torneo"
    Fm = f"metricas_v1 › unidades[{club}, {ape(c)}] › por_torneo"
    pos_txt = ", ".join(M.c(f_pct(s["pos"]), f"{F}.{s['t']}.rel_E_T") for s in serie)
    n_sobre = sum(s["pos"] > 0 for s in serie)
    n_bajo = sum(s["pos"] < 0 for s in serie)
    cierre = (". Todos por encima de la liga." if n_sobre == len(serie) else
              ". Todos por debajo de la liga." if n_bajo == len(serie) else
              ". Por encima de la liga en " + M.c(f"{n_sobre} de {len(serie)}", F) + ".")
    ft = [s["ft"] for s in serie if s["ft"] is not None]
    comp = [s for s in serie if s["xg"] is not None]
    if H["id"] == JARDINE:
        exige(len(comp) >= 2, "2.5: menos de dos torneos completos en metricas_v1")
    B = [M.frase("C", f"Posesión sobre la liga en los {M.c(str(len(serie)), F)} torneos, "
                 "en orden: " + pos_txt + cierre,
                 nota_adenda="ADR-59 la marcaba B; la serie por torneo no trae intervalo.")]
    if len(comp) >= 2:
        xg = [s["xg"] for s in comp]
        ult = comp[-1]
        B += [
            M.frase("C", "Field tilt entre el percentil " +
                    M.c(f"{min(ft):.2f}", Fm + " › field_tilt.percentil (mín)") + " y el " +
                    M.c(f"{max(ft):.2f}", Fm + " › field_tilt.percentil (máx)") +
                    " de la liga en los torneos completos."),
            M.frase("C", "npxG a favor entre el percentil " +
                    M.c(f"{min(xg[:-1]):.2f}", Fm + " › npxg_favor.percentil (mín, sin el último)") +
                    " y el " + M.c(f"{max(xg[:-1]):.2f}", Fm + " › npxg_favor.percentil (máx, sin el último)") +
                    " en los torneos completos anteriores, y " +
                    M.c(f"{ult['xg']:.2f}", f"{Fm}.{ult['t']}.npxg_favor.percentil") +
                    " en " + ult["t"] + ". Es la evolución observada; el informe no le "
                    "atribuye una causa."),
        ]
    else:
        B.append(M.hueco(1, "Percentiles de field tilt y npxG: la era tiene menos de dos "
                         "torneos completos en metricas_v1."))
    hi = max(serie, key=lambda s: s["pos"])
    lo = min(serie, key=lambda s: s["pos"])
    B += [
        M.fig("fig4", "Torneo a torneo, contra la liga",
              "Cambia la métrica con el selector. La línea punteada es la liga del "
              "mismo torneo.", serie),
        M.ejemplo(f"El torneo con las posesiones más largas respecto a la liga fue {hi['t']} (" +
                  M.c(f_pct(hi["pos"]), f"{F}.{hi['t']}.rel_E_T") + f"); el más bajo, {lo['t']} (" +
                  M.c(f_pct(lo["pos"]), f"{F}.{lo['t']}.rel_E_T") + ")."),
        plegable_fuente(M, "Cómo lo medimos", [
            "La serie por torneo repite la comparación de la duración, torneo por torneo. " +
            M.cita(J["h4"]["reglas_preinscritas"].get("D53-7", "—"),
                   "did_h4_v1 › reglas_preinscritas.D53-7") +
            ": sin intervalo, nivel C (adenda 1).",
            "Percentil: posición de la era entre los clubes de la liga en ese torneo; los "
            "torneos parciales no llevan percentil."],
            [F, Fm]),
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


def s26(M: Modelo, H):
    M.need("ctx")
    ctx = M.J["ctx"]
    c, club = H["coach"], H["principal"]
    liga = []
    for cx, (a, b, nomb) in CTX.items():
        for mk, (mn, uni) in MET.items():
            va, vb = ctx["liga"][cx][mk][a], ctx["liga"][cx][mk][b]
            liga.append({"ctx": nomb, "a": a, "b": b, "m": mn, "uni": uni,
                         "va": va, "vb": vb, "d": va - vb})
    # las eras del club principal que están en la familia casos (ADR-57)
    eras_club = [co for co, clubes in ctx["casos"].items() if club in clubes]
    if c not in eras_club:
        eras_club.insert(0, c)
    eras_club.sort(key=lambda co: (co != c, primer_torneo(M.J, club, co)))
    bosque_ = {}
    for co in eras_club:
        u = unidad(M.J, "ctx", club, co)
        filas = []
        for cx, (a, b, nomb) in CTX.items():
            for mk, (mn, uni) in MET.items():
                d = u["contrastes"][f"{cx}|{mk}"]
                filas.append({"ctx": nomb, "m": mk, "mn": mn, "uni": uni,
                              "t": d["theta"], "ic": d["ic95"],
                              "q": d.get("q_casos"), "r": bool(d.get("rechaza_casos"))})
        bosque_[co] = filas
    fj = bosque_[c]
    n_total = sum(len(v) for v in bosque_.values())
    n_rech = sum(f["r"] for v in bosque_.values() for f in v)
    excl = [f for f in fj if f["ic"][0] * f["ic"][1] > 0 and not f["r"]]
    F = f"contexto_v1 › unidades[{club}, *] › contrastes"

    def fx(f):
        return f_num(f["t"], 2) if f["uni"] == "num" else f_pp(f["t"])

    if H["id"] == JARDINE:
        exige(not any(f["r"] for f in fj), "2.6: un contraste de Jardine ahora sobrevive a BH")
    excl_txt = "; ".join(
        f'{f["ctx"]} · {f["mn"]} ' +
        M.c(fx(f), f"contexto_v1 › unidades[{club}, {ape(c)}] › contrastes.{f['ctx']}|{f['m']}.theta")
        for f in excl)
    etiq = (f"{el_(club)[0].upper()}{el_(club)[1:]}")
    B = [M.frase("C", "Lo que ajusta la liga entera: perdiendo contra ganando, en casa contra "
                 "fuera, antes y después del minuto 60, y ante rivales fuertes o débiles. "
                 "La tabla muestra los dos valores de cada contexto.",
                 nota_adenda="ADR-59 la marcaba B; contexto_v1 › liga no trae intervalo.")]
    if n_rech == 0:
        B.append(M.nulo(f"{etiq} ajusta al contexto como la liga: " +
                        M.c(f"{n_rech} de {n_total}", F + " › rechaza_casos "
                            f"({len(bosque_)} eras × 16)", "CtxRech") +
                        " contrastes sobreviven a la corrección. " +
                        (f"Bajo {ape(c)}, {M.c(str(len(excl)), F + ' (IC que excluye el cero)')} " +
                         ("intervalo excluye el cero antes de corregir y no sobrevive: "
                          if len(excl) == 1 else
                          "intervalos excluyen el cero antes de corregir y ninguno sobrevive: ") +
                         excl_txt + "." if excl else "")))
    else:
        rech = [(co, f) for co, v in bosque_.items() for f in v if f["r"]]
        B.append(M.frase("A", f"{en_(club)[0].upper()}{en_(club)[1:]}, " +
                         M.c(f"{n_rech} de {n_total}", F + " › rechaza_casos") +
                         " contrastes sobreviven a la corrección: " + "; ".join(
                             f"{ape(co)}, {f['ctx']} · {f['mn']} " +
                             M.c(fx(f), f"contexto_v1 › unidades[{club}, {ape(co)}] › contrastes.{f['ctx']}|{f['m']}.theta") +
                             M.q(f["q"], f"contexto_v1 › unidades[{club}, {ape(co)}] › contrastes.{f['ctx']}|{f['m']}.q_casos")
                             for co, f in rech) + ". Los demás no se distinguen del ajuste de la liga."))
    u = unidad(M.J, "ctx", club, c)
    ta = u.get("tasas", {})
    B += [
        M.fig("tabla5", "Lo que ajusta la liga", "Fuente: contexto_v1 › liga. Sin intervalo en "
              "el JSON: se muestra como descriptivo (adenda 1).", liga),
        M.fig("fig5", "Bosque de θ: cuánto ajusta cada era más allá de la liga",
              "θ = ajuste de la era menos ajuste de la liga en el mismo contexto. "
              "Aro: no sobrevive a la corrección. Cada nulo se lee por su extremo más lejano.",
              bosque_),
    ]
    if ta.get("marcador|M1|perdiendo") is not None and ta.get("marcador|M1|ganando") is not None:
        Ft = f"contexto_v1 › unidades[{club}, {ape(c)}] › tasas"
        B.append(M.ejemplo(f"Con {el_(club)} de {ape(c)} perdiendo, sus posesiones duraron " +
                           M.c(m_num(ta["marcador|M1|perdiendo"]), Ft + "[marcador|M1|perdiendo]") +
                           " acciones; ganando, " +
                           M.c(m_num(ta["marcador|M1|ganando"]), Ft + "[marcador|M1|ganando]") + "."))
    else:
        B.append(M.hueco(3, "La era no trae tasas por marcador en contexto_v1."))
    rg = ctx.get("reglas", {})
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        M.cita(rg.get("D56", "—"), "contexto_v1 › reglas.D56") + ".",
        "Familia: " + M.cita(rg.get("D57-2", "—"), "contexto_v1 › reglas.D57-2") +
        " (" + M.cita(rg.get("D57-1", "—"), "contexto_v1 › reglas.D57-1") + ").",
        "Bootstrap: " + M.cita(rg.get("D56-bootstrap", "—"), "contexto_v1 › reglas.D56-bootstrap") + "."],
        [F + "[<contexto>|<métrica>] › theta, ic95, q_casos, rechaza_casos"]))
    return B


def s27(M: Modelo, H):
    M.need("bp")
    bp = M.J["bp"]
    c, club = H["coach"], H["principal"]
    lg, mo = bp["liga"], bp["modelo"]
    u = unidad(M.J, "bp", club, c)
    Fl = "balon_parado_v2 › liga"
    Fu = f"balon_parado_v2 › unidades[{club}, {ape(c)}]"
    of, de = u["C1_of"], u["C1_def"]
    if H["id"] == JARDINE:
        exige(not (of.get("rechaza") or of["rechaza_casos"] or de.get("rechaza") or de["rechaza_casos"]),
              "2.7: el América ahora se separa de la liga en córners")
    exige(mo["delta_auc_ic95_percentil"][0] > 0, "2.7: ΔAUC ya no excluye el cero")
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
        M.frase("B", "Añadir la geometría del remate (portería libre, defensores) mejora "
                "la discriminación del modelo de xG en " +
                M.c(f"{mo['delta_auc']:+.3f}", "balon_parado_v2 › modelo.delta_auc", "Dauc") + " de AUC" +
                '<span class="tec"> ' + M.c(f"[{mo['delta_auc_ic95_percentil'][0]:+.3f}, "
                                            f"{mo['delta_auc_ic95_percentil'][1]:+.3f}]",
                                            "balon_parado_v2 › modelo.delta_auc_ic95_percentil") +
                "</span>. La portería queda libre en " +
                M.c(f"{lg['goal_open_medio']['corner']:.3f}", Fl + " › goal_open_medio.corner") +
                " de los remates de córner contra " +
                M.c(f"{lg['goal_open_medio']['juego_abierto']:.3f}",
                    Fl + " › goal_open_medio.juego_abierto") + " en juego abierto."),
    ]
    rech_of, rech_de = bool(of["rechaza_casos"]), bool(de["rechaza_casos"])
    if not rech_of and not rech_de:
        B.append(M.nulo(f"{el_(club)[0].upper()}{el_(club)[1:]} de {ape(c)} no se separa de la "
                        "liga en córners. A favor: " +
                        M.c(f_pp(of["did"]), Fu + " › C1_of.did") +
                        M.ic(of["ic95"], f_pp, Fu + " › C1_of.ic95") + "; en contra: " +
                        M.c(f_pp(de["did"]), Fu + " › C1_def.did") +
                        M.ic(de["ic95"], f_pp, Fu + " › C1_def.ic95") +
                        ". No detectamos una diferencia mayor a " +
                        M.c(m_pp(max(margen(of["ic95"]), margen(de["ic95"]))),
                            Fu + " › C1_of/C1_def.ic95 (extremo)") + "."))
    else:
        for lado, d, nm in (("of", of, "a favor"), ("def", de, "en contra")):
            B.append(frase_contraste(M, f"Córners {nm}, {el_(club)} de {ape(c)} contra la liga:",
                                     d["did"], d["ic95"], d["q_casos"], d["rechaza_casos"],
                                     f_pp, m_pp, f"{Fu} › C1_{lado}"))
    B += [
        M.fig("fig7", "Embudo del balón parado en la liga",
              "Cambia entre remate y gol con el selector.",
              [{"k": k, "n": n, "s": lg["P_S_secuencia"][k], "g": lg["P_G_secuencia"][k]}
               for k, n in tipos]),
        M.fig("fig7b", "Qué pesa en el xG de un remate",
              "Coeficientes estandarizados del modelo base, con IC 95%. A la izquierda "
              "del cero, menos xG.",
              [{"k": k, "b": mo["beta_base_estandarizado"][k],
                "ic": mo["beta_base_ic95"][k]} for k in ("dist_meta", "angulo", "cabeza")]),
        M.fig("remates", "Dónde remata y dónde le rematan",
              "Remates tras córner por zona del área. Fuente: balon_parado_v2 › "
              "unidades › descriptivos.",
              {"of": u["descriptivos"]["mapa_remates_of"],
               "def": u["descriptivos"]["mapa_remates_def"]}),
        M.nota("Las zonas de cada rival en los remates (Voronoi a favor y en contra) llegan en "
               "la fase F5."),
    ]
    if "corners_por_partido_of" in u:
        B.append(M.ejemplo(f"En un partido, {el_(club)} de {ape(c)} sacó " +
                           M.c(m_num(u["corners_por_partido_of"], 1), Fu + " › corners_por_partido_of") +
                           " córners y le sacaron " +
                           M.c(m_num(u["corners_por_partido_def"], 1), Fu + " › corners_por_partido_def") +
                           "; en toda la era, " + M.c(str(u["remates_of"]), Fu + " › remates_of") +
                           " remates tras córner a favor y " + M.c(str(u["remates_def"]), Fu + " › remates_def") +
                           " en contra."))
    else:
        B.append(M.hueco(3, "La era no trae córners por partido en balon_parado_v2."))
    rg = bp.get("reglas", {})
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        M.cita(rg.get("D55-1", "—"), "balon_parado_v2 › reglas.D55-1") + ".",
        M.cita(rg.get("D55-6", "—"), "balon_parado_v2 › reglas.D55-6") + ".",
        "Familia: los casos de ADR-57, corregidos juntos (" +
        M.c(str(bp.get("familia_casos", {}).get("m", "—")), "balon_parado_v2 › familia_casos.m") +
        " contrastes)."],
        [Fu + " › C1_of, C1_def", Fl]))
    return B


def s28(M: Modelo, H):
    M.need("jug")
    jug = M.J["jug"]
    c, club = H["coach"], H["principal"]
    u = unidad(M.J, "jug", club, c)
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
    Fa = f"jugadores_v1 › unidades[{club}, {ape(c)}] › A"
    Fc = f"jugadores_v1 › unidades[{club}, {ape(c)}] › C"
    if H["id"] == JARDINE:
        exige(not C["M2"]["rechaza_casos"] and not C["FT"]["rechaza_casos"],
              "2.8: el cambio tras el primer cambio ahora sobrevive a BH")
        exige(C["M2"]["ic95"][0] < 0 < C["M2"]["ic95"][1] and C["FT"]["ic95"][0] < 0 < C["FT"]["ic95"][1],
              "2.8: un IC tras el primer cambio ya no cruza el cero; cambia la redacción")
    B = []
    if completos:
        B.append(M.frase("C", "Rotación: la continuidad del once quedó en el " +
                         M.regla("cont_inferior", "15%") + " inferior de la liga en " +
                         M.c(f"{n_bajo} de {len(completos)}", Fa + " › percentil_continuidad", "RotJ") +
                         " torneos, y el número de jugadores que suman el 80% de los minutos (N80) "
                         "quedó por encima de la " + M.regla("n80_mediana", "mediana") +
                         " de la liga en " + M.c(f"{n_alto} de {len(completos)}", Fa + " › percentil_n80") +
                         ". Hay partidos fuera de estos datos (otras competiciones) que pueden "
                         "estar detrás de la rotación; no los medimos.",
                         nota_adenda="El umbral del N80 (mediana) lo fija la adenda; ADR-58 no lo fijaba.",
                         portada=4))
    else:
        B.append(M.hueco(1, "Rotación: la era no tiene torneos completos en jugadores_v1."))
    B.append(M.frase("C", "Roles: los cinco jugadores con más minutos, con su posición más "
                     "frecuente y dónde intervienen. Toca uno para ver su mapa."))
    B.append(M.nulo("Tras sus primeros cambios, el equipo no se movió de forma detectable: "
                    "remate " + M.c(f_pp(C["M2"]["theta"]), Fc + " › M2.theta") +
                    M.ic(C["M2"]["ic95"], f_pp, Fc + " › M2.ic95") + "; field tilt " +
                    M.c(f_pp(C["FT"]["theta"]), Fc + " › FT.theta") +
                    M.ic(C["FT"]["ic95"], f_pp, Fc + " › FT.ic95") +
                    ". No detectamos un cambio mayor a " +
                    M.c(m_pp(margen(C["M2"]["ic95"])), Fc + " › M2.ic95 (extremo)") +
                    " en remate ni a " +
                    M.c(m_pp(margen(C["FT"]["ic95"])), Fc + " › FT.ic95 (extremo)") +
                    " en field tilt.")
             if not (C["M2"]["rechaza_casos"] or C["FT"]["rechaza_casos"]) else
             frase_contraste(M, "Tras sus primeros cambios, field tilt:", C["FT"]["theta"],
                             C["FT"]["ic95"], C["FT"].get("q_casos"), C["FT"]["rechaza_casos"],
                             f_pp, m_pp, Fc + " › FT"))
    if (C["M2"]["rechaza_casos"] or C["FT"]["rechaza_casos"]):
        B.append(frase_contraste(M, "Tras sus primeros cambios, remate:", C["M2"]["theta"],
                                 C["M2"]["ic95"], C["M2"].get("q_casos"), C["M2"]["rechaza_casos"],
                                 f_pp, m_pp, Fc + " › M2"))
    B.append(M.frase("C", "En la liga, tras el primer cambio cuando el equipo va perdiendo: "
                     "remate " + M.c(f_pp(tl["M2"]["perdiendo"][0]),
                                     "jugadores_v1 › liga.Tactical.M2.perdiendo[0]") +
                     " y field tilt " + M.c(f_pp(tl["FT"]["perdiendo"][0]),
                                            "jugadores_v1 › liga.Tactical.FT.perdiendo[0]") + ".",
                     nota_adenda="ADR-59 la marcaba B; el JSON trae [delta, n], sin intervalo."))
    B += [
        M.fig("fig6", "Continuidad del once y N80, percentil en la liga",
              "Cada anillo es un torneo. Continuidad baja = más cambios en el once.", A),
        M.fig("roles", "Los cinco con más minutos", "Fuente: jugadores_v1 › B. Sin nombres: "
              "el JSON solo trae el identificador del jugador.",
              [{"id": b["player_id"], "pos": pos(b["posicion_modal"]), "min": b["minutos"],
                "acc": b["acciones"],
                "z": [b["zonas"][ix * NY:(ix + 1) * NY] for ix in range(NX)]} for b in top]),
        M.nota("La red de pases por posición llega en la fase F4 (ADR-62)."),
    ]
    if top:
        t0 = top[0]
        Fb = f"jugadores_v1 › unidades[{club}, {ape(c)}] › B[jugador {t0['player_id']}]"
        B.append(M.ejemplo("El jugador con más minutos (" + esc(pos(t0["posicion_modal"])) +
                           ") sumó " + M.c(f"{t0['minutos']:.0f}", Fb + " › minutos") +
                           " minutos y " + M.c(str(t0["acciones"]), Fb + " › acciones") +
                           " acciones en los " + M.c(str(u["n_partidos"]),
                                                     f"jugadores_v1 › unidades[{club}, {ape(c)}] › n_partidos") +
                           " partidos de la era."))
    else:
        B.append(M.hueco(3, "La era no trae jugadores con minutos suficientes en jugadores_v1."))
    rg = jug.get("reglas", {})
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        M.cita(rg.get("D58-A", "—"), "jugadores_v1 › reglas.D58-A") + ".",
        M.cita(rg.get("D58-B", "—"), "jugadores_v1 › reglas.D58-B") + ".",
        M.cita(rg.get("D58-C", "—"), "jugadores_v1 › reglas.D58-C") + ".",
        "Familia: " + M.cita(rg.get("D58-familias", "—"), "jugadores_v1 › reglas.D58-familias") + "."],
        [Fa, Fc]))
    return B


# ---------------------------------------------------------------------------
# ACTO 3 · de dónde viene eso (por historia)
# ---------------------------------------------------------------------------
def rel_par(J, club, x, y):
    """La pareja de relevos_v1 (ADR-60) en ese club, en cualquier orden."""
    hall = [p for p in J["rel"]["pares"] if p.get("club") == club and {p["a"], p["b"]} == {x, y}]
    if len(hall) > 1:
        raise KeyError(f"relevos_v1: {len(hall)} parejas para {club}: {x} / {y}")
    return hall[0] if hall else None


def rel_de(J, H):
    """Parejas de F60 de la historia, en orden de club y de tiempo."""
    ps = [p for p in J["rel"]["pares"] if p.get("club") in H["clubes"] and H["coach"] in (p["a"], p["b"])]
    return sorted(ps, key=lambda p: (H["clubes"].index(p["club"]), primer_torneo(J, p["club"], p["a"]),
                                     primer_torneo(J, p["club"], p["b"])))


def f3(v):
    return f"{v:.3f}"


def fpct0(v):
    return f"{v * 100:.0f}%"


def frase_T(M: Modelo, r) -> dict:
    """ADR-60 §4: T es nivel A; un nulo se lee por el extremo superior del IC."""
    F = f"relevos_v1 › pares[{r['club']}, {ape(r['a'])}→{ape(r['b'])}]"
    base = (f"Uso del campo tras el relevo {ape(r['a'])} → {ape(r['b'])} {en_(r['club'])}: T = " +
            M.c(f3(r["T"]), F + " › T") + M.ic(r["ic95"]["T"], f3, F + " › ic95.T") +
            M.q(r["q"], F + " › q"))
    if r["rechaza"]:
        return M.frase("A", base + ". Cambió más de lo que da el azar al barajar los partidos.")
    return M.nulo(base + ". No detectamos un cambio en el uso del campo mayor a " +
                  M.c(f3(r["ic95"]["T"][1]), F + " › ic95.T[1] (extremo)") + ".")


CLAVES_H4 = {"Santiago Solari": ("SolJ", "SolJic", "SolJq", ""),
             "Fernando Ortiz": ("OrtJ", "OrtJic", "OrtJq", "OrtJmargen")}


def s31(M: Modelo, H):
    M.need("h4")
    J, c = M.J, H["coach"]
    ps = pares_de(J["h4"]["pares"], H["clubes"])
    propios = [p for p in ps if c in (p["a"], p["b"])]
    propios.sort(key=lambda p: (H["clubes"].index(p["club"]),
                                primer_torneo(J, p["club"], p["b"] if p["a"] == c else p["a"])))
    if H["id"] == JARDINE:
        pjs, _ = par(J["h4"]["pares"], CLUB_J, FOCO, "Santiago Solari")
        pjo, _ = par(J["h4"]["pares"], CLUB_J, FOCO, "Fernando Ortiz")
        es, eo = pjs["did"]["E_T"], pjo["did"]["E_T"]
        exige(es["rechaza_fdr"] and es["rel"] > 0, "3.1: Jardine–Solari ya no difiere (A)")
        exige(not eo["rechaza_fdr"], "3.1: Jardine–Ortiz ahora sobrevive a BH; ya no es un nulo")
    B = []
    for p in propios:
        a, b, club = p["a"], p["b"], p["club"]
        otro = b if a == c else a
        e = p["did"]["E_T"]
        F = f"did_h4_v1 › pares[{club}, {ape(a)}–{ape(b)}] › did.E_T"
        claves = (CLAVES_H4.get(otro, ("",) * 4)
                  if H["id"] == JARDINE and club == CLUB_J else ("",) * 4)
        etq = (f"Duración de la posesión, {ape(a)} frente a {ape(b)} {en_(club)} "
               f"({ape(otro)} llegó {cuando(J, H, otro, club)}):")
        B.append(frase_contraste(M, etq, e["rel"], e["ic95"], e["q"], e["rechaza_fdr"],
                                 f_pct, m_pct, F, claves))
        if J.get("rel"):
            r = rel_par(J, club, a, b)
            B.append(frase_T(M, r) if r else
                     M.hueco(1, f"La pareja {ape(a)}–{ape(b)} no está en relevos_v1.json."))
    if propios and J.get("rel"):
        # ADR-60 adenda 1 §2 y §4: qué dice el control y el placebo, sacado de los JSON
        cn = J["rel"]["control_negativo"]
        Fc = "relevos_v1 › control_negativo"
        B.append(M.frase("C", f"El control no aisló al técnico: {ape(cn['a'])} → {ape(cn['b'])} {en_(cn['club'])}, "
                         "el mismo técnico en el mismo club, da T = " + M.c(f3(cn["T"]), Fc + " › T") +
                         ", por encima del " + M.c("percentil 95", Fc + " › T_nula_p95 (cuantil 0.95 de la nula)") + " de su nula (" + M.c(f3(cn["T_nula_p95"]), Fc + " › T_nula_p95") +
                         "). Por eso un T que rechaza dice que el uso del campo cambió entre las dos eras, "
                         "no que lo cambió el técnico.", nota_adenda="Lectura fijada en la adenda 1 de ADR-60 tras el fallo del control.", adenda=1))
        if J.get("pla"):
            pl_ = J["pla"]
            Fp = "placebo_v1"
            B.append(M.frase("C", "Placebo exploratorio: partiendo cada era en dos mitades por fecha, el uso del "
                             "campo cambia con mediana T = " + M.c(f3(pl_["resumen"]["mediana"]), Fp + " › resumen.mediana") +
                             " y " + M.c("percentil 90", Fp + " › resumen.p90 (cuantil 0.9, adenda 1 §4)") + " de " + M.c(f3(pl_["resumen"]["p90"]), Fp + " › resumen.p90") + " sin "
                             "cambiar de técnico. " + M.c(f"{pl_['k']} de {pl_['de']}", Fp + " › k") +
                             " relevos quedan por encima de ese corte: " + esc(pl_["lectura_texto"]) + ".",
                             nota_adenda="Placebo definido en la adenda 1 de ADR-60 antes de calcularlo; lectura fijada de antemano.",
                             adenda=1))
        else:
            B.append(M.hueco(1, "El placebo de T sale de <b>placebo_v1.json</b> (" + esc(FUENTES["pla"][1]) + ")."))
    if propios and not J.get("rel"):
        B.append(M.hueco(1, "El cambio en el uso del campo (T, ADR-60) sale de <b>relevos_v1.json</b> (" +
                         esc(FUENTES["rel"][1]) + ")."))
    if not propios:
        B.append(M.hueco(1, f"No hay parejas del mismo club con {ape(c)} en did_h4_v1."))
    for club in H["clubes"]:
        despues = [p for p in ps if p["club"] == club and c in (p["a"], p["b"])
                   and cuando(J, H, p["b"] if p["a"] == c else p["a"], club) == "después"]
        if not despues and any(p["club"] == club for p in ps):
            B.append(M.frase("C", f"{en_(club)[0].upper()}{en_(club)[1:]} no hay una era analizable posterior a la de "
                             f"{ape(c)} dentro de los datos."))
    B += [
        M.fig("fig3", "Parejas del mismo club: corregido contra crudo",
              "Duración de la posesión, diferencia relativa. Punto lleno: comparación "
              "contra la liga del mismo torneo. Aro: la resta cruda, sin corregir la deriva.",
              [{"par": f"{ape(p['a'])} – {ape(p['b'])}", "club": p["club"],
                "did": p["did"]["E_T"]["rel"], "did_ic": p["did"]["E_T"]["ic95"],
                "q": p["did"]["E_T"]["q"], "rech": p["did"]["E_T"]["rechaza_fdr"],
                "cru": p["crudo"]["E_T"]["rel"], "cru_ic": p["crudo"]["E_T"]["ic95"],
                "cru_rech": p["crudo"]["E_T"]["rechaza_fdr"]} for p in ps]),
        M.nota("Qué parte del cambio viene del plantel y qué parte del uso lo contesta la sección siguiente."),
    ]
    if J.get("rel") and rel_de(J, H):
        B.append(M.fig("fig_T", "Cuánto cambió el uso del campo en cada relevo",
                       "T: distancia de variación total entre las ocupaciones en exceso de la liga "
                       "(cero: igual; uno: nada en común). Punto lleno: sobrevive a la corrección.",
                       {"filas": [{"par": f"{ape(r['a'])} → {ape(r['b'])}", "club": r["club"], "v": r["T"],
                                   "ic": r["ic95"]["T"], "q": r["q"], "r": r["rechaza"],
                                   "nula95": r.get("T_nula_p95")} for r in rel_de(J, H)],
                        "placebo90": J["pla"]["resumen"]["p90"] if J.get("pla") else None}))
    if propios:
        p = propios[0]
        Fp = f"did_h4_v1 › pares[{p['club']}, {ape(p['a'])}–{ape(p['b'])}]"
        B.append(M.ejemplo(f"Sin corregir la deriva, {ape(p['a'])} frente a {ape(p['b'])} "
                           f"{en_(p['club'])} daba " + M.c(f_pct(p["crudo"]["E_T"]["rel"]), Fp + " › crudo.E_T.rel") +
                           "; comparando cada era con la liga del mismo torneo, " +
                           M.c(f_pct(p["did"]["E_T"]["rel"]), Fp + " › did.E_T.rel") + "."))
    else:
        B.append(M.hueco(3, "Sin parejas, no hay ejemplo."))
    rg = J["h4"]["reglas_preinscritas"]
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        "Diferencia en diferencias: cada era contra la liga del mismo torneo, y luego una era "
        "contra la otra.",
        "Familia: " + M.cita(rg.get("D53-1", "—"), "did_h4_v1 › reglas_preinscritas.D53-1") +
        ", " + M.c(str(J["h4"]["n_pares"]), "did_h4_v1 › n_pares") + " pares. " +
        M.cita(rg.get("D53-3", "—"), "did_h4_v1 › reglas_preinscritas.D53-3") + ".",
        "Antes o después: según el primer torneo de cada era (" +
        M.cita("did_h4_v1 › unidades[].torneos", "did_h4_v1 › unidades[].torneos") + ")."] +
        ([M.cita(J["rel"]["reglas"]["D60-1"], "relevos_v1 › reglas.D60-1") + ". " +
          M.cita(J["rel"]["reglas"]["D60-2"], "relevos_v1 › reglas.D60-2") + ". Familia: " +
          M.cita(J["rel"]["reglas"]["D60-5"], "relevos_v1 › reglas.D60-5") + "."] if J.get("rel") else []),
        ["did_h4_v1 › pares[] › did.E_T", "did_h4_v1 › pares[] › crudo.E_T"] +
        (["relevos_v1 › pares[] › T, q"] if J.get("rel") else [])))
    return B


def s32(M: Modelo, H):
    M.need("rel")
    J, c = M.J, H["coach"]
    rel = J["rel"]
    ps = rel_de(J, H)
    u0 = str(rel["parametros"]["umbral"])
    B = []
    for r in ps:
        F = f"relevos_v1 › pares[{r['club']}, {ape(r['a'])}→{ape(r['b'])}]"
        base = r["umbrales"][u0]
        etq = f"Relevo {ape(r['a'])} → {ape(r['b'])} {en_(r['club'])}: "
        k = M.c(str(base["compartidos"]), F + f" › umbrales.{u0}.compartidos")
        if not r["estimable"]:
            B.append(M.frase("C", etq + "solo " + k + (" jugador tuvo" if base["compartidos"] == 1 else
                                                        " jugadores tuvieron") + " al menos " +
                             M.c(u0, "relevos_v1 › parametros.umbral") + " acciones en las dos eras; "
                             "la parte del uso no se estima."))
            continue
        phi = M.c(fpct0(base["phi_U"]), F + f" › umbrales.{u0}.phi_U")
        txt = (etq + "del cambio en el uso del campo, " + phi)
        if r["estable"]:
            B.append(M.frase("B", txt + M.ic(r["ic95"]["phi_U"], fpct0, F + " › ic95.phi_U") +
                             " corresponde a cómo cambiaron de zonas los " + k +
                             " jugadores que siguieron; el resto, a quién jugó."))
        else:
            alt = "; ".join("con " + M.c(str(u), "relevos_v1 › parametros.umbrales_sensibilidad") + " acciones, " +
                            (M.c(fpct0(r["umbrales"][str(u)]["phi_U"]), F + f" › umbrales.{u}.phi_U")
                             if r["umbrales"][str(u)]["phi_U"] is not None else "no se estima")
                            for u in rel["parametros"]["umbrales_sensibilidad"])
            B.append(M.frase("C", txt + " corresponde a los " + k + " jugadores que siguieron. "
                             "La cifra depende del umbral de compartidos (" + alt + ")."))
    if not ps:
        B.append(M.hueco(1, f"No hay parejas de {ape(c)} en relevos_v1.json."))
    B += [
        M.fig("cu", "Composición contra uso, por relevo",
              "½‖C‖₁: quién jugó. ½‖U‖₁: cómo cambiaron de zonas los que siguieron. "
              "Sin intervalo en la barra; el intervalo de la parte del uso va en el texto.",
              [{"par": f"{ape(r['a'])} → {ape(r['b'])}", "club": r["club"],
                "U": r["umbrales"][u0]["U"], "C": r["umbrales"][u0]["C"],
                "phi": r["umbrales"][u0]["phi_U"], "estimable": r["estimable"]} for r in ps]),
        M.fig("mapas_dif", "Dónde cambió: el cambio total, la parte del uso y la de composición",
              "Diferencia de ocupación en exceso de la liga, entrante menos saliente, en puntos "
              "porcentuales. Mismo rango de color en las tres canchas.",
              [{"par": f"{ape(r['a'])} → {ape(r['b'])} · {r['club']}", **r["mapas"]} for r in ps]),
    ]
    if ps:
        r = ps[0]
        F = f"relevos_v1 › pares[{r['club']}, {ape(r['a'])}→{ape(r['b'])}]"
        B.append(M.ejemplo(f"En el relevo {ape(r['a'])} → {ape(r['b'])} {en_(r['club'])}, " +
                           M.c(str(r["umbrales"][u0]["compartidos"]), F + f" › umbrales.{u0}.compartidos") +
                           " jugadores tuvieron al menos " + M.c(u0, "relevos_v1 › parametros.umbral") +
                           " acciones con los dos técnicos: ellos forman la parte del uso. Todos los "
                           "demás, y el cambio de minutos de estos, son la composición."))
    else:
        B.append(M.hueco(3, "Sin parejas, no hay ejemplo."))
    sens = "; ".join(
        f"{ape(r['a'])} → {ape(r['b'])}: " + ", ".join(
            (M.c(fpct0(r["umbrales"][str(u)]["phi_U"]), f"relevos_v1 › pares[{r['club']}, "
                 f"{ape(r['a'])}→{ape(r['b'])}] › umbrales.{u}.phi_U")
             if r["umbrales"][str(u)]["phi_U"] is not None else "—")
            for u in (100, 200, 400)) for r in ps)
    js = "; ".join(f"{ape(r['a'])} → {ape(r['b'])} " +
                   M.c(f3(r["js_Q_crudo"]), f"relevos_v1 › pares[{r['club']}, {ape(r['a'])}→{ape(r['b'])}] › js_Q_crudo")
                   for r in ps if r.get("js_Q_crudo") is not None)
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        M.cita(rel["reglas"]["D60-3"], "relevos_v1 › reglas.D60-3") + ": la identidad cierra sin residuo "
        "y la interacción se reparte, por convención, mitad y mitad.",
        M.cita(rel["reglas"]["D60-4"], "relevos_v1 › reglas.D60-4") + ". La parte del uso con los "
        "tres umbrales, en ese orden: " + (sens or "—") + ". Se llama estable si los dos alternos "
        "caen a menos de " + M.c(f"{rel['parametros']['estable_si_dif_menor_a']:.2f}",
                                 "relevos_v1 › parametros.estable_si_dif_menor_a") + " del valor base.",
        "Sensibilidad cruda, sin corregir la deriva ni familia: distancia de Jensen–Shannon entre "
        "las matrices de transición de las dos eras. " + (js or "—") + ".",
        "Es un reparto contable: no dice por qué cambió el equipo.",
        "Con menos compartidos, más cambio cae en composición por construcción: la correlación entre "
        "compartidos y la parte del uso es en parte mecánica y no debe leerse como evidencia externa "
        "(adenda 1 de ADR-60)."],
        ["relevos_v1 › pares[] › umbrales, ic95, mapas"]))
    return B


def s33(M: Modelo, H):
    M.need("est")
    J, c = M.J, H["coach"]
    est = J["est"]
    Fe = "estilos_v1"
    mias = [e for e in est["eras"] if e["coach"] == c]
    pos = {(e["club"], e["coach"]): (e["PC1"], e["PC2"]) for e in est["eras"]}
    flechas = []
    for r in est["relevos"]:
        if r["club"] in H["clubes"] and c in (r["a"], r["b"]):
            if (r["club"], r["a"]) in pos and (r["club"], r["b"]) in pos:
                flechas.append({"tipo": "relevo", "de": pos[(r["club"], r["a"])], "a": pos[(r["club"], r["b"])],
                                "etq": f"{ape(r['a'])} → {ape(r['b'])} · {r['club']}"})
    for t in est["traslados"]:
        if t["coach"] == c:
            flechas.append({"tipo": "traslado", "de": pos[(t["club_a"], c)], "a": pos[(t["club_b"], c)],
                            "etq": f"{ape(c)}: {t['club_a']} → {t['club_b']}"})
    d = est["distancias_todas"]
    B = [
        M.frase("C", "Cada punto es una era. El eje horizontal resume el " + esc(est["ejes"]["PC1"]) +
                " (" + M.c(fpct0(est["ejes"]["varianza"][0]), Fe + " › ejes.varianza[0]") +
                " de la variación entre las " + M.c(str(len(est["eras"])), Fe + " › eras (conteo)") +
                " eras) y el vertical, la " + esc(est["ejes"]["PC2"]) + " (" +
                M.c(fpct0(est["ejes"]["varianza"][1]), Fe + " › ejes.varianza[1]") +
                "). Los nombres de los ejes se eligieron viendo las cargas."),
        M.frase("C", f"Las eras de {ape(c)} van resaltadas; las flechas unen cada relevo y cada "
                "cambio de club. Es un mapa descriptivo, sin intervalos."),
        M.fig("estilos", "Mapa de estilos", "Componentes principales de nueve métricas medidas "
              "contra la liga del mismo torneo. Toca un punto para ver la era.",
              {"eras": est["eras"], "coach": c, "flechas": flechas,
               "ejes": [est["ejes"]["PC1"], est["ejes"]["PC2"]],
               # hacia dónde crece cada nombre: el signo de la carga que lo define
               "dir": [-1 if est["cargas"].get("field_tilt", [1, 1])[0] < 0 else 1,
                       -1 if est["cargas"].get("n80", [1, 1])[1] < 0 else 1]}),
        M.ejemplo("La distancia entre dos eras cualesquiera tiene mediana " +
                  M.c(f"{d['mediana']:.2f}", Fe + " › distancias_todas.mediana") + ", y nueve de cada diez quedan por debajo de " +
                  M.c(f"{d['p90']:.2f}", Fe + " › distancias_todas.p90") + " sobre " +
                  M.c(str(d["n"]), Fe + " › distancias_todas.n") + " parejas: es la escala para leer "
                  "cualquier flecha del mapa."),
        plegable_fuente(M, "Cómo lo medimos", [
            "Componentes principales de las eras sobre nueve métricas estandarizadas: " +
            M.cita(", ".join(est["metricas"]), Fe + " › metricas") + ". Mismo cálculo que el barrido "
            "exploratorio, recalculado desde los JSON.",
            "Sin elipses: cinco de las nueve métricas no tienen réplicas por partido y unas elipses "
            "armadas con intervalos marginales inventarían una covarianza (ADR-60).",
            "La escala de distancias es contexto, nunca criterio de rechazo."],
            [Fe + " › eras[] › PC1, PC2", Fe + " › cargas"]),
    ]
    if not mias:
        B.insert(1, M.hueco(1, f"Ninguna era de {ape(c)} tiene las nueve métricas completas."))
    return B


def _fila_era(J, club, coach, lim):
    h = unidad(J, "h4", club, coach)
    g = unidad(J, "met", club, coach)["global"]
    a = [v for v in unidad(J, "jug", club, coach)["A"].values() if not v["parcial"]]
    return {"era": f"{ape(coach)} · {club}", "club": club, "coach": coach,
            "pos": h["rel_E_T_vs_liga"], "pos_ic": h["rel_E_T_vs_liga_ic95"],
            "ft": g["field_tilt"]["dif"], "ft_ic": g["field_tilt"]["ic95"],
            "xg": g["npxg_favor"]["dif"], "xg_ic": g["npxg_favor"]["ic95"],
            "cont": sum(v["percentil_continuidad"] <= lim for v in a), "cont_n": len(a)}


def s34(M: Modelo, H):
    M.need("h4", "met", "jug", "ctx")
    J, c = M.J, H["coach"]
    lim = REGLAS["cont_inferior"][0]
    if H["id"] == JARDINE:
        eras = [(CLUB_J, FOCO), FUERA[0], (CLUB_J, "Fernando Ortiz"), FUERA[1]]
    else:
        eras = [(e["club"], c) for e in H["eras"]]
    filas = [_fila_era(J, club, co, lim) for club, co in eras]
    k, n, lista = viajan_marcador(J["ctx"])
    exige(k < 6, "3.4: la predicción de ADR-57 ahora se cumple; cambia la redacción")
    pj = J["ctx"]["predicciones"][-1]
    B = [M.nota("La tabla junta las eras. Las tres primeras columnas son mediciones contra la "
                "liga del mismo torneo, con intervalo (nivel B); la última es descriptiva "
                "(nivel C).")]
    if H["id"] == JARDINE:
        ja, sl, oa, om = filas
        exige(all(r["pos_ic"][0] > 0 and r["ft_ic"][0] > 0 for r in (ja, oa)),
              "3.4: en el América los dos ya no comparten posesión larga y dominio territorial")
        exige(sl["pos"] < 0 and sl["ft"] < 0 and sl["xg"] < 0,
              "3.4: el perfil de Jardine en San Luis ya no se invierte en las tres métricas")
        exige(om["pos_ic"][0] > 0 and om["ft_ic"][0] <= 0,
              "3.4: Ortiz en Monterrey ya no conserva la posesión sin el dominio territorial")
        B += [
            M.frase("C", "En el América, los dos técnicos muestran el mismo perfil: posesión "
                    "larga y dominio territorial."),
            M.frase("C", "Fuera del América, el perfil de Jardine se invierte en las tres "
                    "métricas (posesión " +
                    M.c(f_pct(sl["pos"]), "did_h4_v1 › unidades[Atlético San Luis, Jardine] › rel_E_T_vs_liga") +
                    ", field tilt " +
                    M.c(f_pp(sl["ft"]), "metricas_v1 › unidades[Atlético San Luis, Jardine] › global.field_tilt.dif") +
                    "). Ortiz conserva la posesión larga en Monterrey y pierde casi todo el "
                    "dominio territorial.", portada=5),
            M.frase("C", "Lo que viaja depende del técnico y de la métrica. El dominio "
                    "territorial es compatible con que sea más del contexto América que de "
                    "quien lo dirige."),
        ]
    else:
        def linea(nombre, k_v, k_ic, fuente, portada=None):
            fmt = f_pct if k_v == "pos" else f_pp if k_v == "ft" else f_num
            grupos = {1: [], -1: [], 0: []}
            for r in filas:
                grupos[direccion(r[k_ic])].append(
                    el_(r["club"]) + " (" + M.c(fmt(r[k_v]), fuente.format(club=r["club"], ape=ape(c))) + ")")
            partes = []
            for s_, t in ((1, "por encima de la liga en"), (-1, "por debajo de la liga en"),
                          (0, "sin separarse de la liga en")):
                g = grupos[s_]
                if g:
                    partes.append(t + " " + (", ".join(g[:-1]) + " y " + g[-1] if len(g) > 1 else g[0]))
            return M.frase("C", f"{nombre} bajo {ape(c)}: " + "; ".join(partes) + ".",
                           portada=portada)
        B += [
            linea("Posesión contra la liga", "pos", "pos_ic",
                  "did_h4_v1 › unidades[{club}, {ape}] › rel_E_T_vs_liga", portada=5),
            linea("Field tilt", "ft", "ft_ic",
                  "metricas_v1 › unidades[{club}, {ape}] › global.field_tilt.dif"),
            linea("npxG a favor", "xg", "xg_ic",
                  "metricas_v1 › unidades[{club}, {ape}] › global.npxg_favor.dif"),
        ]
    B += [
        M.fig("fig8", f"El mismo técnico en otro club", "Toca una celda para ver el intervalo "
              "y la fuente.", filas),
        *([M.frase("C", f"En el mapa de estilos, {ape(c)} entre {el_(t['club_a'])} y {el_(t['club_b'])}: "
                   "distancia " + M.c(f"{t['distancia']:.2f}", f"estilos_v1 › traslados[{ape(c)}, {t['club_a']}–{t['club_b']}] › distancia") +
                   ", más lejos que " + M.c(fpct0(t["percentil"]), f"estilos_v1 › traslados[{ape(c)}, {t['club_a']}–{t['club_b']}] › percentil") +
                   " de las parejas de eras de la liga.")
            for t in J["est"]["traslados"] if t["coach"] == c] if J.get("est") else
          [M.nota("La distancia en el mapa de estilos sale de estilos_v1.json (" + esc(FUENTES["est"][1]) + ").")]),
        M.frase("C", "La comparación entre clubes no separa plantel, presupuesto ni "
                "calendario, que cambian con el club; es descriptiva (ADR-37)."),
        M.frase("C", "Entre los técnicos con varios clubes fuera del América, " +
                M.c(f"{k} de {n}", "contexto_v1 › viaja_marcador_M1 (sin Jardine ni Ortiz)", "Viajan") +
                " mantienen el signo de su ajuste al marcador de un club a otro. "
                "La predicción preinscrita pedía al menos seis y no se cumplió.",
                nota_adenda="Conteo sin Jardine ni Ortiz, como en 06_DECISIONS."),
        M.fig("viajan", "¿Viaja el ajuste al marcador?",
              "Técnicos con eras en varios clubes (ADR-57), métrica M1.",
              [{"coach": nom(co), "mismo": v} for co, v in lista]),
        M.nota("El JSON registra la predicción con los once técnicos, incluidos Jardine y "
               "Ortiz: " + M.c(f"{pj['valor'][0]} de {pj['valor'][1]}",
                               "contexto_v1 › predicciones[ADR-57, 1].valor") +
               ". Con cualquiera de los dos conteos la predicción falla."),
    ]
    a0, a1 = filas[0], filas[1] if len(filas) > 1 else None
    if a1:
        B.append(M.ejemplo(f"Con {ape(a0['coach'])} {en_(a0['club'])}, las posesiones iban " +
                           M.c(f_pct(a0["pos"]), f"did_h4_v1 › unidades[{a0['club']}, {ape(a0['coach'])}] › rel_E_T_vs_liga") +
                           f" respecto a la liga; con {ape(a1['coach'])} {en_(a1['club'])}, " +
                           M.c(f_pct(a1["pos"]), f"did_h4_v1 › unidades[{a1['club']}, {ape(a1['coach'])}] › rel_E_T_vs_liga") + "."))
    else:
        B.append(M.hueco(3, "Una sola era: no hay traslado que mostrar."))
    B.append(plegable_fuente(M, "Cómo lo medimos", [
        "Cada celda de las tres primeras columnas es la misma medición de las secciones de duración y de ocasiones, era por "
        "era: nivel B. Juntar eras de clubes distintos es descriptivo (nivel C): ADR-37 no "
        "compara técnicos entre clubes como resultado principal.",
        "El ajuste al marcador que viaja es la primera predicción de ADR-57, sobre los técnicos con "
        "varios clubes."],
        ["did_h4_v1 › unidades[] › rel_E_T_vs_liga", "metricas_v1 › unidades[] › global",
         "jugadores_v1 › unidades[] › A", "contexto_v1 › viaja_marcador_M1"]))
    return B


# ---------------------------------------------------------------------------
# CIERRE (común)
# ---------------------------------------------------------------------------
def c_credibilidad(M: Modelo):
    M.need("h4", "pres", "bp", "ctx", "jug")
    h4, pr = M.J["h4"], M.J["pres"]
    todo = marcador(M.J)
    mk = [p for p in todo if p["adr"] <= 58]
    m60 = [p for p in todo if p["adr"] == 60]
    m61 = [p for p in todo if p["adr"] == 61]
    ok = sum(p["cumple"] for p in mk)
    por_adr = {}
    for p in mk:
        a = por_adr.setdefault(p["adr"], [0, 0])
        a[0] += p["cumple"]
        a[1] += 1
    Fh, Fp = "did_h4_v1", "did_presion_v1"
    resumen = ", ".join(f"ADR-{a} {M.c(f'{v[0]}/{v[1]}', 'marcador › ADR-' + str(a))}"
                        for a, v in sorted(por_adr.items()))
    return [
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
        *([M.frase("C", "Relevos (ADR-60), escritas antes de calcularlos: " +
                   M.c(f"{sum(p['cumple'] is True for p in m60)} de {sum(p['cumple'] is not None for p in m60)}",
                       "relevos_v1 › predicciones") + " se cumplieron" +
                   ("; " + M.c(str(sum(p['cumple'] is None for p in m60)), "relevos_v1 › predicciones (no evaluables)") +
                    " no se pudo evaluar" if any(p["cumple"] is None for p in m60) else "") +
                   ". Cuatro de las seis estaban informadas por el barrido exploratorio y valen menos.")]
          if m60 else []),
        *([M.frase("C", "Progresión y supervivencia (ADR-61), escritas antes de calcularlas: " +
                   M.c(f"{sum(p['cumple'] is True for p in m61)} de {sum(p['cumple'] is not None for p in m61)}",
                       "progresion_v1 › predicciones") + " se cumplieron" +
                   ("; " + M.c(str(sum(p['cumple'] is None for p in m61)), "progresion_v1 › predicciones (no evaluables)") +
                    " no se pudo evaluar" if any(p["cumple"] is None for p in m61) else "") +
                   ". Una estaba informada por ADR-53 y otra replica ADR-21: valen menos.")]
          if m61 else []),
        M.fig("fig9", "Predicciones preinscritas", "Punto lleno: se cumplió. Aro: falló. "
              "Punteado: no evaluable. Toca cada una para leerla.", todo),
    ]


def c_limites(M: Modelo):
    return [
        M.frase("C", "Lo que el marco no captura:"),
        M.nota(LIMITES),
        M.nota("Nada de este informe es causal. Describe cómo jugaron los equipos bajo "
               "cada técnico, contra la liga del mismo torneo; no mide rendimiento ni "
               "intención."),
    ]


# ---------------------------------------------------------------------------
# índice
# ---------------------------------------------------------------------------
# (id, número, componente del reto, título, función | None, pendiente)
ACTO1 = [
    ("a1-1", "1.1", "5.6", "La posesión y sus tres preguntas", a1_posesion, None),
    ("a1-2", "1.2", "5.6", "La cadena: estados vivos y finales", a1_cadena, None),
    ("a1-3", "1.3", "5.6", "Cómo se estiman las probabilidades", a1_estimacion, None),
    ("a1-4", "1.4", "5.6", "En qué confiar", a1_confianza, None),
    ("a1-5", "1.5", "5.6", "Por qué contra la liga del mismo torneo", a1_deriva, None),
    ("a1-6", "1.6", "5.6", "Dónde vive una posesión viva", a1_viva, None),
    ("a1-7", "1.7", "5.6", "Por qué no simulamos", a1_simular, None),
]
ACTO2 = [
    ("a2-1", "2.1", "5.1 ofensiva", "Con el balón: cuánto dura y dónde vive", s21, None),
    ("a2-2", "2.2", "5.1 ofensiva", "Progresión: ¿llega a la franja del área sin perderla?", s22, None),
    ("a2-3", "2.3", "5.1 ofensiva", "Ocasiones y territorio", s23, None),
    ("a2-4", "2.4", "5.1 defensiva", "Sin el balón", s24, None),
    ("a2-5", "2.5", "5.2 consistencia", "¿La misma idea torneo tras torneo?", s25, None),
    ("a2-6", "2.6", "5.2 variabilidad", "¿Ajusta al contexto?", s26, None),
    ("a2-7", "2.7", "5.4", "Balón parado", s27, None),
    ("a2-8", "2.8", "5.3", "Jugadores y minutos", s28, None),
]
ACTO3 = [
    ("a3-1", "3.1", "5.3", "El club antes y después de él", s31, None),
    ("a3-2", "3.2", "5.3", "¿Cambió el plantel o cambió el uso?", s32, None),
    ("a3-3", "3.3", "5.5", "Mapa de estilos", s33, None),
    ("a3-4", "3.4", "diferenciador", "¿Qué viaja con él y qué se queda en el club?", s34, None),
]
CIERRE = [
    ("c-1", "C.1", "credibilidad", "¿El método distingue de verdad?", c_credibilidad, None),
    ("c-2", "C.2", "5.6", "Framework y límites", c_limites, None),
    ("c-3", "C.3", "anexo", "Errores silenciosos encontrados", None,
     {"adr": "catálogo de errores", "fase": "F7",
      "que": "el catálogo de los errores silenciosos, con su fuente (adenda 1, punto 7)"}),
]

DEF_POSESION = (
    "<p><b>Posesión</b>: la cadena de acciones de un equipo desde que recupera el balón "
    "hasta que lo pierde, sale o remata. <b>Acción</b>: pase, conducción o remate. "
    "<b>Fase</b>: juego abierto, transición, reanudación o balón parado. "
    "<b>Zona</b>: una de las 20 zonas de la cancha.</p>")

DEF_MARKOV = (
    "<p><b>Estado</b>: zona × fase (20 × 4). <b>Cadena</b>: cada acción mueve la posesión "
    "de un estado a otro con probabilidad <i>Q<sub>ij</sub></i>, o la termina en remate, "
    "gol o pérdida con probabilidad <i>R<sub>ik</sub></i>. La matriz completa tiene la forma "
    "<i>P = (Q R ; 0 I)</i>: los finales no devuelven el balón.</p>"
    "<p>Con la matriz fundamental <i>N = (I − Q)<sup>−1</sup></i>, la duración esperada es "
    "<i>E[T] = N·1</i> y la probabilidad de terminar en remate o gol es <i>B = N·R</i>.</p>"
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
def _seccion(M, H, sid, num, comp, tit, fn, pend):
    s = {"id": sid, "num": num, "comp": comp, "tit": tit}
    if pend is not None:
        s["pendiente"] = pend
        return s
    try:
        s["bloques"] = fn(M, H) if H is not None else fn(M)
    except LecturaCambio as e:
        quien = f" (historia {H['id']})" if H else ""
        sys.exit(f"LECTURA PREINSCRITA ROTA en {sid}{quien}: {e}. Revisar ADR-59 antes de publicar.")
    except FaltaInsumo as e:
        nombre, cmd = FUENTES[e.clave]
        s.pop("bloques", None)
        s["falta"] = {"archivo": nombre, "comando": cmd}
    return s


def construye(J: dict, traza: dict) -> tuple[dict, Modelo]:
    registro: list[dict] = []
    M0 = Modelo(J, registro, exporta=True, hid="comun")
    acto1 = [_seccion(M0, None, *x) for x in ACTO1]
    hs = []
    for hid, coach in HISTORIAS:
        H = historia(J, hid, coach)
        M = Modelo(J, registro, exporta=(hid == JARDINE), hid=hid)
        if not H["eras"]:
            vacias = [{"id": sid, "num": num, "comp": comp, "tit": tit,
                       "falta": {"archivo": "metricas_v1.json", "comando": FUENTES["met"][1]}}
                      for sid, num, comp, tit, _, _ in ACTO2 + ACTO3]
            hs.append({**{k: H[k] for k in ("id", "coach", "nombre", "eras", "principal")},
                       "acto2": vacias[:len(ACTO2)], "acto3": vacias[len(ACTO2):]})
            continue
        hs.append({**{k: H[k] for k in ("id", "coach", "nombre", "eras", "principal")},
                   "acto2": [_seccion(M, H, *x) for x in ACTO2],
                   "acto3": [_seccion(M, H, *x) for x in ACTO3]})
    cierre = [_seccion(M0, None, *x) for x in CIERRE]
    datos = {"acto1": acto1, "historias": hs, "cierre": cierre,
             "traza": traza, "reglas": REGLAS}
    M0.cifras = registro
    return datos, M0


def todas_las_secciones(datos):
    """(historia, sección) de toda la página. Para los tests y el resumen."""
    for s in datos["acto1"]:
        yield "comun", s
    for h in datos["historias"]:
        for s in h["acto2"] + h["acto3"]:
            yield h["id"], s
    for s in datos["cierre"]:
        yield "comun", s


def escribe_tex(M: Modelo, ruta: Path):
    """Las cifras con clave, como macros para la guía LaTeX: la guía tampoco
    teclea números. Solo Jardine y el acto 1 exportan (adenda 2 §9)."""
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
    ap.add_argument("--datos", default=str(RAIZ),
                    help="raíz bajo la que viven data/processed_api_<club>/ (mapas de zonas)")
    ap.add_argument("--out", default="reporte.html")
    ap.add_argument("--modelo", default=None, help="vuelca el modelo a JSON (tests)")
    ap.add_argument("--tex", default=None, help="macros de cifras para la guía LaTeX")
    args = ap.parse_args()

    J, traza = recolecta(Path(args.reports), Path(args.datos))
    try:
        datos, M = construye(J, traza)
    except ZonasIlegibles as e:
        sys.exit(f"ZONAS ILEGIBLES: {e}. No se escribe nada.")
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
    print(f"escrito: {salida.resolve()}  ({salida.stat().st_size / 1024:.0f} KB)")
    print(f"cifras con fuente: {len(M.cifras)}")
    for h in datos["historias"]:
        faltan = [s["num"] for s in h["acto2"] + h["acto3"] if "falta" in s]
        pend = [s["num"] for s in h["acto2"] + h["acto3"] if "pendiente" in s]
        huecos = sum(b["tipo"] == "hueco" for s in h["acto2"] + h["acto3"]
                     for b in s.get("bloques", []))
        z = J["zonas"].get((h["principal"], h["coach"]), {})
        print(f"  {h['id']:9s} principal {h['principal']:<18s} eras {len(h['eras'])} · "
              f"sin insumo {faltan or '-'} · pendientes {pend} · huecos {huecos} · "
              "zonas " + (f"ok ({z['n']} acciones, {z['fuera']} fuera de la malla)" if "m" in z
                          else "FALTA (no hay parquet)"))
    print(f"commit: {traza['commit']['hash']}"
          + (" (con cambios sin commitear)" if traza["commit"]["sucio"] else ""))


HTML = r"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>La historia de un entrenador</title>
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
  /* semáforo (adenda 2 §5): el ÚNICO color fuera del gris. Solo en las
     etiquetas de nivel; ninguna figura lo usa. */
  --sem-a:#30d158; --sem-b:#ffd60a; --sem-c:#8e8e96;
}
.aviso{background:var(--mono-bg);border-color:var(--brd);color:var(--tx2)}
.chipd.ok{background:rgba(255,255,255,.12);color:var(--tx);border-color:var(--brd)}
.chipd.dn{background:transparent;color:var(--tx2);border:1px dashed var(--brd)}
#tip b{color:var(--tx2)}
.dot{background:var(--tx2)}
h1 em{background:linear-gradient(120deg,#fff,#9a9aa2);-webkit-background-clip:text}

/* barra de secciones: el segmentado de iOS, ahora como índice */
.navin{flex-wrap:nowrap}
#segHist,#segActo{overflow-x:auto;scrollbar-width:none;max-width:100%}
#segHist::-webkit-scrollbar,#segActo::-webkit-scrollbar{display:none}
#segActo button{font-family:var(--mono);padding:.42rem .7rem}
@media(max-width:700px){.navin{flex-wrap:wrap}}
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
.nv-A{background:var(--sem-a);color:#0b0b0e}
.nv-B{background:var(--sem-b);color:#0b0b0e}
.nv-C{border:1.5px dashed var(--sem-c);color:var(--tx2)}
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
.pto.ne{background:transparent;border-style:dashed;border-color:var(--tx3)}
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

/* ---------- tres actos (adenda 2) ---------- */
body:not(.tecnica) .tec{display:none}
.acto{margin:6rem 0 0;padding:2.2rem 0 0;border-top:1px solid var(--brd)}
.acto h3{font-size:clamp(1.5rem,3vw,2.2rem);font-weight:800;letter-spacing:-.04em}
.acto p{color:var(--tx2);font-size:1.02rem;margin-top:.5rem;max-width:62ch;line-height:1.55}
.acto .eyebrow{margin-bottom:.4rem}
.pregunta{font-size:1.05rem;color:var(--tx2);margin:-.3rem 0 1.2rem;max-width:62ch}
.ejemplo{background:var(--card2);border:1px solid var(--brd);border-left:3px solid var(--a1);
 border-radius:var(--r-sm);padding:1rem 1.2rem;margin:1.2rem 0;font-size:1rem;line-height:1.6;
 max-width:70ch}
.ejemplo u{text-decoration:none;display:block;font-family:var(--mono);font-size:.7rem;
 letter-spacing:.16em;text-transform:uppercase;color:var(--tx2);margin-bottom:.3rem}
.hueco{background:transparent;border:1px dashed var(--brd);border-radius:var(--r-sm);
 padding:.9rem 1.2rem;margin:1rem 0;color:var(--tx2);font-size:.95rem;line-height:1.55;max-width:70ch}
.hueco u{text-decoration:none;font-family:var(--mono);font-size:.7rem;letter-spacing:.14em;
 text-transform:uppercase;margin-right:.5rem;color:var(--tx2)}
.pendiente{background:var(--card2);border:1px dashed var(--brd);border-radius:var(--r-md);
 padding:1.3rem 1.5rem;color:var(--tx2);font-size:.98rem;line-height:1.6}
.pendiente b{color:var(--tx)}
.cf.cita{white-space:normal;font-family:var(--sans);font-weight:400;font-size:1em}
.portada{display:flex;flex-direction:column;gap:.2rem;margin-top:1.4rem;max-width:74ch}
.portada a{color:inherit;text-decoration:none}
.portada .fr{margin:.45rem 0}
.portada .fr:hover .tx{color:var(--tx)}
.portada .ir{font-family:var(--mono);font-size:.72rem;color:var(--tx2);margin-left:.4rem;white-space:nowrap}
.eras{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1rem}
.eras .chip.pr{border-color:var(--a1)}
#segHist button{font-size:.84rem}
#segModo button{font-size:.8rem}
.sem{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}
@media(max-width:760px){.sem{grid-template-columns:1fr 1fr}}
.sem .card{padding:1rem}
.sem .nv{margin-bottom:.5rem}
.sem p{font-size:.88rem;color:var(--tx2);line-height:1.5}
</style></head><body>
<div id="aura"></div>
<div id="tip"></div>

<header class="wrap">
  <div class="kicker"><span class="dot"></span><span>Liga MX · fase regular · cinco historias</span></div>
  <h1 id="titulo">La historia<br><em>de un entrenador</em></h1>
  <p id="bajada">Cómo jugó un equipo bajo un entrenador, y qué de eso cambia cuando el entrenador cambia de club.</p>
  <div class="eras" id="eras"></div>
  <div class="portada" id="portada"></div>
  <div class="traza tec" id="traza"></div>
</header>

<nav><div class="navin">
  <div class="seg" id="segHist"><div class="pill"></div></div>
  <div class="seg" id="segActo"><div class="pill"></div></div>
  <div class="seg" id="segModo" style="margin-left:auto"><div class="pill"></div></div>
</div></nav>

<div class="wrap">
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
 A:"<b>verde · A · probado</b>Contraste preinscrito, intervalo por bootstrap y corrección BH dentro de su familia.",
 B:"<b>ámbar · B · medido</b>Diferencia contra la liga del mismo torneo, con intervalo; sin familia.",
 C:"<b>gris · C · descriptivo</b>Percentiles, perfiles o comparaciones sin intervalo."};
const ADENDA=(m,n)=>`<b>adenda ${n||1} de ADR-59</b>${esc(m)}`;
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
/* mapa con signo: más (--a1) o menos (--neg) que antes, rango común vm */
function mapaDif(v,vm){
 return pitch((s)=>{let g="";
  for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++){
   const x=v[ix*NY+iy],a=Math.min(1,Math.abs(x)/vm),X0=ix*cw*s,Y0=iy*ch*s;
   /* un solo tono (15 §5.5): más = lleno, menos = aro punteado; el número va escrito */
   const t=`${x>=0?"+":"−"}${Math.abs(x*100).toFixed(1)}`;
   g+=`<g class="celda" data-tip="<b>${esc(FRANJA[iy])}, tercio ${esc(TERCIO[ix])}</b>${t} pp"><rect x="${X0+2.5}" y="${Y0+2.5}" width="${cw*s-5}" height="${ch*s-5}" rx="8"
    fill="${x>=0?C_FOCO:"none"}" fill-opacity="${x>=0?(.05+.8*a).toFixed(2):0}" stroke="${x>=0?"#fff":C_FOCO}"
    stroke-opacity="${x>=0?.14:(.25+.7*a).toFixed(2)}" stroke-width="${x>=0?1:1.2+2.4*a}" ${x>=0?"":'stroke-dasharray="4 3"'}/>
    <text x="${X0+cw*s/2}" y="${Y0+ch*s/2+4}" text-anchor="middle" font-size="10.5" font-family="var(--mono)"
     fill="${x>=0&&a>.55?"#0b0b0e":"var(--tx)"}" pointer-events="none">${t}</text></g>`;}
  return g;},300);
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
  if(d.falta)return vacio("Falta el parquet de transiciones de esta era; el mapa se pinta al generar el informe en la máquina del proyecto.",d.falta);
  return mapaSVG(d.m,C_FOCO,"de las acciones de la era")+
   leyenda(rampa(C_FOCO,"pocas acciones","muchas"),"Los porcentajes suman 100.");
 },
 fig3(d,fid){
  const modo=ESTADO[fid]??"did";
  const filas=d.map(p=>({etq:p.par,sub:`${p.club||""} · q = ${p.q.toFixed(3)}`,marcas:[
   ...(modo!=="cru"?[{v:p.did,ic:p.did_ic,lleno:true,nombre:"corregido",q:p.q,nota:p.rech?"sobrevive a la corrección":"no sobrevive a la corrección"}]:[]),
   ...(modo!=="did"?[{v:p.cru,ic:p.cru_ic,lleno:false,nombre:"crudo",nota:"resta directa, con la deriva dentro"}]:[])]}));
  return seg(fid,[["did","corregido"],["cru","crudo"],["ambos","los dos"]])+
   bosque(filas,v=>pct(v))+leyenda(SW(C_FOCO,"contra la liga del mismo torneo"),SW("var(--tx2)","resta cruda",true));
 },
 fig3b(d){
  return bosque(d.map(p=>({etq:p.par,sub:`${p.club||""} · q = ${p.q.toFixed(3)}`,marcas:[{v:p.t,ic:p.ic,lleno:p.r,q:p.q,
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
  const ok=d.filter(p=>p.cumple===true&&p.adr<=58).length,n58=d.filter(p=>p.adr<=58).length,grupos={};
  d.forEach(p=>(grupos[p.adr]=grupos[p.adr]||[]).push(p));
  return `<div class="grid duo"><div class="puntos">${Object.entries(grupos).map(([a,ps])=>
   `<div class="grupo-adr"><u>ADR-${a}</u>${ps.map(p=>`<span class="pto ${p.cumple===null||p.cumple===undefined?"ne":p.cumple?"si":"no"}"
    data-tip="<b>ADR-${a} · predicción ${p.n}</b>${esc(p.texto)}<br>${p.cumple===null||p.cumple===undefined?"no evaluable":p.cumple?"se cumplió":"falló"}"></span>`).join("")}</div>`).join("")}</div>
   <div class="cifra"><u>SE CUMPLIERON · ADR-53 A 58</u><b class="marcador-total"><span data-num="${ok}" data-dec="0">0</span> / ${n58}</b>
   <i>Las que fallaron se quedan a la vista.</i></div></div>`;
 },
 eras_pos(d){
  return bosque(d.map(r=>({etq:r.era,sub:`${r.n} partidos${r.principal?" · era principal":""}`,
   marcas:[{v:r.v,ic:r.ic,lleno:r.principal,nota:r.principal?"era principal de la historia":"otra era del técnico"}]})),v=>pct(v),{refTxt:"LIGA DEL MISMO TORNEO"})+
   leyenda(SW(C_FOCO,"era principal"),SW("var(--tx2)","otras eras",true));
 },
 concedido(d){
  return bosque(d.map(r=>({etq:r.era,sub:`${r.n} partidos${r.principal?" · era principal":""}`,
   marcas:[{v:r.v,ic:r.ic,lleno:r.principal}]})),v=>fmtS(v,2),{refTxt:"LIGA DEL MISMO TORNEO"})+
   leyenda(SW(C_FOCO,"era principal"),SW("var(--tx2)","otras eras",true));
 },
 tarjetas(d){
  return `<div class="grid g2f">${d.map(x=>{const f=x.u==="pp"?(v=>ppt(v)):(v=>fmtS(v,x.k==="prog_pases"?1:2));
   return `<div class="card flat"><div class="eq">${esc(x.t)}</div>
    <div class="c-val" style="font-size:1.9rem">${f(x.v)}</div>
    <div class="tec">${mini(x.v,x.ic)}<div class="c-pie">[${f(x.ic[0])}, ${f(x.ic[1])}]</div></div></div>`;}).join("")}</div>`;
 },
 cadena(){
  const n=[[70,60],[170,40],[170,120],[70,140]],f=[["remate",330,30],["gol",330,85],["pérdida",330,140]];
  let g=`<svg viewBox="0 0 420 180">`;
  [[0,1],[1,2],[2,3],[3,0],[0,2],[1,3]].forEach(([a,b])=>{g+=`<line x1="${n[a][0]}" y1="${n[a][1]}" x2="${n[b][0]}" y2="${n[b][1]}" stroke="var(--tx2)" stroke-width="1.4" opacity=".6"/>`;});
  [[1,0],[2,1],[2,2]].forEach(([a,k])=>{g+=`<path d="M${n[a][0]+14} ${n[a][1]} L${f[k][1]-36} ${f[k][2]}" stroke="var(--a1)" stroke-width="1.6" fill="none" stroke-dasharray="5 4"/>
   <path d="M${f[k][1]-36} ${f[k][2]} l-7 -4 v8 z" fill="var(--a1)"/>`;});
  n.forEach(([x,y],i)=>{g+=`<circle cx="${x}" cy="${y}" r="15" fill="var(--a1)" opacity=".85"/><text x="${x}" y="${y+4}" text-anchor="middle" font-size="11" fill="#0b0b0e" font-weight="700">vivo</text>`;});
  f.forEach(([t,x,y])=>{g+=`<rect x="${x-34}" y="${y-13}" width="84" height="26" rx="8" fill="none" stroke="var(--a1)" stroke-width="1.6"/><text x="${x+8}" y="${y+4}" text-anchor="middle" font-size="12" fill="var(--tx)">${t}</text>`;});
  g+=`<text x="120" y="172" text-anchor="middle" font-size="11" fill="var(--tx2)">transitorios: se pasan el balón</text>
   <text x="338" y="172" text-anchor="middle" font-size="11" fill="var(--tx2)">absorbentes: sin regreso</text></svg>`;
  return g;
 },
 estimacion(){
  const barra=(x,h,t,op)=>`<rect x="${x}" y="${130-h}" width="70" height="${h}" rx="8" fill="var(--a1)" opacity="${op}"/>
   <text x="${x+35}" y="152" text-anchor="middle" font-size="12" fill="var(--tx2)">${t}</text>`;
  return `<svg viewBox="0 0 420 165">${barra(30,95,"lo observado",.9)}${barra(175,55,"la liga",.35)}${barra(320,80,"lo que se usa",.65)}
   <path d="M108 70 C140 70 150 90 170 95" stroke="var(--tx2)" fill="none" stroke-width="1.4"/>
   <path d="M253 95 C280 90 295 70 315 70" stroke="var(--tx2)" fill="none" stroke-width="1.4"/></svg>`;
 },
 semaforo(){
  const c=(n,t,p,nulo)=>`<div class="card flat"><span class="nv nv-${n}"${nulo?' style="display:inline-flex;gap:.3rem"':""}>${n}${nulo?" · nulo":""}</span><h4 style="margin:.2rem 0 .3rem">${t}</h4><p>${p}</p></div>`;
  return `<div class="sem">${c("A","Probado","Escrito antes de medir, sobrevive a la corrección. Se dice «difiere».")}
   ${c("A","Nulo","Probado sin diferencia: dice el tamaño máximo que descarta.",true)}
   ${c("B","Medido","Contra la liga del mismo torneo, con intervalo.")}
   ${c("C","Descriptivo","Percentiles y comparaciones, sin lenguaje de hallazgo.")}</div>`;
 },
 fig_T(D_){
  const d=D_.filas||D_,p90=D_.placebo90;
  return bosque(d.map(p=>({etq:p.par,sub:`${p.club} · q = ${(+p.q).toFixed(3)}`,marcas:[{v:p.v,ic:p.ic,lleno:p.r,q:p.q,
   nota:(p.r?"sobrevive a la corrección":"no sobrevive a la corrección")+(p.nula95!=null?` · percentil 95 de la nula ${(+p.nula95).toFixed(3)}`:"")}]})),
   v=>(+v).toFixed(3),p90!=null?{ref:p90,refTxt:"P90 DEL PLACEBO"}:{refTxt:"SIN CAMBIO"})+
   leyenda(SW(C_FOCO,"sobrevive"),SW("var(--tx2)","no sobrevive",true),
    p90!=null?`<span class="leg">línea punteada: percentil 90 del placebo (${(+p90).toFixed(3)}), contexto y no criterio</span>`:"");
 },
 cu(d){
  if(!d.length)return vacio("Sin relevos de esta historia en relevos_v1.json.");
  const mx=Math.max(...d.map(x=>x.U+x.C),1e-9);
  return `<div class="lista">${d.map(x=>`<div class="item" data-tip="<b>${esc(x.par)} · ${esc(x.club)}</b>uso ${(+x.U).toFixed(3)} · composición ${(+x.C).toFixed(3)}${x.estimable?` · parte del uso ${Math.round(100*x.phi)}%`:" · uso no estimable"}">
   <div class="it-tx"><div class="it-nom">${esc(x.par)}</div><div class="it-sub">${esc(x.club)}</div></div>
   <div class="it-bar" style="width:180px"><i style="background:var(--a1);width:${(100*x.U/mx).toFixed(1)}%" data-w="${(100*x.U/mx).toFixed(1)}"></i><i style="background:var(--riv);width:${(100*x.C/mx).toFixed(1)}%" data-w="${(100*x.C/mx).toFixed(1)}"></i></div>
   <div class="it-val">${x.estimable?Math.round(100*x.phi)+"%":"—"}</div></div>`).join("")}</div>`+
   leyenda(SW(C_FOCO,"uso"),SW("var(--riv)","composición"),`<span class="leg">a la derecha: parte del uso</span>`);
 },
 mapas_dif(d,fid){
  if(!d.length)return vacio("Sin relevos de esta historia en relevos_v1.json.");
  const on=+(ESTADO[fid]??0),x=d[Math.min(on,d.length-1)];
  const vm=Math.max(...["delta","U","C"].flatMap(k=>x[k].map(Math.abs)),1e-9);
  const sel=d.length>1?seg(fid,d.map((p,i)=>[String(i),p.par])):"";
  return sel+`<div class="grid g3">${[["delta","cambio total"],["U","uso"],["C","composición"]].map(([k,t])=>
   `<div class="panel"><div class="mapcap">${t}</div>${mapaDif(x[k],vm)}</div>`).join("")}</div>`+
   leyenda(SW(C_FOCO,"más que antes"),SW(C_FOCO,"menos que antes (aro)",true),`<span class="leg">escala común ±${(vm*100).toFixed(1)} pp</span>`);
 },
 estilos(d){
  const W=840,H=520,m=46,xs=d.eras.map(e=>e.PC1),ys=d.eras.map(e=>e.PC2);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
  const X=v=>m+(v-x0)/((x1-x0)||1)*(W-2*m),Y=v=>H-m-(v-y0)/((y1-y0)||1)*(H-2*m);
  let g=`<svg viewBox="0 0 ${W} ${H}" data-estilos="1"><defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--a1)"/></marker></defs>
   <line x1="${m}" x2="${W-m}" y1="${H-m}" y2="${H-m}" stroke="#fff" stroke-opacity=".2"/><line x1="${m}" x2="${m}" y1="${m}" y2="${H-m}" stroke="#fff" stroke-opacity=".2"/>
   ${(d.dir||[1,1])[0]>0?`<text x="${W-m}" y="${H-m+30}" text-anchor="end" fill="var(--tx2)" font-size="12">más ${esc(d.ejes[0])} →</text>`
     :`<text x="${m}" y="${H-m+30}" fill="var(--tx2)" font-size="12">← más ${esc(d.ejes[0])}</text>`}
   ${(d.dir||[1,1])[1]>0?`<text x="${m-30}" y="${m}" fill="var(--tx2)" font-size="12" transform="rotate(-90 ${m-30} ${m})" text-anchor="end">más ${esc(d.ejes[1])} →</text>`
     :`<text x="${m-30}" y="${H-m}" fill="var(--tx2)" font-size="12" transform="rotate(-90 ${m-30} ${H-m})">← más ${esc(d.ejes[1])}</text>`}`;
  d.flechas.forEach(f=>{g+=`<line x1="${X(f.de[0])}" y1="${Y(f.de[1])}" x2="${X(f.a[0])}" y2="${Y(f.a[1])}" stroke="var(--a1)"
   stroke-width="${f.tipo==="traslado"?2.4:1.4}" ${f.tipo==="traslado"?"":'stroke-dasharray="5 4"'} marker-end="url(#punta)" opacity=".85"><title>${esc(f.etq)}</title></line>`;});
  d.eras.forEach(e=>{const mia=e.coach===d.coach;
   g+=`<g data-tip="<b>${esc(e.coach)} · ${esc(e.club)}</b>${e.n_partidos} partidos"><circle cx="${X(e.PC1)}" cy="${Y(e.PC2)}" r="${mia?8:5}"
    fill="${mia?"var(--a1)":"var(--bg)"}" stroke="${mia?"var(--a1)":"var(--tx3)"}" stroke-width="1.6"/>${mia?`<text x="${X(e.PC1)+11}" y="${Y(e.PC2)+4}" fill="var(--tx)" font-size="12">${esc(e.club)}</text>`:""}</g>`;});
  return g+`</svg>`+leyenda(SW(C_FOCO,"eras del técnico"),SW("var(--tx3)","otras eras",true),
   `<span class="leg">línea continua: cambio de club · punteada: relevo</span>`);
 },
 viva(d,fid){
  const n=d.frames.length,ops=[["0","al empezar"],[String(Math.floor(n/2)),"a mitad"],["pi","a la larga"]];
  const on=ESTADO[fid]??"0",v=on==="pi"?d.pi:d.frames[Math.min(+on,n-1)];
  const vm=Math.max(...d.pi,...d.frames.flat());
  const m=[];for(let ix=0;ix<NX;ix++){m.push([]);for(let iy=0;iy<NY;iy++)m[ix].push(v[ix*NY+iy]);}
  return seg(fid,ops)+`<div data-viva="1">${mapaSVG(m,C_FOCO,"de las posesiones vivas",vm)}</div>`+
   leyenda(rampa(C_FOCO,"poca masa","mucha"),`<span class="leg">${on==="pi"?"distribución cuasi-estacionaria":"paso "+on+" de la iteración"} · misma escala en los tres pasos</span>`);
 },
 viva_era(d){
  const vm=Math.max(...d.era.flat(),...d.base.flat());
  return `<div class="grid par">${[["era",d.etq[0]],["base",d.etq[1]]].map(([k,t])=>
   `<div class="panel"><div class="mapcap">${esc(t)}</div>${mapaSVG(d[k],C_FOCO,"de las posesiones vivas",vm)}</div>`).join("")}</div>`+
   leyenda(rampa(C_FOCO,"poca masa","mucha"),"Escala común; los porcentajes de cada cancha suman 100.");
 },
 superv(d){
  const W=840,H=300,x0=58,x1=W-24,y0=20,y1=H-46,K=d.obs.length;
  const X=k=>x0+(k-1)/(K-1)*(x1-x0),Y=v=>y1-v*(y1-y0);
  let g=`<svg viewBox="0 0 ${W} ${H}" data-superv="1">`;
  [0,.5,1].forEach(t=>{g+=`<line x1="${x0}" x2="${x1}" y1="${Y(t)}" y2="${Y(t)}" stroke="#fff" stroke-opacity=".06"/>
   <text x="${x0-8}" y="${Y(t)+4}" text-anchor="end" fill="var(--tx3)" font-size="10" font-family="var(--mono)">${Math.round(t*100)}%</text>`;});
  [1,5,10,15,20,25,30].filter(k=>k<=K).forEach(k=>{g+=`<text x="${X(k)}" y="${H-24}" text-anchor="middle" fill="var(--tx2)" font-size="11" font-family="var(--mono)">${k}</text>`;});
  g+=`<text x="${(x0+x1)/2}" y="${H-6}" text-anchor="middle" fill="var(--tx3)" font-size="11">acciones</text>`;
  g+=`<polyline points="${d.mod.map((v,i)=>`${X(i+1)},${Y(v)}`).join(" ")}" fill="none" stroke="var(--tx2)" stroke-width="2" stroke-dasharray="6 4"/>`;
  g+=`<polyline points="${d.obs.map((v,i)=>`${X(i+1)},${Y(v)}`).join(" ")}" fill="none" stroke="var(--a1)" stroke-width="2.4"/>`;
  d.obs.forEach((v,i)=>{g+=`<g data-tip="<b>más de ${i+1} acciones</b>observado ${(v*100).toFixed(1)}% · cadena ${(d.mod[i]*100).toFixed(1)}%"><circle cx="${X(i+1)}" cy="${Y(v)}" r="9" fill="transparent"/><circle cx="${X(i+1)}" cy="${Y(v)}" r="3" fill="var(--a1)"/></g>`;});
  return g+`</svg>`+leyenda(SW(C_FOCO,"observado"),SW("var(--tx2)","lo que predice la cadena (punteado)",true),
   `<span class="leg">torneo ${esc(d.t)} · distancia máxima ${(+d.ks).toFixed(3)}</span>`);
 },
 prog(d,fid){
  const k=ESTADO[fid]??"L",fs=d.filter(x=>x[k]);
  const sel=seg(fid,[["L","llegar"],["tau","tiempo hasta llegar"]]);
  if(!fs.length)return sel+vacio("Ninguna era evaluable para este estimando.");
  return sel+bosque(fs.map(x=>({etq:x.etq,sub:(x.mia?"esta historia · ":"")+`q = ${(+x[k].q).toFixed(3)}`,
   marcas:[{v:x[k].v,ic:x[k].ic,lleno:x[k].r,q:x[k].q,nota:x[k].r?"sobrevive a la corrección":"no sobrevive a la corrección"}]})),
   v=>pct(v),{refTxt:"LIGA DE LOS MISMOS TORNEOS"})+leyenda(SW(C_FOCO,"sobrevive"),SW("var(--tx2)","no sobrevive",true));
 },
 jugada(d){
  const z=d.zonas;
  return pitch((s)=>{
   const cx=q=>(Math.floor(q/NY)+.5)*cw*s,cy=q=>(q%NY+.5)*ch*s;
   const jit=i=>((i*37)%11-5)*s*.9;
   let g=`<rect x="${4*cw*s}" y="0" width="${cw*s}" height="${A*s}" fill="var(--a1)" fill-opacity=".10"/>`;
   const pts=z.map((q,i)=>[cx(q)+jit(i),cy(q)+jit(i+3)]);
   g+=`<polyline points="${pts.map(p=>p.map(v=>v.toFixed(1)).join(",")).join(" ")}" fill="none" stroke="var(--a1)" stroke-width="2.2" stroke-opacity=".8"/>`;
   pts.forEach(([x,y],i)=>{const ult=i===pts.length-1;
    const tip=ult?"<b>llega a la franja</b>":`<b>acción ${i+1}</b>${esc((d.jugadores||[])[i]||"")}${d.tipos&&d.tipos[i]?" · "+esc(d.tipos[i]):""}`;
    g+=`<g data-tip="${tip}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${ult?9:8}" fill="${ult?"var(--a1)":"var(--bg)"}" stroke="var(--a1)" stroke-width="2"/>
     <text x="${x.toFixed(1)}" y="${(y+4).toFixed(1)}" text-anchor="middle" font-size="10.5" font-family="var(--mono)" fill="${ult?"var(--bg)":"var(--tx)"}" pointer-events="none">${ult?"★":i+1}</text></g>`;});
   return g;});
 },
 p4(d){
  const W=560,H=320,m=52,ps=d.puntos,xs=ps.map(p=>p.rel_E_T),ys=ps.map(p=>Math.exp(p.D_L)-1);
  const lo=a=>Math.min(0,...a),hi=a=>Math.max(0,...a),pad=a=>(hi(a)-lo(a))*.12||.01;
  const X=v=>m+(v-lo(xs)+pad(xs))/(hi(xs)-lo(xs)+2*pad(xs))*(W-2*m),Y=v=>H-m-(v-lo(ys)+pad(ys))/(hi(ys)-lo(ys)+2*pad(ys))*(H-2*m);
  let g=`<svg viewBox="0 0 ${W} ${H}" data-p4="1" style="max-width:${W}px">
   <line x1="${X(0)}" x2="${X(0)}" y1="${m/2}" y2="${H-m}" stroke="#fff" stroke-opacity=".25" stroke-dasharray="4 4"/>
   <line x1="${m}" x2="${W-m/2}" y1="${Y(0)}" y2="${Y(0)}" stroke="#fff" stroke-opacity=".25" stroke-dasharray="4 4"/>
   <text x="${W-m/2}" y="${H-m+30}" text-anchor="end" fill="var(--tx2)" font-size="11">duración contra la liga →</text>
   <text x="${m-34}" y="${m/2}" fill="var(--tx2)" font-size="11" transform="rotate(-90 ${m-34} ${m/2})" text-anchor="end">llegada contra la liga →</text>`;
  ps.forEach(p=>{const x=X(p.rel_E_T),y=Y(Math.exp(p.D_L)-1);
   g+=`<g data-tip="<b>${esc(p.nom||p.hid)}</b>duración ${pct(p.rel_E_T)} · llegada ${pct(Math.exp(p.D_L)-1)}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7" fill="var(--a1)"/>
    <text x="${(x+10).toFixed(1)}" y="${(y+4).toFixed(1)}" fill="var(--tx)" font-size="11">${esc(p.nom||p.hid)}</text></g>`;});
  const r=d.valor&&d.valor.rho;
  return g+`</svg>`+leyenda(`<span class="leg">ρ de Spearman = ${r==null?"—":(+r).toFixed(2)} con ${ps.length} eras: descriptiva</span>`);
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
let FIGDATOS={};
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
function frase(b){
 const ad=b.adenda?`<span class="adenda" data-tip="${esc(ADENDA(b.adenda,b.n_adenda))}">adenda ${b.n_adenda||1}</span>`:"";
 return `<p class="fr${b.nulo?" nulo":""}" data-nivel="${b.nivel}" data-capa="1"${b.portada?` data-portada="${b.portada}"`:""}><span class="nv nv-${b.nivel}" data-tip="${esc(NIVEL[b.nivel])}">${b.nivel}</span><span class="tx">${b.html}${ad}</span></p>`;
}
function bloque(b,sid,i){
 const cp=b.capa?` data-capa="${b.capa}"`:"";
 if(b.tipo==="frase")return frase(b);
 if(b.tipo==="nota")return `<div class="nota">${b.html}</div>`;
 if(b.tipo==="ejemplo")return `<div class="ejemplo"${cp}><u>en un partido</u>${b.html}</div>`;
 if(b.tipo==="hueco")return `<div class="hueco"${cp}><u>${["","frase","figura","ejemplo","método"][b.capa]||"hueco"} · pendiente</u>${b.html}</div>`;
 if(b.tipo==="plegable")return `<details class="plegable${b.capa===4?" metodo":""}"${cp}${MODO==="tecnica"&&b.capa===4?" open":""}><summary>${esc(b.titulo)}</summary>${b.html}</details>`;
 if(b.tipo==="fig"){
  const fid=`${sid}-${b.id}`;FIGDATOS[fid]={id:b.id,datos:b.datos};
  return `<div class="fig" data-fig-id="${fid}" data-fig="${b.id}"${cp}><div class="card">
   <div class="fig-tit">${esc(b.titulo)}</div>${b.pie?`<div class="nota" style="margin-top:.1rem;margin-bottom:.9rem">${esc(b.pie)}</div>`:""}
   <div class="lienzo"></div></div></div>`;}
 return "";
}
function seccion(s){
 let cuerpo;
 if(s.pendiente)cuerpo=`<div class="pendiente" data-pendiente="1"><b>Pendiente.</b> Esta sección mostrará ${esc(s.pendiente.que)}. Llega con ${esc(s.pendiente.adr)} (fase ${esc(s.pendiente.fase)}), preinscrita antes de medir.</div>`;
 else if(s.falta)cuerpo=vacio(`Falta <b>${esc(s.falta.archivo)}</b>. Esta sección no se pinta sin él.`,s.falta.comando);
 else cuerpo=s.bloques.map((b,i)=>bloque(b,s.id,i)).join("");
 return `<section id="${s.id}" class="rev" data-num="${esc(s.num)}"><div class="eyebrow">${esc(s.num)} · componente ${esc(s.comp)}</div>
  <h2>${esc(s.tit)}</h2>${cuerpo}</section>`;
}
const ACTOS=[
 ["acto1","Acto 1","El marco","Cómo se lee una posesión y en qué confiar. Es igual para las cinco historias."],
 ["acto2","Acto 2","Cómo juega","La era principal del técnico, contra la liga del mismo torneo."],
 ["acto3","Acto 3","De dónde viene eso","El club antes y después de él, y qué cambia cuando cambia de club."],
 ["cierre","Cierre","¿Nos creen?","El método puesto a prueba, sus límites y lo que falta."]];
function cabeza([id,n,t,p]){
 return `<div class="acto" id="${id}"><div class="eyebrow">${n}</div><h3>${t}</h3><p>${p}</p></div>`;
}
function traza(){
 const t=D.traza,c=t.commit;
 $("traza").innerHTML=`<span class="chip" data-tip="<b>código</b>commit con el que se generó esta página">commit ${esc(c.hash)}${c.sucio?" · con cambios":""}</span>`+
  t.insumos.map(x=>x.sha?`<span class="chip" data-tip="<b>${esc(x.archivo)}</b>sha256 ${esc(x.sha)}… · corrida del ${esc(x.fecha)}">${esc(x.archivo.replace(".json",""))} <span>${esc(x.fecha)}</span></span>`
   :`<span class="chip falta" data-tip="<b>falta</b>${esc(x.comando)}">${esc(x.archivo.replace(".json",""))} <span>falta</span></span>`).join("");
 $("pie").innerHTML=`Generado ${esc(t.generado)}. Los JSON de reports/ no se versionan: la huella de cada uno está en la portada (modo técnico).`;
}
let HIST=null,MODO="sencilla";
function portada(h){
 const fr=[];
 h.acto2.concat(h.acto3).forEach(s=>(s.bloques||[]).forEach(b=>{if(b.tipo==="frase"&&b.portada)fr.push([b,s]);}));
 fr.sort((x,y)=>x[0].portada-y[0].portada);
 return fr.map(([b,s])=>`<a href="#${s.id}" data-ancla="${s.id}">${frase(b).replace('<p class="fr','<p data-en-portada="1" class="fr').replace("</span></p>",`<span class="ir">→ ${esc(s.num)}</span></span></p>`)}</a>`).join("");
}
function render(hid){
 HIST=D.historias.find(h=>h.id===hid)||D.historias[0];
 FIGDATOS={};
 const h=HIST;
 $("titulo").innerHTML=`${esc(h.nombre.split(" ").slice(0,-1).join(" "))}<br><em>${esc(h.nombre.split(" ").slice(-1)[0])}</em>`;
 $("eras").innerHTML=h.eras.map(e=>`<span class="chip${e.club===h.principal?" pr":""}" data-tip="<b>${esc(e.club)}</b>${e.n} partidos${e.club===h.principal?" · era principal":""}">${esc(e.club)} <span>${e.n} partidos</span></span>`).join("");
 $("portada").innerHTML=portada(h);
 $("informe").innerHTML=cabeza(ACTOS[0])+D.acto1.map(seccion).join("")+
  cabeza(ACTOS[1])+h.acto2.map(seccion).join("")+
  cabeza(ACTOS[2])+h.acto3.map(seccion).join("")+
  cabeza(ACTOS[3])+D.cierre.map(seccion).join("");
 Object.keys(FIGDATOS).forEach(pintaFig);
 document.querySelectorAll("#informe section").forEach(s=>s.classList.add("on"));
 if(typeof IntersectionObserver!=="function")return;
}
function modo(m){
 MODO=m;document.body.classList.toggle("tecnica",m==="tecnica");
 document.querySelectorAll("details.metodo").forEach(d=>{d.open=(m==="tecnica");});
}
function segmento(el,ops,on,cb){
 el.innerHTML=`<div class="pill"></div>`+ops.map(([k,t])=>`<button data-k="${esc(k)}" class="${k===on?"on":""}">${esc(t)}</button>`).join("");
 el.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{
  el.querySelectorAll("button").forEach(x=>x.classList.toggle("on",x===b));colocaPill(el);cb(b.dataset.k);}));
 colocaPill(el);
}
function nav(){
 segmento($("segHist"),D.historias.map(h=>[h.id,h.nombre.split(" ").slice(-1)[0]]),D.historias[0].id,k=>{render(k);});
 segmento($("segActo"),ACTOS.map(a=>[a[0],a[1]]),"acto1",k=>{const el=$(k);if(el&&el.scrollIntoView)el.scrollIntoView({behavior:"smooth",block:"start"});});
 segmento($("segModo"),[["sencilla","sencilla"],["tecnica","técnica"]],"sencilla",k=>modo(k));
}
function arranca(){
 traza();
 render(D.historias[0].id);
 nav();
 modo("sencilla");
}
arranca();
</script></body></html>"""


if __name__ == "__main__":
    main()
