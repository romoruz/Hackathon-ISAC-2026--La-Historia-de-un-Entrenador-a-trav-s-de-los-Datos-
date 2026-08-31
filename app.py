"""
app.py — La historia de un entrenador, contada con datos.

DISEÑO
------
Oscuro, translucido, tipografia grande. Tres decisiones:

  1. VIDRIO (glassmorphism). Las tarjetas son rgba(255,255,255,.045) con
     backdrop-filter: blur(24px) y borde de 1px al 8% de opacidad. Es lo que
     produce la sensacion de profundidad de las interfaces de Apple sin
     recurrir a sombras pesadas.

  2. CANCHA VERDE. Un campo monocromo se lee como grafica; uno verde se lee
     como FUTBOL. Verde muy oscuro (#0f2a1c) con franjas de siega apenas
     visibles, para que conviva con el fondo negro sin gritar.

  3. TIPOGRAFIA CON SALTOS GRANDES. 5.5rem para el hero, 3rem para titulares,
     1.05rem para cuerpo. La jerarquia tiene que verse de golpe, no
     adivinarse.

SELECTORES
----------
Antes la app tomaba el primer artefacto que encontraba, asi que la huella
podia ser de un entrenador y las barras de otro sin que nada lo indicara.
Ahora club, entrenador y rival son EXPLICITOS, y si falta el artefacto de esa
pareja concreta se muestra el comando exacto para generarlo.

CONTENIDO
---------
Brief ISAC 2026: "que alguien que NO VIO LOS PARTIDOS entienda como juega el
equipo". Cero p-valores, cero lambdas, cero matrices en pantalla.

Uso:
    streamlit run app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import streamlit as st
from matplotlib.patches import FancyBboxPatch, Rectangle

st.set_page_config(page_title="La historia de un entrenador",
                   layout="wide", initial_sidebar_state="collapsed")

RAIZ = Path(__file__).resolve().parent
REPORTS = RAIZ / "reports"

# OJO: el nombre que se muestra NO siempre es el valor de la columna `team`.
# En los datos el America es "América" (sin "Club"), y filtrar por el nombre
# del selector devolvia CERO filas -> la app decia "se necesitan al menos dos
# etapas de entrenador" con un dataset perfectamente valido.
CLUBES = {
    "Club América": {"dir": RAIZ / "data" / "processed", "team": "América"},
    "Cruz Azul": {"dir": RAIZ / "data" / "processed_cruzazul", "team": "Cruz Azul"},
}

NX, NY, LARGO, ANCHO = 5, 4, 120.0, 80.0

TEXTO, GRIS = "#f5f5f7", "#8e8e93"
AZUL, ROJO, APAGADO = "#0a84ff", "#ff453a", "#3a3a3c"
CESPED, CESPED2, LINEA = "#0f2a1c", "#123020", "#3d6b52"

FASE = {"open": "juego abierto", "transition": "transición",
        "restart": "reinicio", "set_piece": "balón parado"}
CORTA = {"open": "abierto", "transition": "transición",
         "restart": "reinicio", "set_piece": "b. parado"}
TERCIO = ["propio", "propio", "medio", "rival", "rival"]
# StatsBomb: origen arriba-izquierda, `y` CRECE HACIA ABAJO. Un equipo que
# ataca hacia x=120 tiene el borde y=0 a su IZQUIERDA. La primera version tenia
# este vector al reves y TODOS los mapas salian espejeados.
# Verificado con Alejandro Zendejas (extremo derecho): 43.6% de sus acciones
# caen en iy=3, que por tanto es la banda DERECHA.
FRANJA = ["banda izquierda", "centro-izquierda", "centro-derecha", "banda derecha"]

mpl.rcParams.update({
    "figure.facecolor": "none", "axes.facecolor": "none",
    "savefig.facecolor": "none", "savefig.transparent": True,
    "text.color": TEXTO, "axes.labelcolor": GRIS,
    "xtick.color": GRIS, "ytick.color": GRIS,
    "font.family": "sans-serif",
    "font.sans-serif": ["SF Pro Display", "Inter", "Helvetica Neue",
                        "DejaVu Sans", "sans-serif"],
})

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;500;600;700;800&display=swap');

.stApp { background:
  radial-gradient(1100px 620px at 12% -8%, #10233a 0%, transparent 58%),
  radial-gradient(900px 520px at 92% 8%, #1a1030 0%, transparent 55%),
  #000000; }
.main .block-container { max-width: 1120px; padding: 3rem 1rem 7rem 1rem; }
html, body, [class*="css"] { font-family:'Inter',-apple-system,
  BlinkMacSystemFont,'SF Pro Display',sans-serif; }
#MainMenu, footer, header { visibility: hidden; }

.hero { font-size: 5.4rem; font-weight: 800; letter-spacing:-.055em;
  line-height:.95; color:#f5f5f7; margin:0 0 1.4rem 0; }
.hero-sub { font-size:1.3rem; font-weight:200; color:#8e8e93;
  line-height:1.55; max-width:36ch; }

.acto { font-size:.72rem; font-weight:700; letter-spacing:.3em;
  text-transform:uppercase; color:#0a84ff; margin-bottom:1rem; }
.titular { font-size:3.1rem; font-weight:700; letter-spacing:-.042em;
  line-height:1.06; color:#f5f5f7; margin:0 0 1.1rem 0; }
.bajada { font-size:1.12rem; font-weight:200; color:#8e8e93;
  line-height:1.62; max-width:56ch; }

.cifra { font-size:7rem; font-weight:800; letter-spacing:-.06em; line-height:.86;
  background:linear-gradient(135deg,#0a84ff 0%,#64d2ff 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  animation:subir .8s cubic-bezier(.16,1,.3,1); }
.cifra-pie { font-size:1rem; font-weight:300; color:#8e8e93; margin-top:1rem;
  line-height:1.5; max-width:24ch; }
.texto { font-size:1.1rem; font-weight:200; color:#d1d1d6; line-height:1.8; }
.texto b { color:#f5f5f7; font-weight:600; }

.vidrio { background:rgba(255,255,255,.045);
  backdrop-filter:blur(24px) saturate(150%);
  -webkit-backdrop-filter:blur(24px) saturate(150%);
  border:1px solid rgba(255,255,255,.085); border-radius:22px;
  padding:1.9rem 2rem; height:100%;
  transition:transform .3s cubic-bezier(.16,1,.3,1), border-color .3s ease; }
.vidrio:hover { transform:translateY(-4px);
  border-color:rgba(255,255,255,.16); }
.t-label { font-size:.7rem; font-weight:700; letter-spacing:.2em;
  text-transform:uppercase; color:#8e8e93; }
.t-valor { font-size:3.2rem; font-weight:700; letter-spacing:-.045em;
  color:#f5f5f7; line-height:1.05; margin-top:.6rem; }
.t-pie { font-size:.88rem; font-weight:300; color:#8e8e93; margin-top:.45rem; }

.nota { font-size:.95rem; font-weight:200; color:#8e8e93; line-height:1.7;
  border-left:2px solid rgba(255,255,255,.1); padding-left:1.3rem;
  margin-top:1.8rem; max-width:62ch; }
.pie-fig { font-size:.95rem; font-weight:200; color:#8e8e93; line-height:1.7;
  max-width:60ch; margin-top:.8rem; }
.sep { height:1px; border:none; margin:5.5rem 0 3.4rem 0;
  background:linear-gradient(90deg,rgba(255,255,255,.14),transparent); }

.chip { display:inline-block; font-size:.87rem; font-weight:500; color:#f5f5f7;
  background:rgba(255,255,255,.05); backdrop-filter:blur(14px);
  border:1px solid rgba(255,255,255,.1); border-radius:999px;
  padding:.5rem 1.05rem; margin:0 .45rem .6rem 0;
  transition:background .25s ease; }
.chip:hover { background:rgba(10,132,255,.16); }
.chip-n { color:#8e8e93; font-weight:300; }

@keyframes subir { from{opacity:0;transform:translateY(18px)} to{opacity:1} }
.aparece { animation:subir .7s cubic-bezier(.16,1,.3,1) both; }

div[data-testid="stSelectbox"] label { color:#8e8e93!important;
  font-size:.7rem!important; font-weight:700!important; letter-spacing:.2em;
  text-transform:uppercase; }
div[data-baseweb="select"] > div { background:rgba(255,255,255,.05)!important;
  backdrop-filter:blur(20px); border:1px solid rgba(255,255,255,.1)!important;
  border-radius:14px!important; color:#f5f5f7!important;
  font-size:1rem!important; padding:.2rem .3rem!important; }
div[data-baseweb="select"] > div:hover {
  border-color:rgba(10,132,255,.5)!important; }
ul[data-testid="stSelectboxVirtualDropdown"] { background:#12121a!important;
  border:1px solid rgba(255,255,255,.1)!important; border-radius:14px!important; }
div[data-testid="stExpander"] { border:1px solid rgba(255,255,255,.09)!important;
  border-radius:18px!important; background:rgba(255,255,255,.03)!important;
  backdrop-filter:blur(20px); }
div[data-testid="stExpander"] summary p { color:#8e8e93!important;
  font-weight:500!important; font-size:1rem!important; }
code { background:rgba(255,255,255,.06)!important; color:#64d2ff!important; }
</style>
"""


# ==========================================================================
@st.cache_data(show_spinner=False)
def leer_parquet(r: str):
    p = Path(r)
    return pl.read_parquet(p) if p.exists() else None


def json_donde(pred, patron: str):
    """Primer JSON de reports/ que cumple `pred`. None si ninguno."""
    for c in sorted(REPORTS.glob(patron)):
        try:
            d = json.loads(c.read_text())
        except Exception:
            continue
        if pred(d):
            return d
    return None


def falta(cmd: str, que: str) -> None:
    st.markdown(f'<div class="nota">Aún no existe {que} para esta pareja. '
                f'Generalo con:</div>', unsafe_allow_html=True)
    st.code(cmd, language="bash")


def parse(e: str):
    z, f = e.split("|")
    return int(z[1]), int(z[2]), f


def celda(ix: int, iy: int):
    w, h = LARGO / NX, ANCHO / NY
    return ix * w, iy * h, w, h


# ==========================================================================
# Cancha
# ==========================================================================
def cancha(ax, franjas: bool = True) -> None:
    """Campo verde oscuro. Un campo monocromo se lee como grafica; uno verde
    se lee como futbol."""
    ax.add_patch(FancyBboxPatch(
        (0, 0), LARGO, ANCHO, boxstyle="round,pad=0,rounding_size=2.5",
        facecolor=CESPED, edgecolor="none", zorder=0))
    if franjas:                       # siega, apenas perceptible
        for k in range(NX * 2):
            if k % 2 == 0:
                ax.add_patch(Rectangle((k * LARGO / (NX * 2), 0),
                                       LARGO / (NX * 2), ANCHO,
                                       facecolor=CESPED2, edgecolor="none",
                                       zorder=1))
    ln = dict(color=LINEA, lw=1.1, zorder=4, alpha=.85)
    ax.add_patch(Rectangle((1.5, 1.5), LARGO - 3, ANCHO - 3, fill=False, **ln))
    ax.plot([LARGO / 2, LARGO / 2], [1.5, ANCHO - 1.5], **ln)
    ax.add_patch(plt.Circle((LARGO / 2, ANCHO / 2), 9.15, fill=False, **ln))
    ax.add_patch(plt.Circle((LARGO / 2, ANCHO / 2), 0.8, color=LINEA,
                            zorder=4, alpha=.85))
    for x0, w in ((1.5, 15), (LARGO - 16.5, 15)):
        ax.add_patch(Rectangle((x0, ANCHO / 2 - 20.15), w, 40.3, fill=False, **ln))
    for x0, w in ((1.5, 4), (LARGO - 5.5, 4)):
        ax.add_patch(Rectangle((x0, ANCHO / 2 - 9.16), w, 18.32, fill=False, **ln))
    for x in (11, LARGO - 11):
        ax.add_patch(plt.Circle((x, ANCHO / 2), 0.7, color=LINEA, zorder=4,
                                alpha=.85))
    ax.set_xlim(-4, LARGO + 4)
    ax.set_ylim(-10, ANCHO + 4)
    ax.set_aspect("equal")
    ax.axis("off")


def fig_huella(top: list, dt: str):
    fig, ax = plt.subplots(figsize=(9.8, 6.6))
    fig.patch.set_alpha(0)
    cancha(ax)
    for ix in range(NX):
        for iy in range(NY):
            x, y, w, h = celda(ix, iy)
            ax.add_patch(Rectangle((x, y), w, h, fill=False,
                                   edgecolor="#ffffff", lw=.5, alpha=.07,
                                   zorder=3))
    if top:
        vmax = max(d["TV_exceso"] for d in top)
        agr: dict = {}
        for d in top:
            ix, iy, f = parse(d["estado"])
            agr.setdefault((ix, iy), {"v": 0.0, "f": set()})
            agr[(ix, iy)]["v"] = max(agr[(ix, iy)]["v"], d["TV_exceso"])
            agr[(ix, iy)]["f"].add(f)
        for (ix, iy), d in agr.items():
            v = d["v"] / vmax
            x, y, w, h = celda(ix, iy)
            ax.add_patch(FancyBboxPatch(
                (x + 1.2, y + 1.2), w - 2.4, h - 2.4,
                boxstyle="round,pad=0,rounding_size=1.8",
                facecolor=AZUL, alpha=.22 + .62 * v,
                edgecolor="#64d2ff", lw=1.2, zorder=5))
            ax.text(x + w / 2, y + h / 2,
                    "\n".join(sorted({CORTA[f] for f in d["f"]})),
                    ha="center", va="center", fontsize=10.5,
                    color="#ffffff", zorder=6, weight="600", linespacing=1.5)
    ax.annotate("", xy=(LARGO * .60, -5.5), xytext=(LARGO * .40, -5.5),
                arrowprops=dict(arrowstyle="->", color=GRIS, lw=1.2))
    ax.text(LARGO / 2, -9, "ataque", ha="center", fontsize=10, color=GRIS)
    fig.tight_layout(pad=0.2)
    return fig


def fig_jugador(m: np.ndarray, vmax: float, color: str):
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    fig.patch.set_alpha(0)
    cancha(ax, franjas=False)
    for ix in range(NX):
        for iy in range(NY):
            x, y, w, h = celda(ix, iy)
            v = m[ix, iy] / vmax if vmax else 0.0
            if v > .02:
                ax.add_patch(FancyBboxPatch(
                    (x + .8, y + .8), w - 1.6, h - 1.6,
                    boxstyle="round,pad=0,rounding_size=1.5",
                    facecolor=color, alpha=.14 + .74 * v,
                    edgecolor="none", zorder=5))
    fig.tight_layout(pad=0.2)
    return fig


def mapa_zonas(t: pl.DataFrame) -> np.ndarray:
    m = np.zeros((NX, NY))
    if t.height == 0:
        return m
    z = t["from_state"].to_numpy().astype(int) // 4
    for a, b in zip(z // NY, z % NY):
        if 0 <= a < NX and 0 <= b < NY:
            m[a, b] += 1
    return m / max(m.sum(), 1e-9)


def fig_barras(filas: list):
    n = len(filas)
    fig, ax = plt.subplots(figsize=(9.8, .95 * n + 1.4))
    fig.patch.set_alpha(0)
    y = np.arange(n)[::-1]
    for yy, f in zip(y, filas):
        act = f.get("activo", True)
        for off, val, col, sig in ((.17, f["dur"], AZUL, True),
                                   (-.17, f["rem"], ROJO, f["sig"])):
            ax.add_patch(FancyBboxPatch(
                (0, yy + off - .125), val, .25,
                boxstyle="round,pad=0,rounding_size=.08",
                facecolor=col if sig else APAGADO, edgecolor="none", zorder=3,
                alpha=1.0 if act else .32, mutation_aspect=.02))
            ax.text(val + (1.3 if val >= 0 else -1.3), yy + off,
                    f"{val:+.0f}%", va="center",
                    ha="left" if val >= 0 else "right", fontsize=11.5,
                    color=(TEXTO if sig else GRIS) if act else "#5a5a60",
                    weight="700")
    ax.axvline(0, color="#ffffff", lw=1, alpha=.18, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels([f["par"] for f in filas], fontsize=12)
    for tk, f in zip(ax.get_yticklabels(), filas):
        tk.set_color(TEXTO if f.get("activo", True) else "#5a5a60")
        tk.set_fontweight("600" if f.get("activo", True) else "400")
    ax.set_ylim(-.6, n - .4)
    lo = min([f["rem"] for f in filas] + [0]) - 16
    hi = max([f["dur"] for f in filas] + [f["rem"] for f in filas]) + 18
    ax.set_xlim(lo, hi)
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.scatter([], [], marker="s", s=110, color=AZUL, label="Duración de la posesión")
    ax.scatter([], [], marker="s", s=110, color=ROJO, label="Remates generados")
    leg = ax.legend(frameon=False, fontsize=11.5, loc="upper center", ncol=2,
                    bbox_to_anchor=(.5, 1.13))
    for t in leg.get_texts():
        t.set_color(GRIS)
    fig.tight_layout(pad=0.4)
    return fig


# ==========================================================================
def acto(n: str, tit: str, baj: str) -> None:
    st.markdown(f'<div class="aparece"><div class="acto">{n}</div>'
                f'<div class="titular">{tit}</div>'
                f'<div class="bajada">{baj}</div></div>', unsafe_allow_html=True)


def sep() -> None:
    st.markdown('<hr class="sep">', unsafe_allow_html=True)


def esp(h: str) -> None:
    st.markdown(f"<div style='height:{h}'></div>", unsafe_allow_html=True)


def vidrio(lab: str, val, pie: str) -> str:
    return (f'<div class="vidrio"><div class="t-label">{lab}</div>'
            f'<div class="t-valor">{val}</div>'
            f'<div class="t-pie">{pie}</div></div>')


# ==========================================================================
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    st.markdown('<div class="hero">La historia<br>de un entrenador</div>'
                '<div class="hero-sub">Ocho temporadas de Liga MX. Sin ver un '
                'solo partido: qué hace distinto cada entrenador y dónde lo '
                'hace.</div>', unsafe_allow_html=True)
    esp("2.6rem")

    # ----------------------------------------------------- selectores
    s1, s2, s3 = st.columns(3)
    with s1:
        club = st.selectbox("Club", list(CLUBES.keys()))
    cfg = CLUBES[club]
    equipo = cfg["team"]
    trans = leer_parquet(str(cfg["dir"] / "transitions.parquet"))
    if trans is None:
        sep()
        falta(f'dtdecoder phase0 --src eventos_completos_*.csv --club "{club}"',
              "la tabla de transiciones")
        st.stop()

    dts = (trans.filter((pl.col("team") == equipo) & pl.col("coach").is_not_null())
           .group_by("coach").len().sort("len", descending=True)["coach"].to_list())
    if len(dts) < 2:
        st.error("Se necesitan al menos dos etapas de entrenador.")
        st.stop()
    with s2:
        dt = st.selectbox("Entrenador", dts)
    with s3:
        rival = st.selectbox("Comparar contra", [c for c in dts if c != dt])

    ic = json_donde(lambda d: d.get("a") == dt and d.get("b") == rival, "ic_*.json")
    pj = json_donde(lambda d: d.get("a") == dt and d.get("b") == rival,
                    "plantel_*.json")
    indir = cfg["dir"].name

    # --------------------------------------------------------- ACTO I
    sep()
    acto("Acto I · el ritmo", "Tarda más en perder el balón",
         f"Cada vez que el {club} recupera la pelota bajo {dt}, la conserva "
         f"durante más acciones antes de que la jugada termine. No es una "
         f"impresión: está medido sobre miles de posesiones.")
    if ic:
        r = ic["resultados"][0]["E_T"]
        esp("2rem")
        c1, c2 = st.columns([1, 1.4])
        with c1:
            st.markdown(f'<div class="cifra">{r["diff_pct"]:+.0f}%</div>'
                        f'<div class="cifra-pie">acciones por posesión frente '
                        f'a {rival}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="texto"><b>{r["a"]:.1f} acciones</b> por '
                        f'posesión con {dt}, frente a <b>{r["b"]:.1f}</b> con '
                        f'{rival}.<br><br>Repitiendo el cálculo mil veces sobre '
                        f'muestras distintas de partidos, la diferencia siempre '
                        f'queda <b>entre {r["lo_pct"]:.0f}% y '
                        f'{r["hi_pct"]:.0f}%</b>.</div>', unsafe_allow_html=True)
        rem, gol = ic["resultados"][0]["P_remate"], ic["resultados"][0]["P_gol"]
        st.markdown(f'<div class="nota">Durar más no significó rematar más: la '
                    f'probabilidad de acabar en tiro cambió '
                    f'{rem["diff_pct"]:+.0f}% y la de gol '
                    f'{gol["diff_pct"]:+.0f}%. Volvemos a esto en el Acto '
                    f'IV.</div>', unsafe_allow_html=True)
    else:
        falta(f'python scripts/08_ic_derivados.py --a "{dt}" --b "{rival}" '
              f'--club "{club}" --indir data/{indir}', "el análisis de duración")

    # -------------------------------------------------------- ACTO II
    sep()
    acto("Acto II · el hábitat", "Y lo hace sobre todo aquí",
         f"De las veinte zonas del campo, solo unas pocas separan de verdad a "
         f"{dt} del resto de entrenadores del club. El resto del campo lo "
         f"juegan casi igual.")
    tabla, apellido = None, dt.split()[-1].lower()
    for c in REPORTS.glob("huella_*.parquet"):
        if apellido in c.stem.lower():
            tabla = pl.read_parquet(c)
            break
    if tabla is not None:
        top = (tabla.filter(pl.col("significativo") & (pl.col("z") >= 3)
                            & (pl.col("n") >= 50))
               .sort("TV_exceso", descending=True).head(10).to_dicts())
        esp("1.6rem")
        g1, g2 = st.columns([2.5, 1])
        with g1:
            st.pyplot(fig_huella(top, dt), use_container_width=True)
        with g2:
            esp(".8rem")
            chips = "".join(
                f'<div class="chip">{FRANJA[parse(d["estado"])[1]]}, tercio '
                f'{TERCIO[parse(d["estado"])[0]]}'
                f'<span class="chip-n"> · {FASE[parse(d["estado"])[2]]}</span>'
                f'</div>' for d in top[:5])
            st.markdown(chips, unsafe_allow_html=True)
        st.markdown('<div class="pie-fig">Solo se iluminan las zonas que superan '
                    'con claridad lo que produciría el azar. Las demás se '
                    'apagaron a propósito: más de la mitad de las diferencias '
                    'aparentes entre entrenadores es ruido de muestreo.</div>',
                    unsafe_allow_html=True)
    else:
        falta(f'python scripts/09_huella_efecto.py --unit coach --value "{dt}" '
              f'--baseline other_coaches --club "{club}" --indir data/{indir}',
              "la huella táctica")

    # ------------------------------------------------------- ACTO III
    sep()
    acto("Acto III · el factor humano",
         "No son los fichajes: los mismos jugadores cambiaron",
         "La objeción evidente es que cambió el plantel. Así que miramos solo a "
         "los futbolistas que jugaron con ambos entrenadores, y comparamos a "
         "cada uno consigo mismo.")
    if pj and "player_id" in trans.columns:
        n1, n3 = pj["nivel1_solapamiento"], pj["nivel3_intra_jugador"]
        camb = [j for j in n3 if j.get("cambio")]
        esp("2rem")
        for col, args in zip(st.columns(3), [
                ("Jugadores en común", n1["compartidos"],
                 f'de {n1["jugadores_en_a"]} que usó {dt.split()[-1]}'),
                ("Acciones heredadas",
                 f'{n1["pct_acciones_de_a_por_compartidos"]:.0f}%',
                 f'del plantel de {rival.split()[-1]}'),
                ("Cambiaron su juego", f"{len(camb)}/{len(n3)}",
                 "con datos suficientes en ambas etapas")]):
            col.markdown(vidrio(*args), unsafe_allow_html=True)

        if n1["pct_acciones_de_a_por_compartidos"] < 45:
            st.markdown(f'<div class="nota">Ojo: el solapamiento de plantilla es '
                        f'bajo ({n1["pct_acciones_de_a_por_compartidos"]:.0f}%). '
                        f'Con pocos jugadores en común este contraste pierde '
                        f'fuerza, y conviene decirlo.</div>',
                        unsafe_allow_html=True)
        if camb:
            esp("2.4rem")
            sel = st.selectbox("Ver un jugador", [j["player"] for j in camb])
            jid = next(j["player_id"] for j in camb if j["player"] == sel)
            sub = trans.filter(pl.col("player_id") == jid)
            ma = mapa_zonas(sub.filter(pl.col("coach") == rival))
            mb = mapa_zonas(sub.filter(pl.col("coach") == dt))
            vmax = max(ma.max(), mb.max(), 1e-9)
            esp(".8rem")
            q1, q2 = st.columns(2)
            with q1:
                st.markdown(f'<div class="t-label">Con {rival}</div>',
                            unsafe_allow_html=True)
                st.pyplot(fig_jugador(ma, vmax, ROJO), use_container_width=True)
            with q2:
                st.markdown(f'<div class="t-label">Con {dt}</div>',
                            unsafe_allow_html=True)
                st.pyplot(fig_jugador(mb, vmax, AZUL), use_container_width=True)
            st.markdown('<div class="pie-fig">Mismo futbolista, misma cancha, '
                        'distinto reparto de sus intervenciones. Eso no lo '
                        'explica el mercado de fichajes.</div>',
                        unsafe_allow_html=True)
    else:
        falta(f'python scripts/11_confusion_plantel.py --a "{dt}" --b "{rival}" '
              f'--club "{club}" --indir data/{indir}', "el control de plantel")

    # -------------------------------------------------------- ACTO IV
    sep()
    acto("Acto IV · el matiz", "Durar no es lo mismo que hacer daño",
         f"Dos entrenadores pueden alargar la posesión por motivos opuestos. "
         f"Uno la usa para llegar; otro, para controlar el partido. Todas las "
         f"comparaciones disponibles del {club}.")
    # Solo parejas del CLUB seleccionado: antes se mezclaban America y Cruz
    # Azul en la misma grafica sin que nada lo indicara.
    filas = []
    for c in sorted(REPORTS.glob("ic_*.json")):
        d = json.loads(c.read_text())
        if not (d.get("a") and d.get("b")):
            continue
        if d["a"] not in dts or d["b"] not in dts:
            continue
        r0 = d["resultados"][0]
        filas.append({"par": f'{d["a"].split()[-1]} vs {d["b"].split()[-1]}',
                      "dur": r0["E_T"]["diff_pct"],
                      "rem": r0["P_remate"]["diff_pct"],
                      "sig": r0["P_remate"]["excluye_cero"],
                      "activo": d["a"] == dt and d["b"] == rival})
    filas.sort(key=lambda f: (not f["activo"], -abs(f["dur"])))
    if filas:
        esp("1.8rem")
        st.pyplot(fig_barras(filas), use_container_width=True)
        st.markdown('<div class="pie-fig">Las barras apagadas son diferencias '
                    'que el azar explica por sí solo. Cuando la de remates es '
                    'corta y la de duración larga, el equipo retiene sin generar '
                    'más peligro: controla. Cuando ambas crecen, la posesión se '
                    'convierte en ataque.</div>', unsafe_allow_html=True)

    sep()
    with st.expander("Lo que este análisis no puede decir"):
        st.markdown("""
**No dice quién es mejor entrenador.** Describe estilo, no resultados. La
probabilidad de gol no difirió con claridad en ninguna comparación.

**No mide la calidad de ejecución.** Un pase perfecto y uno mediocre hacia la
misma zona cuentan igual.

**No prueba causalidad.** Detecta que una etapa difiere de otra; no demuestra
que el entrenador sea la causa. El Acto III acota mucho esa duda, pero aunque
el jugador sea el mismo, sus compañeros y sus rivales cambian.

**No ve lo que pasa sin balón.** Presión, líneas y altura del bloque quedan
fuera del alcance del modelo.

**Las fechas de partido son reconstruidas**, no oficiales. Las etapas con
cambio de entrenador a media temporada son las menos fiables.
""")


if __name__ == "__main__":
    main()
