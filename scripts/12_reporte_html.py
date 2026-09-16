#!/usr/bin/env python3
"""
12_reporte_html.py — Genera un reporte HTML autocontenido.

POR QUE HTML Y NO STREAMLIT
---------------------------
Streamlit apila bloques en columnas y no hay CSS que cambie eso: no se pueden
hacer rejillas asimetricas, tarjetas de tamaños distintos ni barras laterales.
Un HTML propio no tiene ese techo, corre con doble clic sin servidor, y es
ademas el formato de entregable que pide el reto.

QUE PRODUCE
-----------
UN SOLO archivo `reporte.html` con:
  - todos los datos embebidos como JSON (no depende de rutas ni de red)
  - selectores de club / entrenador / rival en JavaScript puro
  - graficas dibujadas en SVG en el navegador, que se rehacen al cambiar
    de seleccion
  - sin dependencias externas: ni CDN, ni fuentes remotas, ni librerias

DISEÑO
------
Oscuro, tipo interfaz de iOS. Anillos de progreso al estilo de las apps de
salud, tarjetas de vidrio, tipografia grande con saltos marcados.

Uso:
    python scripts/12_reporte_html.py
    python scripts/12_reporte_html.py --out reporte.html
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import polars as pl

RAIZ = Path(__file__).resolve().parent.parent
REPORTS = RAIZ / "reports"

# Clubes con seccion profunda. Criterio preinscrito por ROL EN EL ARGUMENTO,
# nunca por magnitud del efecto: America es el foco del reto, Leon aporta el
# control negativo (equivalencia preinscrita) y Atlas el limite del metodo
# (Cocca I vs Cocca II: un tecnico difiere de si mismo).
# Ampliable sin tocar el codigo:  DTDECODER_CLUBES=america,leon,atlas,...
CLUBES_H7 = os.environ.get("DTDECODER_CLUBES", "america,leon,atlas").split(",")


def _descubre_clubes() -> dict:
    """Construye CLUBES desde `phase0_report.json`, no desde nombres a mano.

    El nombre del club tiene que ser EL MISMO que usan 25_pares_h4.py y
    27_robustez_h4.py, porque las claves de `pares_h4_v5.json` vienen de ahi.
    Si el reporte lo escribiera distinto ("Club León" contra "León"), la tabla
    de pares no casaria y la seccion saldria vacia sin decir por que.
    """
    out: dict = {}
    for slug in [s.strip() for s in CLUBES_H7 if s.strip()]:
        d = RAIZ / "data" / f"processed_api_{slug}"
        rp = d / "phase0_report.json"
        if not (d / "transitions.parquet").exists():
            print(f"[salto] {slug}: sin transitions.parquet en {d}",
                  file=sys.stderr)
            continue
        equipo = None
        if rp.exists():
            equipo = (json.loads(rp.read_text()).get("coaches") or {}).get("club")
        if not equipo:
            print(f"[salto] {slug}: phase0_report.json sin nombre de club",
                  file=sys.stderr)
            continue
        out[equipo] = {"dir": d, "team": equipo, "slug": slug}
    if not out:
        print("NINGUN club disponible. Revisa data/processed_api_*.",
              file=sys.stderr)
    return out


CLUBES = _descubre_clubes()
NX, NY = 5, 4
MIN_POSS = 1500


def mapa_zonas(t: pl.DataFrame) -> list[list[float]]:
    m = np.zeros((NX, NY))
    if t.height:
        z = t["from_state"].to_numpy().astype(int) // 4
        for a, b in zip(z // NY, z % NY):
            if 0 <= a < NX and 0 <= b < NY:
                m[a, b] += 1
    tot = max(m.sum(), 1e-9)
    return (m / tot).round(5).tolist()



def _slug(s: str) -> str:
    return s.lower().replace(" ", "")


# Archivos descartados por no declarar su club. Se imprimen al final de
# recolecta(): un descarte silencioso seria el mismo bug con otro sintoma.
_SIN_CLUB: dict[str, set] = {}


def _es_del_club(d: dict, equipo: str, origen: str) -> bool:
    """Clave compuesta (club, entrenador) -- paquete h2_11, patron bug #17.

    Jardine (America, San Luis), Ortiz (America, Monterrey), Larcamon (Leon,
    Cruz Azul) y Torrent (San Luis, Monterrey) dirigen en dos de los clubes
    del reporte. Filtrar solo por nombre de era mezcla sus artefactos entre
    clubes sin error ni aviso. Un JSON sin `club` NO se acepta: se registra y
    se avisa. `scripts/31_backfill_club.py` lo rellena de forma verificable.
    """
    c = d.get("club")
    if c is None:
        _SIN_CLUB.setdefault(origen, set()).add(equipo)
        return False
    return c == equipo


def defensa(lista: list[str], equipo: str) -> dict:
    """Todo el bloque D1 para un club, indexado por pareja `a|b`.

    Se lee de los JSON que dejan los scripts 16 y 18-22. Si falta alguno, la
    clave simplemente no aparece y el HTML muestra el comando que lo genera:
    es preferible a un reporte que finge tener datos que no tiene.
    """
    d: dict = {"pares": {}, "instrumento": {}, "cochran": {}}

    # --- q-valores de la familia D1-contrastes (ADR-48) -------------------
    # El q de la familia completa (script 22). Se indexa por (a, b, ix, iy),
    # NO por el texto del detalle: "z32 (84,50)" depende de como se formatee un
    # float, y si no calza exactamente `dict.get` cae al q de respaldo -- el de
    # la familia de 20 zonas del script 18. Sintoma: el mapa dibuja el borde con
    # un q y el texto de al lado cuenta con otro.
    import re as _re
    qmap: dict = {}
    fp = REPORTS / "fdr_presion.json"
    if fp.exists():
        for c in json.loads(fp.read_text()).get("contrastes", []):
            if c.get("club") != equipo:          # h2_11: clave compuesta
                continue
            if c["tipo"] == "zona":
                m = _re.match(r"z(\d)(\d)", str(c["detalle"]))
                if m:
                    qmap[(c["a"], c["b"], int(m.group(1)), int(m.group(2)))] = c["q"]
            else:
                qmap[(c["a"], c["b"], c["tipo"], c["detalle"])] = c["q"]

    # --- curva de decaimiento (script 19) ---------------------------------
    for p in REPORTS.glob("presion_indice_*.json"):
        j = json.loads(p.read_text())
        a, b = j["era_a"], j["era_b"]
        if not _es_del_club(j, equipo, p.name):
            continue
        if a not in lista or b not in lista or not j.get("curva"):
            continue
        d["pares"].setdefault(f"{a}|{b}", {})["curva"] = [
            {"k": c["k"], "pa": round(c["pi_a"], 4), "pb": round(c["pi_b"], 4),
             "la": round(c["ic_a"][0], 4), "ha": round(c["ic_a"][1], 4),
             "lb": round(c["ic_b"][0], 4), "hb": round(c["ic_b"][1], 4),
             "na": c["n_a"], "nb": c["n_b"]}
            for c in j["curva"]]

    # --- campo de presion por zona ----------------------------------------
    for p in REPORTS.glob("campo_presion_*.json"):
        j = json.loads(p.read_text())
        a, b = j["era_a"], j["era_b"]
        if not _es_del_club(j, equipo, p.name):
            continue
        if a not in lista or b not in lista:
            continue
        k = f"{a}|{b}"
        zs = []
        for z in j["zonas"]:
            q = qmap.get((a, b, z["ix"], z["iy"]), z["q"])
            zs.append({"ix": z["ix"], "iy": z["iy"],
                       "pa": round(z["pi_a"], 4), "pb": round(z["pi_b"], 4),
                       "d": round(z["delta"], 4), "q": round(float(q), 4),
                       "na": z["n_a"], "nb": z["n_b"]})
        d["pares"].setdefault(k, {})["zonas"] = zs
        d["pares"][k]["tercios"] = j.get("tercios", [])
        d["pares"][k]["pi_a"] = round(j["pi_marginal_a"], 4)
        d["pares"][k]["pi_b"] = round(j["pi_marginal_b"], 4)
        d["cochran"][k] = {"phi_a": round(j.get("cochran_phi_mediana_a", 0), 2),
                           "phi_b": round(j.get("cochran_phi_mediana_b", 0), 2)}

    # --- nivel en k>=k0 ----------------------------------------------------
    for p in REPORTS.glob("nivel_calibracion_*.json"):
        j = json.loads(p.read_text())
        a, b = j["era_a"], j["era_b"]
        k = f"{a}|{b}"
        if not _es_del_club(j, equipo, p.name):
            continue
        if a not in lista or b not in lista or "nivel" not in j:
            continue
        nv = j["nivel"]
        q = qmap.get((a, b, "nivel", f"k>={j.get('k0', 3)}"))
        d["pares"].setdefault(k, {})["nivel"] = {
            "k0": j.get("k0", 3), "pa": round(nv["pi_a"], 4),
            "pb": round(nv["pi_b"], 4), "dif": round(nv["diff"], 4),
            "q": None if q is None else round(float(q), 4),
            "na": nv["n_a"], "nb": nv["n_b"]}

    # --- instrumento: ¿la presion sirve? ----------------------------------
    for p in sorted(REPORTS.glob("calibracion_*.json")):
        j = json.loads(p.read_text())
        # h2_11: este era el caso ACTIVO del patron #17. Sin el filtro, la
        # calibracion de Jardine en San Luis podia pintarse como la del
        # America (y la de Larcamon en Cruz Azul como la de Leon), segun el
        # orden en que el sistema de archivos devolviera el glob.
        if not _es_del_club(j, equipo, p.name):
            continue
        for era, v in j.get("eras", {}).items():
            if era in lista:
                d["instrumento"][era] = {
                    "efecto": round(v["efecto_corregido"], 4),
                    "viejo": round(v.get("efecto_definicion_vieja", 0), 4)}

    # --- cantidades concedidas, estandarizadas por rival ------------------
    for p in REPORTS.glob("estandarizacion_defense_*.json"):
        for r in json.loads(p.read_text()):
            a, b = r["era_a"], r["era_b"]
            if not _es_del_club(r, equipo, p.name):
                continue
            if a not in lista or b not in lista:
                continue
            dd = r["diferencias"]
            d["pares"].setdefault(f"{a}|{b}", {})["concede"] = {
                "acciones": {"a": round(r["std_a"]["acciones_por_posesion"], 3),
                             "b": round(r["std_b"]["acciones_por_posesion"], 3),
                             "sig": dd["acciones_por_posesion"]["significativa_sin_corregir"]},
                "remate": {"a": round(r["std_a"]["tasa_remate"], 4),
                           "b": round(r["std_b"]["tasa_remate"], 4),
                           "sig": dd["tasa_remate"]["significativa_sin_corregir"]},
                "cobertura": round(min(r["masa_cubierta_a"], r["masa_cubierta_b"]), 3),
                "soporte": r["n_soporte"]}
    return d


# Patrones de nombre de estado por si algún día son cadenas. Con enteros no se
# usan: la ruta principal es la fórmula de `mapa_zonas`.
_PATRONES = [
    ("z<ix><iy>|fase", re.compile(r"^z(\d)(\d)\b")),
    ("z<ix>_<iy>",     re.compile(r"^z(\d+)[_,\-](\d+)")),
    ("(<ix>,<iy>)",    re.compile(r"^\(?(\d+)\s*,\s*(\d+)\)?")),
]


def resuelve_estados(estados: list, absorbentes: set, tope: int | None = None) -> tuple:
    """Devuelve (zonas, abs, diagnostico). `zonas[i]` es [ix, iy] o None.

    RUTA PRINCIPAL — estados enteros. Se usa la MISMA descodificación que
    `mapa_zonas()` emplea desde hace versiones para los mapas de jugador:

        z = estado // n_fases ;  ix = z // NY ;  iy = z % NY

    Escribir una segunda fórmula sería el bug #2 (dos recetas para lo mismo), y
    ésta ya está validada: es la que produce los mapas que la verificación del
    eje Y contrastó contra tres jugadores de banda conocida.

    `n_fases` se deriva de los datos. Si no sale un entero limpio, se rechaza en
    vez de redondear y devolver zonas plausibles pero equivocadas.
    """
    trans = [e for e in estados if e not in absorbentes]
    if not trans:
        return None, None, "no hay estados transitorios"

    if all(isinstance(e, (int, np.integer)) for e in trans):
        nz = NX * NY
        # Se deriva del INDICE MAXIMO, no de cuantos estados se observaron: una
        # era corta puede no visitar nunca alguna combinacion zona x fase, y
        # contarlos daria 79 en vez de 80. Eso tiraba el tablero de Solari y
        # Herrera sin que faltara ningun dato real.
        # El espacio de estados es propiedad del ARTEFACTO, no de la era: una
        # era corta puede no visitar nunca alguna combinacion zona x fase. Por
        # eso el tope se calcula sobre TODO el club y se pasa aqui; el maximo
        # local es solo el respaldo.
        tope = tope or (max(int(e) for e in trans) + 1)
        if tope % nz != 0:
            return None, None, (f"el indice mas alto es {tope-1}: {tope} no es "
                                f"multiplo de {nz} zonas ({NX}x{NY}), la malla "
                                f"del artefacto no coincide con la del reporte")
        nf = tope // nz
        zonas, absv = [], []
        for e in estados:
            if e in absorbentes:
                zonas.append(None)
                absv.append(1)
                continue
            z = int(e) // nf
            ix, iy = z // NY, z % NY
            zonas.append([ix, iy] if 0 <= ix < NX and 0 <= iy < NY else None)
            absv.append(0)
        malos = sum(1 for i, z in enumerate(zonas) if z is None and not absv[i])
        if malos:
            return None, None, f"{malos} estados caen fuera de la malla {NX}x{NY}"
        return zonas, absv, (f"indices enteros, {nf} fases x {nz} zonas "
                             f"(misma formula que mapa_zonas)")

    # RUTA ALTERNATIVA — estados con nombre. No se usa hoy; se conserva por si
    # el formato del artefacto cambia.
    mejor, nom, aciertos = None, "ninguno", 0
    for nombre, rx in _PATRONES:
        k = sum(1 for e in trans if rx.match(str(e)))
        if k > aciertos:
            mejor, nom, aciertos = rx, nombre, k
    cob = aciertos / len(trans)
    if cob < 0.8:
        return None, None, (f"estados no numericos y ningun patron los reconoce "
                            f"(mejor: {nom}, {cob:.0%}). Ejemplos: {trans[:4]}")
    zonas, absv = [], []
    for e in estados:
        m = mejor.match(str(e)) if e not in absorbentes else None
        zonas.append([int(m.group(1)), int(m.group(2))] if m else None)
        absv.append(1 if e in absorbentes else 0)
    return zonas, absv, f"patron '{nom}' resuelve el {cob:.0%}"


def nombra_absorbentes(t, est: list, absv: list, absorbentes: set) -> tuple:
    """Pone nombre a los absorbentes, que en el parquet son enteros sin etiqueta.

    HISTORIAL DE DOS INTENTOS FALLIDOS, porque explica el criterio actual:

      v1, por FRECUENCIA global: dejo REMATE y BALON FUERA intercambiados.
      v2, por GRADIENTE en puntos porcentuales sobre el eje del campo: llamo
          REMATE a la PERDIDA, porque la perdida tambien crece hacia la
          porteria rival (11.48 -> 27.51 = +16 pp) y parte de una base alta,
          asi que su subida ABSOLUTA supera la del remate (0.00 -> 10.92).

    v3, el actual, en tres pasos:

      1. PERDIDA = la de mas masa. Definicional: casi toda posesion se pierde.
      2. GOL y REMATE = las dos que NO EXISTEN en el tercio propio. Es un
         COCIENTE, no una resta. Un remate desde tu propia area es casi
         imposible; perder el balon ahi, no.
      3. De esas dos, la mas rara es el GOL.

    Validado contra las cifras reales de cuatro entrenadores: acierta los cuatro
    estados en los cuatro casos.

    Devuelve (fin, tabla). La tabla se imprime para que sea verificable: la fila
    REMATE debe ser ~0 en el tercio propio y grande en el rival.
    """
    idx_abs = [i for i, a in enumerate(absv) if a]
    if not idx_abs:
        return {}, "sin absorbentes"

    d = t.with_columns(((pl.col("from_state") // 4) // NY).alias("_ix"))
    tot = dict(d.group_by("_ix").len().iter_rows())
    cnt = {}
    filtro = (pl.col("is_absorbing") if "is_absorbing" in d.columns
              else pl.col("to_state").is_in(list(absorbentes)))
    for ix, to, c in d.filter(filtro).group_by(["_ix", "to_state"]).len().iter_rows():
        cnt[(ix, to)] = c

    perfil, masa = {}, {}
    for i in idx_abs:
        e = est[i]
        perfil[i] = [cnt.get((ix, e), 0) / max(1, tot.get(ix, 1)) for ix in range(NX)]
        masa[i] = sum(cnt.get((ix, e), 0) for ix in range(NX))

    fin = {}
    # (1) la perdida es, por definicion, el desenlace de la mayoria
    perd = max(idx_abs, key=lambda i: masa[i])
    fin[perd] = "PERDIDA"
    resto = [i for i in idx_abs if i != perd]

    if resto:
        # (2) concentracion hacia adelante: cociente, no diferencia
        atras = lambda i: perfil[i][0] + perfil[i][1]          # noqa: E731
        alante = lambda i: perfil[i][-1] + perfil[i][-2]       # noqa: E731
        conc = {i: alante(i) / (atras(i) + alante(i) + 1e-12) for i in resto}
        ofen = sorted(resto, key=lambda i: -conc[i])[:2]
        for i in resto:
            if i not in ofen:
                fin[i] = "BALON FUERA"
        # (3) de las dos ofensivas, la mas rara es el gol
        for k, i in enumerate(sorted(ofen, key=lambda i: masa[i])):
            fin[i] = "GOL" if k == 0 else "REMATE"

    filas = [f"{'estado':>8} {'nombre':>12} {'conc.adelante':>14}  "
             f"tasa por tercio (propio->rival)"]
    for i in sorted(idx_abs, key=lambda i: -(perfil[i][-1])):
        cc = (perfil[i][-1] + perfil[i][-2]) / (sum(perfil[i][:2]) + perfil[i][-1]
                                                + perfil[i][-2] + 1e-12)
        tt = " ".join(f"{100*v:5.2f}" for v in perfil[i])
        filas.append(f"{str(est[i]):>8} {fin.get(i,'?'):>12} {cc:14.2f}  {tt}")
    return fin, "\n      ".join(filas)


def tope_estados(sub: pl.DataFrame) -> int | None:
    """Indice mas alto + 1 sobre TODO el club. Define el espacio de estados."""
    try:
        col = pl.concat([sub["from_state"], sub["to_state"]])
        tr = sub.filter(~pl.col("is_absorbing"))["to_state"] \
            if "is_absorbing" in sub.columns else col
        m = max(int(sub["from_state"].max()), int(tr.max()))
        return m + 1
    except Exception:                                   # noqa: BLE001
        return None


def lift_ruta(t: pl.DataFrame, zi: dict, fin: dict, nz: int,
              min_sop: int = 10, min_gol: int = 100) -> dict:
    """P(visita zona | desenlace) / P(visita zona), por desenlace.

    `zi` mapea estado -> indice de zona. Devuelve, por nombre de desenlace, el
    lift por zona (o `None` si el soporte no llega), el soporte, y la puerta del
    modo gol.
    """
    fp = (t.filter(pl.col("is_absorbing"))
           .group_by("poss_uid").agg(pl.col("to_state").last().alias("_f")))
    n_tot = fp.height
    if not n_tot:
        return {}

    vis = (t.with_columns(pl.col("from_state").replace_strict(zi, default=None)
                            .alias("_z"))
            .drop_nulls("_z").select(["poss_uid", "_z"]).unique())
    marg = dict(vis.group_by("_z").agg(pl.col("poss_uid").n_unique().alias("n"))
                   .iter_rows())

    out = {}
    for est_abs, nombre in fin.items():
        if nombre not in ("REMATE", "GOL"):
            continue
        pos = fp.filter(pl.col("_f") == int(est_abs)).select("poss_uid")
        n_d = pos.height
        # La puerta del modo gol: con pocos goles casi todas las zonas caerian
        # por soporte y las que quedaran serian ruido con aspecto de hallazgo.
        if nombre == "GOL" and n_d < min_gol:
            out[nombre] = {"n": n_d, "bloqueado": True, "minimo": min_gol}
            continue
        if n_d < 30:
            out[nombre] = {"n": n_d, "bloqueado": True, "minimo": 30}
            continue

        cnt = dict(vis.join(pos, on="poss_uid", how="semi")
                      .group_by("_z").agg(pl.col("poss_uid").n_unique().alias("n"))
                      .iter_rows())
        lift, sop = {}, {}
        for z in range(nz):
            c = cnt.get(z, 0)
            sop[z] = c
            m = marg.get(z, 0)
            # supresion: sin soporte no se emite cociente, se emite nada
            lift[z] = round((c / n_d) / (m / n_tot), 3) if (c >= min_sop and m) else None
        out[nombre] = {"n": n_d, "bloqueado": False, "lift": lift,
                       "soporte": sop, "min_sop": min_sop}
    return out


def cadena_empirica(sub: pl.DataFrame, coach: str, umbral: float = 0.004,
                    tope: int | None = None) -> dict:
    """Matriz de transición empírica de una era, en formato disperso.

    Es la MISMA cadena que estima el pipeline, sin encogimiento: aquí no se hace
    inferencia, se hace pedagogía. El simulador existe para que alguien vea de
    dónde salen E[T] y P(gol), no para producir un número nuevo.

    Dispersa porque una matriz 84x84 densa por entrenador infla el HTML sin
    aportar: la mayoría de renglones tienen menos de veinte destinos con masa.
    `umbral` recorta la cola y se RENORMALIZA, o el simulador se quedaría
    colgado en un estado cuya fila no suma 1.
    """
    t = sub.filter(pl.col("coach") == coach)
    if t.height == 0:
        return {}

    # La absorción sale de la COLUMNA, no de adivinar por el nombre.
    if "is_absorbing" in t.columns:
        absorbentes = set(t.filter(pl.col("is_absorbing"))["to_state"].unique().to_list())
        origen = "columna is_absorbing"
    else:
        # Sin la columna: absorbente = estado al que se llega y del que nunca
        # se sale. Es la definición, no una heurística sobre el nombre.
        salen = set(t["from_state"].unique().to_list())
        llegan = set(t["to_state"].unique().to_list())
        absorbentes = llegan - salen
        origen = "estados sin transiciones de salida (falta is_absorbing)"
    if not absorbentes:
        print(f"[salto] {coach}: no encuentro estados absorbentes", file=sys.stderr)
        return {}

    est = sorted(set(t["from_state"].to_list()) | set(t["to_state"].to_list()))
    zonas, absv, diag = resuelve_estados(est, absorbentes, tope)
    if zonas is None:
        print(f"[salto] simulador de {coach}: {diag}", file=sys.stderr)
        return {}
    idx = {e: i for i, e in enumerate(est)}

    filas: dict[int, list] = {}
    cuenta = t.group_by(["from_state", "to_state"]).len().rename({"len": "n"})
    tot = dict(cuenta.group_by("from_state").agg(pl.col("n").sum()).iter_rows())
    for f, d, c in cuenta.iter_rows():
        pr = c / tot[f]
        if pr >= umbral:
            filas.setdefault(idx[f], []).append([idx[d], round(pr, 5)])
    for k, v in filas.items():
        s_ = sum(x[1] for x in v)
        for x in v:
            x[1] = round(x[1] / s_, 5)

    prim = (t.sort("event_index").group_by("poss_uid").first()
             .group_by("from_state").len())
    tp = prim["len"].sum()
    inicial = [[idx[f], round(c / tp, 5)] for f, c in prim.iter_rows()]

    largos = t.group_by("poss_uid").len()["len"].to_list()
    hist = [0] * 31
    for L in largos:
        hist[min(int(L), 30)] += 1

    fin, tabla = nombra_absorbentes(t, est, absv, absorbentes)

    # ---- agregado POR ZONA para el modo explorar --------------------
    # Se suman CONTEOS y luego se normaliza. Promediar las filas de las cuatro
    # fases daria el mismo peso a una fase con 8,000 acciones y a otra con 200.
    zdest: dict[int, dict] = {}          # zona -> {zona_destino: conteo}
    zfin: dict[int, dict] = {}           # zona -> {absorbente: conteo}
    zvis: dict[int, int] = {}            # zona -> veces que el balon estuvo ahi
    zi = {e: (z[0] * NY + z[1]) if z else None for e, z in zip(est, zonas)}
    for f, d, c in cuenta.iter_rows():
        a = zi.get(f)
        if a is None:
            continue
        zvis[a] = zvis.get(a, 0) + c
        if d in absorbentes:
            zfin.setdefault(a, {})[str(d)] = zfin.setdefault(a, {}).get(str(d), 0) + c
        else:
            b = zi.get(d)
            if b is not None:
                zdest.setdefault(a, {})[b] = zdest.setdefault(a, {}).get(b, 0) + c

    zona_mat = {}
    for a, tot_a in zvis.items():
        dst = sorted(zdest.get(a, {}).items(), key=lambda kv: -kv[1])
        fin_a = zfin.get(a, {})
        zona_mat[a] = {
            "n": tot_a,
            # `mismo` es la auto-transicion: el balon se queda en la zona. Es el
            # 40% de E[T] segun `05_auto_transiciones.py`, asi que ocultarlo
            # falsearia el reparto.
            "dest": [[b, round(c / tot_a, 4)] for b, c in dst[:8]],
            "fin": {k: round(c / tot_a, 4) for k, c in fin_a.items()},
            "sigue": round(sum(c for _, c in dst) / tot_a, 4),
        }
    tot_v = max(sum(zvis.values()), 1)
    zona_visitas = {a: round(v / tot_v, 6) for a, v in zvis.items()}

    # ---- nombre de cada indice de fase, LEIDO de los datos ----------
    # El estado es (zona x fase) y la fase es la mitad del espacio de estados,
    # pero estaba oculta. El orden NO se cablea: se toma la fase mas frecuente
    # para cada `from_state % nf`. Adivinarlo seria repetir el error de las
    # etiquetas de desenlace.
    fases = []
    if "phase" in t.columns:
        nf_ = max(1, len([z for z in zonas if z]) // max(1, NX * NY))
        pf = (t.with_columns((pl.col("from_state") % nf_).alias("_f"))
               .group_by(["_f", "phase"]).len().sort("len", descending=True))
        vistos: dict[int, str] = {}
        for f_, ph, _c in pf.iter_rows():
            vistos.setdefault(int(f_), str(ph))
        fases = [vistos.get(k, f"fase {k}") for k in range(nf_)]

    # ---- mezcla de tipos de accion por zona -------------------------
    # Separada en SIGUE y TERMINA: la accion que termina una posesion en el area
    # rival es un remate; la que la continua en campo propio es casi siempre un
    # pase. Mezclarlas diria que se remata desde todas partes.
    ztipo: dict[int, dict] = {}
    if "action_type" in t.columns:
        tt = (t.with_columns([
                pl.col("from_state").replace_strict(
                    {e: (z[0] * NY + z[1]) for e, z in zip(est, zonas) if z},
                    default=None).alias("_z")])
               .drop_nulls("_z"))
        col_abs = (pl.col("is_absorbing") if "is_absorbing" in t.columns
                   else pl.col("to_state").is_in(list(absorbentes)))
        for caso, filt in (("sigue", ~col_abs), ("fin", col_abs)):
            g = (tt.filter(filt).group_by(["_z", "action_type"]).len())
            tot_z: dict[int, int] = {}
            for z_, _a, c in g.iter_rows():
                tot_z[z_] = tot_z.get(z_, 0) + c
            for z_, a_, c in g.iter_rows():
                if tot_z.get(z_):
                    ztipo.setdefault(int(z_), {}).setdefault(caso, {})[str(a_)] = \
                        round(c / tot_z[z_], 4)

    print(f"[sim] {coach}: {len(est)} estados, {len(absorbentes)} absorbentes "
          f"({origen}); {diag}", file=sys.stderr)
    print(f"      {tabla}", file=sys.stderr)

    return {"estados": [str(e) for e in est], "zonas": zonas, "abs": absv,
            "fin": {str(est[i]): v for i, v in fin.items()},
            "zmat": zona_mat, "zvis": zona_visitas,
            "fases": fases, "ztipo": ztipo,
            "lift": lift_ruta(t, {e: (z[0] * NY + z[1])
                                  for e, z in zip(est, zonas) if z},
                              {str(est[i]): v for i, v in fin.items()}
                              if False else
                              {est[i]: v for i, v in fin.items()},
                              NX * NY),
            "filas": filas, "inicial": inicial,
            "hist": hist, "n_pos": len(largos),
            "nx": max((z[0] for z in zonas if z), default=4) + 1,
            "ny": max((z[1] for z in zonas if z), default=3) + 1}


def recolecta() -> dict:
    datos: dict = {"clubes": {}}
    for nombre, cfg in CLUBES.items():
        p = cfg["dir"] / "transitions.parquet"
        if not p.exists():
            print(f"[salto] {nombre}: sin transitions.parquet", file=sys.stderr)
            continue
        trans = pl.read_parquet(p)
        equipo = cfg["team"]
        sub = trans.filter((pl.col("team") == equipo) & pl.col("coach").is_not_null())
        if sub.height == 0:
            print(f"[salto] {nombre}: columna coach vacia", file=sys.stderr)
            continue

        dts = (sub.group_by("coach")
               .agg(pl.col("poss_uid").n_unique().alias("n"))
               .filter(pl.col("n") >= MIN_POSS)
               .sort("n", descending=True))
        # MISMO conjunto de unidades que H4 y que los generadores: el campo
        # `suficiente` de phase0 (>=25 partidos). Filtrar solo por posesiones
        # dejaba entrar eras cortas -- Leon/Bava, Atlas/Pineda -- que tienen
        # tarjeta y cadena en el reporte pero ni huella ni pares, porque los
        # generadores no les crearon artefactos, y que ademas no aparecen en
        # la tabla de los 60 pares. Un entrenador a medias es peor que uno
        # ausente: el lector no sabe si falta el dato o falta el analisis.
        _rp = cfg["dir"] / "phase0_report.json"
        if _rp.exists():
            _co = json.loads(_rp.read_text()).get("coaches") or {}
            _ok = {c["coach"] for c in _co.get("coverage", [])
                   if c.get("suficiente")}
            if _ok:
                dts = dts.filter(pl.col("coach").is_in(list(_ok)))
        lista = dts["coach"].to_list()
        if len(lista) < 2:
            print(f"[salto] {nombre}: menos de dos etapas con muestra",
                  file=sys.stderr)
            continue

        club = {"entrenadores": lista,
                "posesiones": dict(zip(lista, dts["n"].to_list())),
                # `dir` y `team` viajan a los datos porque el JavaScript los
                # necesita para componer el comando de ayuda que se muestra
                # cuando falta un artefacto. Antes los deducia de un ternario
                # con dos clubes escritos a mano.
                "dir": str(cfg["dir"].relative_to(RAIZ)),
                "team": equipo,
                "pares": {}, "huella": {}, "jugadores": {}, "cadena": {}}

        tope_club = tope_estados(sub)

        # --- cadena para el tablero interactivo -------------------------
        # Ademas de la del entrenador, la del CLUB SIN EL: `12_API_STATSBOMB.md`
        # §6 advierte que la base del club contiene al propio foco (Jardine es
        # el 53% de las transiciones del America), asi que compararlo contra
        # "el club" es compararlo consigo mismo a medias. La base honesta es
        # `other_coaches`, el resto de eras.
        for a in lista:
            try:
                c_ = cadena_empirica(sub, a, tope=tope_club)
                if c_:
                    resto = sub.filter(pl.col("coach").is_not_null()
                                       & (pl.col("coach") != a))
                    if resto.height:
                        r_ = cadena_empirica(
                            resto.with_columns(pl.lit("__resto__").alias("coach")),
                            "__resto__", tope=tope_club)
                        if r_:
                            c_["resto"] = {"zmat": r_["zmat"], "zvis": r_["zvis"],
                                           "n_pos": r_["n_pos"],
                                           "lift": r_.get("lift", {})}
                    club["cadena"][a] = c_
            except Exception as e:                      # noqa: BLE001
                # Si falta una columna el simulador se salta, pero el resto
                # del reporte NO se cae: es la regla de que una sección sin
                # datos muestra el comando, no un error.
                print(f"[salto] cadena de {a}: {e}", file=sys.stderr)

        # --- huella por entrenador -----------------------------------
        for a in lista:
            # Igualdad EXACTA contra el slug, no subcadena de la ultima
            # palabra. La version anterior hacia `ap = a.split()[-1].lower()`
            # y `if ap in c.stem.lower()`: para "Diego Cocca I" eso da
            # ap = "i", y "i" esta dentro de casi cualquier nombre de
            # archivo. Cocca I se quedaba con la huella del primer parquet
            # que devolviera el glob, sin error ni aviso.
            ap = a.replace(" ", "").lower()
            for c in REPORTS.glob("huella_*.parquet"):
                if c.stem.lower() in (f"huella_{cfg['slug']}_{ap}",):
                    t = pl.read_parquet(c)
                    top = (t.filter(pl.col("significativo") & (pl.col("z") >= 3)
                                    & (pl.col("n") >= 50))
                           .sort("TV_exceso", descending=True).head(10))
                    club["huella"][a] = [
                        {"estado": r["estado"], "n": int(r["n"]),
                         "tv": round(float(r["TV"]), 4),
                         "ruido": round(float(r["TV_ruido"]), 4),
                         "exceso": round(float(r["TV_exceso"]), 4)}
                        for r in top.iter_rows(named=True)]
                    break

        # --- pares: IC + plantel -------------------------------------
        for c in sorted(REPORTS.glob("ic_*.json")):
            d = json.loads(c.read_text())
            a, b = d.get("a"), d.get("b")
            if a not in lista or b not in lista:
                continue
            if not _es_del_club(d, equipo, c.name):
                continue
            r0 = d["resultados"][0]
            club["pares"][f"{a}|{b}"] = {
                "et": r0["E_T"], "gol": r0["P_gol"], "rem": r0["P_remate"],
                "n_a": d.get("n_poss_a"), "n_b": d.get("n_poss_b")}

        for c in sorted(REPORTS.glob("plantel_*.json")):
            if c.stem.startswith("plantel_f"):
                continue
            d = json.loads(c.read_text())
            a, b = d.get("a"), d.get("b")
            k = f"{a}|{b}"
            if k not in club["pares"]:
                continue
            if not _es_del_club(d, equipo, c.name):
                continue
            todos = d["nivel3_intra_jugador"]
            camb = [j for j in todos if j.get("cambio")]
            # TODOS los futbolistas, no solo los que cruzan el umbral: con 0 de
            # 12 la lista quedaba vacia y la seccion no pintaba nada. El cero es
            # el resultado, pero el lector merece poder mirarlo.
            # Orden por `tv_exceso`, NO por G2 ni z: esos escalan con el tamaño
            # de muestra y ordenarian por minutos jugados (ADR-25, ADR-28).
            orden = sorted(todos, key=lambda j: -j.get("tv_exceso", 0))
            club["pares"][k]["plantel"] = {
                "compartidos": d["nivel1_solapamiento"]["compartidos"],
                "jugadores_a": d["nivel1_solapamiento"]["jugadores_en_a"],
                "pct": d["nivel1_solapamiento"]["pct_acciones_de_a_por_compartidos"],
                "cambian": len(camb), "total": len(todos),
                "lista": [{"id": j["player_id"], "nombre": j["player"],
                           "exceso": j.get("tv_exceso", 0),
                           "cambio": bool(j.get("cambio"))} for j in orden]}
            # mapas: para los que cambiaron y, si no cambio ninguno, para los
            # ocho primeros del orden, que es lo que se puede abrir.
            for j in (camb if camb else orden[:8]):
                jid = str(j["player_id"])
                if jid in club["jugadores"]:
                    continue
                ps = trans.filter(pl.col("player_id") == j["player_id"])
                club["jugadores"][jid] = {
                    "nombre": j["player"],
                    "mapas": {co: mapa_zonas(ps.filter(pl.col("coach") == co))
                              for co in lista}}

        # --- referencia de los rivales, UNA para toda la ventana ---------
        # No se calcula por era: los rivales de un tecnico y los de otro son
        # conjuntos distintos, y la referencia se moveria por sesgo de
        # calendario en vez de por estilo.
        try:
            riv = sub.filter(pl.col("coach").is_null())
            if riv.height:
                largos = riv.group_by("poss_uid").len()["len"]
                fin_r = (riv.filter(pl.col("is_absorbing"))
                            .group_by("poss_uid")
                            .agg(pl.col("to_state").last().alias("f")))
                # el estado de REMATE se toma del etiquetado del club: los
                # indices son globales al artefacto, no por entrenador
                est_rem = None
                for cc in club["cadena"].values():
                    for k, v in (cc.get("fin") or {}).items():
                        if v == "REMATE":
                            est_rem = int(k)
                    if est_rem is not None:
                        break
                rem = (fin_r.filter(pl.col("f") == est_rem).height / fin_r.height
                       if est_rem is not None and fin_r.height else None)
                club["ref_rivales"] = {
                    "et": float(largos.mean()),
                    "rem": rem,
                    "np": int(largos.len()),
                    "equipos": int(riv["team"].n_unique())
                    if "team" in riv.columns else None}
                print(f"[ref] {nombre}: rivales {largos.len():,} posesiones, "
                      f"{largos.mean():.2f} acciones"
                      + (f", {100*rem:.1f} remates por 100" if rem else ""),
                      file=sys.stderr)
        except Exception as e:                           # noqa: BLE001
            print(f"[salto] referencia de rivales: {e}", file=sys.stderr)

        club["defensa"] = defensa(lista, equipo)
        # --- goal_open (opcional; si no está, la tarjeta no se pinta) ---
        club["goal_open"] = {}
        for f in REPORTS.glob("goal_open_*.json"):
            try:
                club["goal_open"][f.stem] = json.loads(f.read_text())
            except Exception:                            # noqa: BLE001
                pass
        fdr = REPORTS / "fdr_goal_open.json"
        if fdr.exists():
            try:
                club["fdr_goal_open"] = json.loads(fdr.read_text())
            except Exception:                            # noqa: BLE001
                pass

        datos["clubes"][nombre] = club
        print(f"[ok] {nombre}: {len(lista)} entrenadores, "
              f"{len(club['pares'])} pares, {len(club['jugadores'])} jugadores",
              file=sys.stderr)
    if _SIN_CLUB:
        print(f"\n[AVISO h2_11] {len(_SIN_CLUB)} JSON descartados por no "
              "declarar `club` (clave compuesta). Rellenalos con:\n"
              "    python scripts/31_backfill_club.py            # ver\n"
              "    python scripts/31_backfill_club.py --escribir # aplicar",
              file=sys.stderr)
        for f in sorted(_SIN_CLUB)[:12]:
            print(f"    {f}", file=sys.stderr)
        if len(_SIN_CLUB) > 12:
            print(f"    ... y {len(_SIN_CLUB) - 12} mas", file=sys.stderr)
    return datos


# ==========================================================================
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
/* En movil no hay `mouseover`: sin esto, todo lo que explica una casilla es
   inalcanzable en el telefono. */
#tip.fijo{pointer-events:auto}
.celda,.pt,[data-tip]{-webkit-tap-highlight-color:transparent}
</style></head><body>
<div id="aura"></div>
<div id="tip"></div>

<header class="wrap">
  <div class="kicker"><span class="dot"></span><span id="kick">Liga MX</span></div>
  <h1>La historia<br>de un <em>entrenador</em></h1>
  <p>Sin ver un solo partido: qué hace distinto cada técnico y dónde lo hace.</p>
</header>

<nav><div class="navin">
  <div class="seg" id="segClub"><div class="pill"></div></div>
  <span class="navlab">técnico</span>
  <select id="selDT" aria-label="Técnico analizado"></select>
  <button class="swap" id="swap" title="Intercambiar los dos técnicos"
   aria-label="Intercambiar los dos técnicos">&#8646;</button>
  <span class="navlab">frente a</span>
  <select id="selRival" aria-label="Técnico de comparación"></select>
  <button class="ayuda" id="btnGuia" style="margin-left:auto">¿Cómo se lee?</button>
</div></nav>

<div class="wrap">
  <details class="guia" id="guia" open><summary>Empieza por aquí: qué estás mirando</summary>

  <div class="paso"><div class="num">1</div><div>
   <h4>Una <span class="term" data-tip="<b>Posesión</b>La cadena de pases y conducciones que un equipo encadena desde que recibe el balón hasta que lo pierde, lo manda fuera o remata.">posesión</span> es la unidad de todo esto</h4>
   <p>Cada vez que un equipo se hace con el balón empieza una cadena de pases y
   conducciones que acaba en pérdida, en balón fuera o en remate. Ese trozo de
   juego es una posesión. Todo el reporte cuenta cosas sobre esas cadenas: cuánto
   duran, por dónde pasan y cómo acaban. Hay decenas de miles detrás de cada
   número, no un puñado de jugadas escogidas.</p></div></div>

  <div class="paso"><div class="num">2</div><div>
   <h4>El campo va siempre en la misma dirección</h4>
   <p>En todos los mapas, el equipo que analizamos ataca hacia la <b>derecha</b>:
   su portería queda a la izquierda y la del rival a la derecha. El campo está
   partido en veinte casillas. «Tercio propio» es la zona de su portería,
   «tercio rival» la de enfrente. Cuanto más encendida está una casilla, más
   pasa ahí lo que esa figura esté midiendo.</p></div></div>

  <div class="paso"><div class="num">3</div><div>
   <h4>Dos colores, siempre los mismos</h4>
   <p>El <b>color del club</b> es siempre el técnico que estás analizando; la
   <b>plata</b> es el técnico con el que lo comparas. En los mapas de diferencia
   el color del club marca dónde hace <em>más</em> y el coral dónde hace
   <em>menos</em>. No cambia de una sección a otra.</p></div></div>

  <div class="paso"><div class="num">4</div><div>
   <h4>Cuando decimos «no lo distinguimos del azar»</h4>
   <p>Dos técnicos nunca dan exactamente el mismo número, aunque jueguen igual:
   los partidos varían. Antes de llamar «diferencia» a algo, comprobamos que sea
   mayor que ese vaivén normal. Si no lo es, decimos que no lo distinguimos del
   azar — que <em>no</em> es lo mismo que decir que son iguales. Significa que,
   si hay diferencia, es más pequeña de lo que estos partidos permiten ver.</p></div></div>

  <div class="paso"><div class="num">5</div><div>
   <h4>Toca o pasa el cursor por cualquier casilla</h4>
   <p>Todas las casillas, barras y puntos llevan su cifra exacta detrás. En el
   ordenador, pasando el cursor; en el teléfono, tocándolos. Y arriba puedes
   cambiar de club y de pareja de técnicos: el reporte entero se recalcula.</p></div></div>
  </details>

  <section id="s0" class="rev"></section>
  <section id="s1" class="rev"></section>
  <section id="s2" class="rev"></section>
  <section id="s3" class="rev"></section>
  <section id="s4" class="rev"></section>
  <details>
  <summary>Que no puede decir este analisis</summary>
  <p><b>No dice quien es mejor.</b> Describe estilo, no resultados.</p>
  <p><b>No mide la calidad de ejecucion.</b> Un pase perfecto y uno mediocre
  hacia la misma zona cuentan igual.</p>
  <p><b>No prueba causalidad.</b> Aunque el jugador sea el mismo, sus companeros
  y sus rivales cambian.</p>
  <p><b>No ve lo que pasa sin balon.</b> Presion, lineas y altura del bloque
  quedan fuera del modelo.</p>
  <p><b>Las fechas son reconstruidas</b>, no oficiales.</p>
  </details>
</div>

<script>
const DATOS = __DATOS__;
const TEMA={
 "Club América":{a1:"#ffd21e",a2:"#fff08a",aura:"rgba(255,210,30,.075)",
  aura2:"rgba(10,40,110,.14)"},
 "Cruz Azul":{a1:"#2d6cff",a2:"#8ab6ff",aura:"rgba(45,108,255,.10)",
  aura2:"rgba(255,255,255,.045)"}};
const FASE={open:"juego abierto",transition:"transición",restart:"reinicio",
 set_piece:"balón parado"};
const CORTA={open:"abierto",transition:"transición",restart:"reinicio",
 set_piece:"b. parado"};
/* La leyenda muestra la etiqueta TAL COMO aparece en el mapa, luego el nombre
   completo. Antes el mapa decia "abierto" y la leyenda "Juego abierto", y no
   habia forma de saber que eran lo mismo. */
const EXPLICA=[
 ["abierto","Juego abierto",
  "La jugada nace del juego corriente, sin que el balón se haya detenido."],
 ["transición","Transición",
  "Empieza justo tras robar el balón o tras un saque del portero: ataque rápido."],
 ["reinicio","Reinicio","Arranca con un saque de banda o un saque de meta."],
 ["b. parado","Balón parado","Arranca en un córner o un tiro libre."]];
const TERCIO=["propio","propio","medio","rival","rival"];
/* StatsBomb: origen arriba-izquierda, `y` CRECE HACIA ABAJO. Un equipo que
   ataca hacia x=120 tiene el borde y=0 a su IZQUIERDA. La primera version
   tenia este vector al reves y TODOS los mapas salian espejeados.
   Verificado con Alejandro Zendejas (extremo derecho): 43.6% de sus acciones
   caen en iy=3, que por tanto es la banda DERECHA. */
const FRANJA=["banda izquierda","centro-izquierda","centro-derecha","banda derecha"];
const NX=5,NY=4,L=120,A=80,cw=L/NX,ch=A/NY;
/* Ancho UNICO para toda cancha que se compare con otra. Antes cada funcion
   traia el suyo (400, 420, 480, 600) y, combinado con la rejilla `.duo`, dos
   mapas del mismo par salian de tamanos distintos: la mancha mas grande
   parecia mas intensa sin serlo. */
const W_MAPA=470;
/* Color del par de comparacion, en un solo sitio. FOCO = color del club,
   RIVAL = plata neutra. La seccion de jugadores ya lo hacia asi; la seccion
   defensiva pintaba los dos tecnicos del mismo amarillo y luego la diferencia
   en azul/rojo, que sobre el America chocaba con su propio color. */
const C_FOCO="var(--a1)", C_RIV="var(--riv)", C_NEG="var(--neg)";
const $=i=>document.getElementById(i);
const ape=n=>n.split(" ").pop();
const parse=e=>{const[z,f]=e.split("|");return[+z[1],+z[2],f];};
const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
 .replace(/"/g,"&quot;");
/* Las tres metricas del reporte, en un solo lugar: nombre, como se formatea y
   como se convierte desde el dato crudo. Antes estaban repetidas en cuatro
   funciones y una se quedo sin actualizar. */
const METRICAS=[
 {k:"et", tit:"Acciones por posesión", corto:"acciones",
  esc:v=>v, fmt:v=>v.toFixed(1), dec:1,
  ayuda:"Cuántos pases, conducciones y remates encadena el equipo antes de "+
   "perder el balón. Más alto = posesiones más largas."},
 {k:"rem",tit:"Remates por 100 posesiones", corto:"remates",
  esc:v=>v*100, fmt:v=>v.toFixed(1), dec:1,
  ayuda:"De cada 100 posesiones, cuántas terminan en un remate."},
 {k:"gol",tit:"Goles por 100 posesiones", corto:"goles",
  esc:v=>v*100, fmt:v=>v.toFixed(2), dec:2,
  ayuda:"De cada 100 posesiones, cuántas terminan en gol. Ninguna diferencia "+
   "de gol resultó mayor que el azar en estos datos."}];

/* ================= simulación de posesiones =================
   La cadena viene del parquet, en formato disperso. `filas[i]` es una lista de
   pares [destino, probabilidad] que suma 1. Simular es muestrear un destino y
   repetir hasta caer en un estado absorbente. */
function sortea(pares){
 let u=Math.random(), a=0;
 for(const [j,p] of pares){a+=p; if(u<=a) return j;}
 return pares[pares.length-1][0];
}
/* `C.abs` y `C.zonas` vienen RESUELTOS desde Python contra los datos reales.
   La version anterior los adivinaba con /^z\d/ y, si el formato no coincidia,
   marcaba TODO como absorbente: el marcador salia en 0.00 y la cancha vacia,
   sin lanzar ningun error. */
function simulaUna(C){
 const ruta=[]; let i=sortea(C.inicial), k=0;
 while(k++<200){
  ruta.push(i);
  if(C.abs[i]) break;
  const f=C.filas[i]; if(!f||!f.length) break;
  i=sortea(f);
 }
 const ult=ruta[ruta.length-1];
 const et=C.abs[ult] ? (C.fin[String(C.estados[ult])]||"FIN") : "PERDIDA";
 return {ruta, fin: et,
         gol: /GOL/.test(et),
         remate: /(GOL|REMATE)/.test(et),
         largo: ruta.length-1};
}
/* Nombre humano de una zona: es lo que convierte "z13" en algo que entiende
   alguien que no ve futbol. TERCIO y FRANJA ya existen en el reporte. */
function nombraZona(z,nx,ny){
 if(!z) return "";
 const t=TERCIO[Math.min(z[0],TERCIO.length-1)]||"";
 const f=FRANJA[Math.min(z[1],FRANJA.length-1)]||"";
 return `${f}, ${t}`;
}

/* ================= leyendas ================= */
/* Toda figura de este reporte lleva ahora su leyenda pegada debajo. El criterio
   es simple: si para entender un color hay que subir a leer un parrafo, la
   figura no se explica sola. */
const SW=(c,t)=>`<span class="leg"><i style="background:${c}"></i>${t}</span>`;
const leyenda=(...xs)=>`<div class="leyenda">${xs.filter(Boolean).join("")}</div>`;
/* `background` plano primero: si el navegador no entiende `color-mix` (Firefox
   <113, Safari <16.2) la segunda declaracion se descarta y la barra se ve
   solida en vez de vacia. El reporte tiene que abrirse en cualquier maquina de
   un jurado, no solo en la del autor. */
const rampa=(c,lo,hi)=>`<span class="rampa">${lo}<u style="background:${c};
 background:linear-gradient(90deg,color-mix(in srgb,${c} 12%,transparent),${c})"></u>${hi}</span>`;
/* Cabecera de una cancha: nombre del tecnico con su cuadrito de color, para no
   tener que adivinar cual mapa es de quien. */
const cap=(col,nom,sub)=>`<div class="mapcap"><i style="background:${col}"></i>
 ${esc(nom)}${sub?`<s>${esc(sub)}</s>`:""}</div>`;

/* ================= tooltip ================= */
const tip=$("tip");
document.addEventListener("mouseover",e=>{
 const t=e.target.closest("[data-tip]");
 if(!t)return;tip.innerHTML=t.dataset.tip;tip.classList.add("on");});
document.addEventListener("mouseout",e=>{
 if(e.target.closest("[data-tip]"))tip.classList.remove("on");});
document.addEventListener("mousemove",e=>{
 if(tip.classList.contains("fijo"))return;
 tip.style.left=e.clientX+"px";tip.style.top=e.clientY+"px";});
/* Tactil: un toque fija el globo, otro lo quita. Sin esto el reporte pierde en
   el telefono toda la lectura por casilla, que es donde vive el detalle. */
document.addEventListener("click",e=>{
 const t=e.target.closest("[data-tip]");
 if(!t){tip.classList.remove("on","fijo");return;}
 tip.innerHTML=t.dataset.tip;tip.classList.add("on","fijo");
 const r=t.getBoundingClientRect();
 tip.style.left=(r.left+r.width/2)+"px";
 tip.style.top=(r.top+r.height/2)+"px";});

/* ================= numeros que suben ================= */
/* Apple Health anima el numero, no solo la barra: el ojo sigue el cambio y se
   entiende que el valor pertenece a la seleccion actual, no a la anterior. */
function sube(el,to,dec){
 const t0=performance.now(),dur=780;
 const paso=t=>{const p=Math.min((t-t0)/dur,1),e=1-Math.pow(1-p,3);
  el.textContent=(to*e).toFixed(dec);
  if(p<1)requestAnimationFrame(paso);};
 requestAnimationFrame(paso);
}
function animaTodo(){
 document.querySelectorAll("[data-num]").forEach(el=>
  sube(el,+el.dataset.num,+el.dataset.dec));
 document.querySelectorAll(".it-bar i").forEach(b=>{
  b.style.width="0";requestAnimationFrame(()=>{b.style.width=b.dataset.w+"%";});});
}

/* ================= perfil absoluto de cada tecnico ================= */
/* Los IC vienen por PAREJA, pero el valor absoluto de un tecnico es el mismo en
   todas las parejas donde aparece. Se recoge una vez y sirve para el rango del
   club (los anillos) y para la nube de puntos. */
function perfiles(c){
 const abs={};
 Object.entries(c.pares).forEach(([k,v])=>{
  const[a,b]=k.split("|");
  if(!abs[a])abs[a]={n:a,et:v.et.a,rem:v.rem.a,gol:v.gol.a,np:v.n_a};
  if(!abs[b])abs[b]={n:b,et:v.et.b,rem:v.rem.b,gol:v.gol.b,np:v.n_b};});
 return Object.values(abs);
}

/* ================= anillo de rango ================= */
/* No es un anillo de "meta cumplida": el arco marca DONDE CAE el tecnico dentro
   del rango que abarcan todos los tecnicos del club, y la muesca blanca es el
   rival. Asi el numero grande tiene una escala con la que compararse. */
function anillo(m,val,riv,lo,hi,dt,rv){
 const R=54,C=2*Math.PI*R,ini=-.4,fin=.4; /* arco de 288 grados */
 const t=(hi-lo)>1e-9?(val-lo)/(hi-lo):.5;
 const tr=Math.max(0,Math.min(1,(hi-lo)>1e-9?(riv-lo)/(hi-lo):.5));
 const arco=v=>{const ang=(ini+(fin-ini)*Math.max(0,Math.min(1,v)))*2*Math.PI;
  return[70+R*Math.sin(ang),70-R*Math.cos(ang)];};
 const largo=C*(fin-ini),len=largo*Math.max(0,Math.min(1,t));
 const[rx,ry]=arco(tr);
 const may=(fin-ini)>.5?1:0;
 const[ax,ay]=arco(0),[bx,by]=arco(1);
 const tt=`<b>${esc(m.tit)}</b>${esc(m.ayuda)}`;
 return `<div class="anillo" data-tip="${tt}">
 <svg viewBox="0 0 140 142">
  <path d="M${ax.toFixed(1)} ${ay.toFixed(1)} A${R} ${R} 0 ${may} 1 ${bx.toFixed(1)} ${by.toFixed(1)}"
   fill="none" stroke="rgba(255,255,255,.075)" stroke-width="13"
   stroke-linecap="round"/>
  <path d="M${ax.toFixed(1)} ${ay.toFixed(1)} A${R} ${R} 0 ${may} 1 ${bx.toFixed(1)} ${by.toFixed(1)}"
   fill="none" stroke="url(#gr${m.k})" stroke-width="13" stroke-linecap="round"
   stroke-dasharray="${len.toFixed(1)} ${(C*2).toFixed(0)}">
   <animate attributeName="stroke-dasharray" from="0 ${(C*2).toFixed(0)}"
    to="${len.toFixed(1)} ${(C*2).toFixed(0)}" dur=".95s" fill="freeze"
    calcMode="spline" keySplines="0.16 1 0.3 1" keyTimes="0;1"/></path>
  <defs><linearGradient id="gr${m.k}" x1="0" y1="1" x2="1" y2="0">
   <stop offset="0%" stop-color="var(--a1)"/>
   <stop offset="100%" stop-color="var(--a2)"/></linearGradient></defs>
  <circle cx="${rx.toFixed(1)}" cy="${ry.toFixed(1)}" r="5.4" fill="var(--bg)"
   stroke="#fff" stroke-width="2.2" opacity=".8"/>
  <text x="70" y="72" text-anchor="middle" class="a-num" fill="var(--tx)"
   font-size="27" data-num="${val.toFixed(4)}" data-dec="${m.dec}">0</text>
  <text x="70" y="93" text-anchor="middle" fill="var(--tx2)" font-size="11"
   font-family="var(--mono)" letter-spacing="1">${esc(ape(dt)).toUpperCase()}</text>
  <text x="70" y="138" text-anchor="middle" fill="var(--tx2)" font-size="11"
   font-family="var(--mono)" letter-spacing=".5">&#9679; ${esc(ape(rv))} ${m.fmt(riv)}</text>
 </svg>
 <div class="a-tit">${esc(m.tit)}</div>
 <div class="a-sub">rango del club ${m.fmt(lo)} &ndash; ${m.fmt(hi)}</div>
</div>`;
}

/* ================= grafica de intervalos (forest plot) ================= */
/* Es el objeto central del proyecto y hasta ahora solo se veia una etiqueta de
   texto. Aqui se ve el intervalo completo y la linea del cero: si la barra la
   toca, la diferencia no sobrevive al azar. */
function intervalos(par,dt,rv){
 const W=840,fh=74,H=fh*METRICAS.length+56,x0=196,x1=W-58;
 const todos=METRICAS.flatMap(m=>[par[m.k].lo_pct,par[m.k].hi_pct,0]);
 let lo=Math.min(...todos),hi=Math.max(...todos);
 const marg=(hi-lo)*.12||1;lo-=marg;hi+=marg;
 const X=v=>x0+(v-lo)/(hi-lo)*(x1-x0);
 const z=X(0);
 let g=`<svg viewBox="0 0 ${W} ${H}">
  <line x1="${z.toFixed(1)}" y1="26" x2="${z.toFixed(1)}" y2="${H-34}"
   stroke="#fff" stroke-opacity=".22" stroke-width="1.4" stroke-dasharray="4 4"/>
  <text x="${z.toFixed(1)}" y="18" text-anchor="middle" fill="var(--tx3)"
   font-size="10" font-family="var(--mono)" letter-spacing="1">SIN DIFERENCIA</text>`;
 METRICAS.forEach((m,i)=>{
  const d=par[m.k],y=46+i*fh,sig=d.excluye_cero;
  const col=sig?(d.diff_pct>0?"var(--ok)":"var(--ro)"):"var(--tx3)";
  const xa=X(d.lo_pct),xb=X(d.hi_pct),xc=X(d.diff_pct);
  const veredicto=sig
   ?`El intervalo no toca el cero: la diferencia sobrevive al azar.`
   :`El intervalo cruza el cero: no distinguimos esta diferencia del azar.`;
  const tt=`<b>${esc(m.tit)}</b>${esc(ape(dt))} ${m.fmt(m.esc(d.a))} frente a `+
   `${esc(ape(rv))} ${m.fmt(m.esc(d.b))}.<br>Diferencia `+
   `${d.diff_pct>0?"+":""}${d.diff_pct.toFixed(1)}% `+
   `(entre ${d.lo_pct.toFixed(1)}% y ${d.hi_pct.toFixed(1)}%).<br>${veredicto}`;
  g+=`<g data-tip="${tt}">
   <rect x="0" y="${y-22}" width="${W}" height="${fh-10}" fill="transparent"/>
   <text x="0" y="${y-2}" fill="var(--tx)" font-size="12.5" font-weight="600"
    font-family="var(--sans)">${esc(m.tit)}</text>
   <text x="0" y="${y+15}" fill="var(--tx3)" font-size="11"
    font-family="var(--mono)">${m.fmt(m.esc(d.a))} vs ${m.fmt(m.esc(d.b))}</text>
   <line x1="${xa.toFixed(1)}" y1="${y}" x2="${xb.toFixed(1)}" y2="${y}"
    stroke="${col}" stroke-width="7" stroke-linecap="round" opacity=".34"/>
   <line x1="${xa.toFixed(1)}" y1="${y-8}" x2="${xa.toFixed(1)}" y2="${y+8}"
    stroke="${col}" stroke-width="2" opacity=".7"/>
   <line x1="${xb.toFixed(1)}" y1="${y-8}" x2="${xb.toFixed(1)}" y2="${y+8}"
    stroke="${col}" stroke-width="2" opacity=".7"/>
   <circle cx="${xc.toFixed(1)}" cy="${y}" r="0" fill="${col}">
    <animate attributeName="r" from="0" to="7" dur=".55s"
     begin="${(i*.11).toFixed(2)}s" fill="freeze" calcMode="spline"
     keySplines="0.16 1 0.3 1" keyTimes="0;1"/></circle>
   <text x="${xb+14}" y="${y+4.5}" fill="${col}" font-size="12.5"
    font-weight="700" font-family="var(--mono)">${d.diff_pct>0?"+":""}${d.diff_pct.toFixed(0)}%</text>
  </g>`;});
 g+=`<text x="${x0}" y="${H-12}" fill="var(--tx3)" font-size="10"
   font-family="var(--mono)">${lo.toFixed(0)}%</text>
  <text x="${x1}" y="${H-12}" text-anchor="end" fill="var(--tx3)" font-size="10"
   font-family="var(--mono)">+${hi.toFixed(0)}%</text>
  <text x="${(x0+x1)/2}" y="${H-12}" text-anchor="middle" fill="var(--tx3)"
   font-size="10" font-family="var(--mono)" letter-spacing="1">DIFERENCIA DE ${esc(ape(dt)).toUpperCase()} FRENTE A ${esc(ape(rv)).toUpperCase()}</text>`;
 return g+`</svg>`;
}

/* ================= cancha ================= */
function pitch(inner,w=W_MAPA){
 const h=w*A/L,s=w/L;
 const ln='stroke="var(--linea)" stroke-width="1.2" fill="none" opacity=".9"';
 let g=`<svg viewBox="0 0 ${w} ${h+34}">
  <defs><linearGradient id="cs" x1="0" y1="0" x2="0" y2="1">
   <stop offset="0%" stop-color="#173f29"/><stop offset="100%" stop-color="#0d2317"/>
  </linearGradient>
  <!-- Halo SUAVE alrededor de la celda, no desenfoque del relleno. El modelo
       estima una probabilidad CONSTANTE por zona: difuminar los bordes
       sugeriria una resolucion espacial continua que no existe. -->
  <filter id="halo" x="-30%" y="-30%" width="160%" height="160%">
   <feGaussianBlur in="SourceAlpha" stdDeviation="5" result="b"/>
   <feFlood class="halo-flood"/>
   <feComposite in2="b" operator="in" result="h"/>
   <feMerge><feMergeNode in="h"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter></defs>
  <rect width="${w}" height="${h}" rx="14" fill="url(#cs)"/>`;
 for(let k=0;k<10;k+=2)g+=`<rect x="${k*w/10}" width="${w/10}" height="${h}"
  fill="#fff" opacity=".018"/>`;
 g+=`<rect x="${2*s}" y="${2*s}" width="${w-4*s}" height="${h-4*s}" rx="4" ${ln}/>
  <line x1="${w/2}" y1="${2*s}" x2="${w/2}" y2="${h-2*s}" ${ln}/>
  <circle cx="${w/2}" cy="${h/2}" r="${9.15*s}" ${ln}/>
  <rect x="${2*s}" y="${(A/2-20.15)*s}" width="${14.5*s}" height="${40.3*s}" ${ln}/>
  <rect x="${w-16.5*s}" y="${(A/2-20.15)*s}" width="${14.5*s}" height="${40.3*s}" ${ln}/>`;
 g+=inner(s,w,h);
 /* La direccion de ataque es el dato que mas veces hay que repetir a quien no
    ve futbol: sin ella, "tercio rival" no significa nada. Va mas grande y con
    la porteria nombrada en los dos extremos. */
 g+=`<line x1="${w*.44}" y1="${h+15}" x2="${w*.56}" y2="${h+15}"
   stroke="var(--tx2)" stroke-width="1.3"/>
  <path d="M${w*.56} ${h+15} l-5.5 -3.6 v7.2 z" fill="var(--tx2)"/>
  <text x="4" y="${h+19}" fill="var(--tx3)" font-size="11"
   font-family="var(--sans)">portería propia</text>
  <text x="${w-4}" y="${h+19}" fill="var(--tx3)" font-size="11"
   text-anchor="end" font-family="var(--sans)">portería rival</text>
  <text x="${w/2}" y="${h+29}" fill="var(--tx2)" font-size="10.5"
   text-anchor="middle" font-family="var(--mono)" letter-spacing="1.5">ATAQUE</text>`;
 return g+`</svg>`;
}
/* rejilla visible: al .06 sobre el cesped era invisible */
function rejilla(s){
 let g="";
 for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++)
  g+=`<rect x="${ix*cw*s+1.5}" y="${iy*ch*s+1.5}" width="${cw*s-3}"
   height="${ch*s-3}" rx="7" fill="none" stroke="#fff" stroke-width="1"
   opacity=".17" stroke-dasharray="4 4"/>`;
 return g;
}
function huellaSVG(top){
 return pitch((s,w,h)=>{
  let g=rejilla(s);
  if(!top.length)return g;
  const vm=Math.max(...top.map(d=>d.exceso)),agr={};
  top.forEach(d=>{const[ix,iy,f]=parse(d.estado),k=ix+","+iy;
   if(!agr[k])agr[k]={v:0,f:new Set(),ix,iy,est:[]};
   agr[k].v=Math.max(agr[k].v,d.exceso);agr[k].f.add(f);agr[k].est.push(d.estado);});
  Object.values(agr).forEach((d,n)=>{
   const v=d.v/vm,x=d.ix*cw*s,y=d.iy*ch*s;
   const fsn=[...d.f].map(f=>FASE[f]).join(", ");
   const tt=`<b>${esc(FRANJA[d.iy])}, tercio ${esc(TERCIO[d.ix])}</b>`+
    `Se distingue aquí en: ${esc(fsn)}.`;
   g+=`<g filter="url(#halo)" class="celda" data-zona="${d.ix},${d.iy}"
     data-tip="${tt}">
    <rect x="${x+4}" y="${y+4}" width="${cw*s-8}" height="${ch*s-8}" rx="9"
     fill="var(--a1)" stroke="var(--a2)" stroke-width="2" opacity="0">
     <animate attributeName="opacity" from="0" to="${(.3+.55*v).toFixed(2)}"
      dur=".55s" begin="${(n*.07).toFixed(2)}s" fill="freeze"/></rect></g>`;
   const fs=[...d.f].map(f=>CORTA[f]).sort();
   fs.forEach((t,i)=>{g+=`<text x="${x+cw*s/2}"
    y="${y+ch*s/2+(i-(fs.length-1)/2)*15+5}" fill="#fff" font-size="12.5"
    font-weight="700" text-anchor="middle" font-family="var(--sans)"
    paint-order="stroke" stroke="rgba(0,0,0,.55)" stroke-width="2.6"
    pointer-events="none" opacity="0">
    ${t}<animate attributeName="opacity" from="0" to="1" dur=".5s"
    begin="${(n*.07+.2).toFixed(2)}s" fill="freeze"/></text>`;});});
  return g;});
}
/* `vmax` OBLIGATORIO cuando el mapa se compara con otro: es el maximo comun de
   los dos. Con cada mapa normalizado a su propio maximo, dos repartos muy
   distintos se pintan con la misma intensidad y la comparacion visual miente.
   `mapaNivel` ya lo hacia; los mapas de jugador no, y son los que van pegados. */
function mapaSVG(m,c,tag,vmax){
 return pitch((s,w,h)=>{
  const vm=vmax||Math.max(...m.flat(),1e-9);let g="";
  for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++){
   const v=Math.min(1,m[ix][iy]/vm),x=ix*cw*s,y=iy*ch*s;
   const tt=`<b>${esc(FRANJA[iy])}, tercio ${esc(TERCIO[ix])}</b>`+
    `${(m[ix][iy]*100).toFixed(1)}% de sus intervenciones ${esc(tag||"")}`;
   /* borde SIEMPRE presente: con relleno tenue las celdas se perdian
      en el cesped y no se sabia donde acababa cada zona */
   g+=`<g class="celda" data-tip="${tt}">
    <rect x="${x+2.5}" y="${y+2.5}" width="${cw*s-5}" height="${ch*s-5}" rx="8"
     fill="${c}" fill-opacity="${(.10+.75*v).toFixed(2)}"
     stroke="#fff" stroke-opacity="${(.14+.32*v).toFixed(2)}"
     stroke-width="1.2"/></g>`;
   /* el numero baja de .14 a .06: antes media cancha salia muda y no habia
      forma de leer una zona floja sin pasar el raton por encima */
   if(v>.06)g+=`<text x="${x+cw*s/2}" y="${y+ch*s/2+4.5}" fill="#fff"
    font-size="12.5" font-weight="700" text-anchor="middle" pointer-events="none"
    font-family="var(--mono)" paint-order="stroke" stroke="rgba(0,0,0,.5)"
    stroke-width="2.6">${(m[ix][iy]*100).toFixed(0)}%</text>`;
  }
  return g;});
}
/* Mapa de DIFERENCIA: dos mapas lado a lado obligan a comparar de memoria.
   Este pinta directamente donde el jugador gano presencia y donde la perdio. */
function mapaDelta(ma,mb,dt,rv){
 return pitch((s,w,h)=>{
  let vm=1e-9;
  for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++)
   vm=Math.max(vm,Math.abs(ma[ix][iy]-mb[ix][iy]));
  let g="";
  for(let ix=0;ix<NX;ix++)for(let iy=0;iy<NY;iy++){
   const d=ma[ix][iy]-mb[ix][iy],v=Math.abs(d)/vm,x=ix*cw*s,y=iy*ch*s;
   const pp=(d*100);
   const tt=`<b>${esc(FRANJA[iy])}, tercio ${esc(TERCIO[ix])}</b>`+
    `${pp>=0?"+":""}${pp.toFixed(1)} puntos con ${esc(ape(dt))} `+
    `que con ${esc(ape(rv))}.`;
   g+=`<g class="celda" data-tip="${tt}">
    <rect x="${x+2.5}" y="${y+2.5}" width="${cw*s-5}" height="${ch*s-5}" rx="8"
     fill="${d>=0?C_FOCO:C_NEG}" fill-opacity="${(.06+.72*v).toFixed(2)}"
     stroke="#fff" stroke-opacity="${(.12+.26*v).toFixed(2)}" stroke-width="1.2"/></g>`;
   if(v>.12)g+=`<text x="${x+cw*s/2}" y="${y+ch*s/2+4.5}" fill="#fff"
    font-size="12" font-weight="700" text-anchor="middle" pointer-events="none"
    font-family="var(--mono)" paint-order="stroke" stroke="rgba(0,0,0,.5)"
    stroke-width="2.6">${pp>0?"+":""}${pp.toFixed(1)}</text>`;
  }
  return g;});
}

/* ================= barras TV observada vs ruido ================= */
/* ADR-30: ninguna distancia se reporta sin su nula. Antes la nula existia en el
   JSON y no se veia. La barra clara es lo que produciria el azar; solo la parte
   solida cuenta como senal. */
function barrasHuella(top,dt){
 const filas=top.slice(0,8);
 const W=560,fh=46,H=filas.length*fh+34;
 const vm=Math.max(...filas.map(d=>d.tv))*1.12||1;
 const x0=178,x1=W-52;
 const X=v=>x0+v/vm*(x1-x0);
 let g=`<svg viewBox="0 0 ${W} ${H}">`;
 filas.forEach((d,i)=>{
  const[ix,iy,f]=parse(d.estado),y=22+i*fh;
  const tt=`<b>${esc(FRANJA[iy])}, tercio ${esc(TERCIO[ix])} &middot; ${esc(FASE[f])}</b>`+
   `Distancia observada ${d.tv.toFixed(3)}. El azar solo, con esta muestra, `+
   `produciria ${d.ruido.toFixed(3)}. Lo que sobra &mdash; ${d.exceso.toFixed(3)} &mdash; `+
   `es la senal. Basado en ${d.n} transiciones.`;
  g+=`<g class="celda" data-zona="${ix},${iy}" data-tip="${tt}">
   <rect x="0" y="${y-16}" width="${W}" height="${fh-6}" fill="transparent"/>
   <text x="0" y="${y-1}" fill="var(--tx)" font-size="13" font-weight="600"
    font-family="var(--sans)">${esc(FRANJA[iy])}, ${esc(TERCIO[ix])}</text>
   <text x="0" y="${y+14}" fill="var(--tx2)" font-size="11.5"
    font-family="var(--mono)">${esc(CORTA[f])} &middot; n=${d.n}</text>
   <rect x="${x0}" y="${y-8}" width="0" height="15" rx="5"
    fill="var(--a1)" opacity=".2">
    <animate attributeName="width" from="0" to="${(X(d.tv)-x0).toFixed(1)}"
     dur=".8s" begin="${(i*.06).toFixed(2)}s" fill="freeze" calcMode="spline"
     keySplines="0.16 1 0.3 1" keyTimes="0;1"/></rect>
   <rect x="${X(d.ruido).toFixed(1)}" y="${y-8}" width="0" height="15" rx="5"
    fill="var(--a1)">
    <animate attributeName="width" from="0" to="${(X(d.tv)-X(d.ruido)).toFixed(1)}"
     dur=".8s" begin="${(i*.06+.16).toFixed(2)}s" fill="freeze" calcMode="spline"
     keySplines="0.16 1 0.3 1" keyTimes="0;1"/></rect>
   <line x1="${X(d.ruido).toFixed(1)}" y1="${y-12}"
    x2="${X(d.ruido).toFixed(1)}" y2="${y+11}" stroke="#fff" stroke-opacity=".5"
    stroke-width="1.5" stroke-dasharray="3 2"/>
   <text x="${x1+8}" y="${y+4}" fill="var(--tx)" font-size="13"
    font-weight="700" font-family="var(--mono)">${d.exceso.toFixed(2)}</text>
  </g>`;});
 g+=`<text x="${x0}" y="${H-4}" fill="var(--tx2)" font-size="11"
  font-family="var(--mono)" letter-spacing=".6">TENUE = LO QUE DA EL AZAR &middot; SOLIDO = LA SEÑAL QUE SOBRA</text>`;
 return g+`</svg>`;
}

/* ================= nube de puntos ================= */
/* El tamano del punto es el numero de posesiones: un tecnico con muestra chica
   se ve chico, y eso comunica incertidumbre sin escribir un p-valor.
   La grafica solo lleva ejes y puntos; toda la lectura de los cuadrantes vive
   en el cuadro de referencia de abajo, para no saturarla. */
function ejes(pts){
 const xs=pts.map(p=>p.et),ys=pts.map(p=>p.rem*100);
 const x0=Math.min(...xs)*.93,x1=Math.max(...xs)*1.07;
 const y0=Math.min(...ys)*.86,y1=Math.max(...ys)*1.14;
 return {x0,x1,y0,y1,mx:(x0+x1)/2,my:(y0+y1)/2};
}
function cuadrante(pts,dt,rv,ref){
 const W=840,H=470,pl=92,pb=72,pt_=34,pr=34;
 const e=ejes(pts);
 const X=v=>pl+(v-e.x0)/(e.x1-e.x0||1)*(W-pl-pr);
 const Y=v=>H-pb-(v-e.y0)/(e.y1-e.y0||1)*(H-pb-pt_);
 const nm=Math.max(...pts.map(p=>p.np));
 const cx=X(e.mx),cy=Y(e.my);
 let g=`<svg viewBox="0 0 ${W} ${H}">
  <line x1="${cx.toFixed(1)}" y1="${pt_}" x2="${cx.toFixed(1)}" y2="${H-pb}"
   stroke="#fff" opacity=".1" stroke-dasharray="5 5"/>
  <line x1="${pl}" y1="${cy.toFixed(1)}" x2="${W-pr}" y2="${cy.toFixed(1)}"
   stroke="#fff" opacity=".1" stroke-dasharray="5 5"/>
  <line x1="${pl}" y1="${H-pb}" x2="${W-pr}" y2="${H-pb}" stroke="#fff"
   opacity=".16"/>
  <line x1="${pl}" y1="${pt_}" x2="${pl}" y2="${H-pb}" stroke="#fff"
   opacity=".16"/>
  <text x="${pl}" y="${H-pb+18}" text-anchor="middle" fill="var(--tx3)"
   font-size="10.5" font-family="var(--mono)">${e.x0.toFixed(1)}</text>
  <text x="${cx.toFixed(1)}" y="${H-pb+18}" text-anchor="middle" fill="var(--tx2)"
   font-size="10.5" font-family="var(--mono)">${e.mx.toFixed(1)}</text>
  <text x="${W-pr}" y="${H-pb+18}" text-anchor="middle" fill="var(--tx3)"
   font-size="10.5" font-family="var(--mono)">${e.x1.toFixed(1)}</text>
  <text x="${W/2}" y="${H-pb+40}" text-anchor="middle" fill="var(--tx)"
   font-size="12" font-weight="600" font-family="var(--sans)">Acciones por posesión &nbsp;&rarr;&nbsp; retiene más</text>
  <text x="${pl-12}" y="${H-pb+4}" text-anchor="end" fill="var(--tx3)"
   font-size="10.5" font-family="var(--mono)">${e.y0.toFixed(1)}</text>
  <text x="${pl-12}" y="${(cy+4).toFixed(1)}" text-anchor="end" fill="var(--tx2)"
   font-size="10.5" font-family="var(--mono)">${e.my.toFixed(1)}</text>
  <text x="${pl-12}" y="${pt_+4}" text-anchor="end" fill="var(--tx3)"
   font-size="10.5" font-family="var(--mono)">${e.y1.toFixed(1)}</text>
  <text transform="translate(26,${(H-pb+pt_)/2}) rotate(-90)" text-anchor="middle"
   fill="var(--tx)" font-size="12" font-weight="600"
   font-family="var(--sans)">Remates por 100 posesiones &nbsp;&rarr;&nbsp; remata más</text>
  <text x="${cx.toFixed(1)}" y="${pt_-11}" text-anchor="middle" fill="var(--tx2)"
   font-size="11" font-family="var(--mono)" letter-spacing="1">PUNTO MEDIO DEL CLUB</text>`;

 /* La referencia de los rivales: una cruz discontinua en plata. Solo se pinta
    si cae DENTRO de los ejes; si queda fuera se dice con una nota, en vez de
    recortarla al borde y hacerla parecer un valor extremo del rango. */
 if(ref&&isFinite(ref.et)&&ref.rem!=null){
  const rx=X(ref.et), ry=Y(100*ref.rem);
  const dentro=rx>=pl&&rx<=W-pr&&ry>=pt_&&ry<=H-pb;
  if(!dentro){
   /* La referencia cae FUERA del rango de los tecnicos. No se recorta al borde
      como si fuera un valor mas: se marca en el margen con una flecha que dice
      hacia donde queda. Eso ES el hallazgo — todos los tecnicos del club estan
      a un lado de la referencia — y esconderlo seria perder informacion.
      Tampoco se estiran los ejes: comprimiria a los tecnicos en una esquina y
      se perderia la comparacion que de verdad importa. */
   const fx=Math.min(W-pr,Math.max(pl,rx)), fy=Math.min(H-pb,Math.max(pt_,ry));
   const izq=rx<pl, aba=ry>H-pb;
   g+=`<g data-tip="<b>Los rivales enfrentados</b>${ref.et.toFixed(2)} acciones por posesion y ${(100*ref.rem).toFixed(1)} remates por 100, sobre ${ref.np.toLocaleString("es-MX")} posesiones. Queda FUERA del rango de este grafico: todos los tecnicos del club estan al otro lado.">
     <path d="M${(izq?pl+2:fx)},${fy} l${izq?-9:9},-5 v10 z" fill="${C_RIV}"
      opacity=".8"/>
     <text x="${izq?pl+16:fx-16}" y="${(fy+4).toFixed(1)}"
      text-anchor="${izq?"start":"end"}" fill="${C_RIV}" font-size="11"
      font-family="var(--mono)" paint-order="stroke" stroke="rgba(0,0,0,.6)"
      stroke-width="3">LOS RIVALES ${ref.et.toFixed(1)} &rarr; fuera</text></g>`;
  }
  if(dentro){
   g+=`<line x1="${rx.toFixed(1)}" y1="${pt_}" x2="${rx.toFixed(1)}" y2="${H-pb}"
     stroke="${C_RIV}" opacity=".28" stroke-dasharray="3 6"/>
    <line x1="${pl}" y1="${ry.toFixed(1)}" x2="${W-pr}" y2="${ry.toFixed(1)}"
     stroke="${C_RIV}" opacity=".28" stroke-dasharray="3 6"/>
    <g data-tip="<b>Los rivales enfrentados</b>${ref.np.toLocaleString("es-MX")} posesiones de los ${ref.equipos||17} equipos que jugaron contra este club en esta ventana. NO es el promedio de la Liga MX: son posesiones jugadas CONTRA este club, asi que la cifra habla tambien de como juega el.">
     <circle cx="${rx.toFixed(1)}" cy="${ry.toFixed(1)}" r="6" fill="none"
      stroke="${C_RIV}" stroke-width="2"/>
     <circle cx="${rx.toFixed(1)}" cy="${ry.toFixed(1)}" r="1.8" fill="${C_RIV}"/>
     <text x="${(rx+11).toFixed(1)}" y="${(ry-9).toFixed(1)}" fill="${C_RIV}"
      font-size="11" font-family="var(--mono)" letter-spacing=".5"
      paint-order="stroke" stroke="rgba(0,0,0,.6)" stroke-width="3">LOS RIVALES</text></g>`;
  }
 }
 pts.forEach((p,i)=>{
  const act=p.n===dt||p.n===rv,esDT=p.n===dt;
  const r=6+7*Math.sqrt(p.np/nm);
  const tt=`<b>${esc(p.n)}</b>${p.et.toFixed(1)} acciones por posesion &middot; `+
   `${(p.rem*100).toFixed(1)} remates por 100 &middot; `+
   `${p.np.toLocaleString("es-MX")} posesiones.<br>Clic para analizarlo.`;
  g+=`<g class="pt celda" data-dt="${esc(p.n)}" data-tip="${tt}"
    opacity="${act?1:.45}">
   <circle cx="${X(p.et).toFixed(1)}" cy="${Y(p.rem*100).toFixed(1)}" r="0"
    fill="${esDT?'var(--a1)':act?'var(--a2)':'var(--tx3)'}">
    <animate attributeName="r" from="0" to="${r.toFixed(1)}" dur=".55s"
    begin="${(i*.08).toFixed(2)}s" fill="freeze" calcMode="spline"
    keySplines="0.16 1 0.3 1" keyTimes="0;1"/></circle>
   <text x="${X(p.et).toFixed(1)}" y="${(Y(p.rem*100)-r-10).toFixed(1)}"
    fill="${act?'var(--tx)':'var(--tx3)'}" font-size="${act?12.5:11}"
    font-weight="${act?700:400}" text-anchor="middle" pointer-events="none"
    font-family="var(--sans)">${esc(ape(p.n))}</text></g>`;});
 return g+`</svg>`;
}

/* ================= cuadro de referencia de la nube ================= */
/* Los cuatro cuadrantes se colocan EN LA MISMA POSICION que en la grafica, para
   que la vista pueda saltar de uno al otro sin traducir nada. */
const CUAD=[
 ["Vertical y peligroso","arriba &middot; izquierda",
  "Posesiones cortas que aun asi acaban en remate. Juego directo: pocos toques, mucha llegada."],
 ["Retiene y ataca","arriba &middot; derecha",
  "Alarga la posesión y además termina rematando. Es el cuadrante más exigente."],
 ["Vertical y sin llegada","abajo &middot; izquierda",
  "Posesiones cortas que tampoco acaban en remate: pierde el balón antes de generar peligro."],
 ["Retiene y controla","abajo &middot; derecha",
  "Alarga la posesión sin rematar más. No es un defecto: es controlar el partido con el balón."]];
function refCuadrantes(pts,n){
 const e=ejes(pts);
 return `<div class="card flat">
 <div class="eq">Cómo se lee esta gráfica</div>
 <div class="refgrid">
  <div>
   <div class="ejex"><b>Eje horizontal &mdash; Acciones por posesión</b>
    Cuántos pases, conducciones y remates encadena el equipo antes de perder el
    balón. Hacia la derecha, posesiones más largas.</div>
   <div class="ejex"><b>Eje vertical &mdash; Remates por 100 posesiones</b>
    De cada 100 posesiones, cuántas acaban en remate. Hacia arriba, más peligro
    generado.</div>
   <div class="ejex"><b>Las líneas punteadas</b>
    Marcan el punto medio del ${esc(n)}: ${e.mx.toFixed(1)} acciones y
    ${e.my.toFixed(1)} remates por 100. No son un objetivo, solo el centro de
    referencia del propio club.</div>
   <div class="ejex"><b>El tamaño del punto</b>
    Es el número de posesiones del técnico. Un punto pequeño tiene menos datos
    detrás, así que su posición es menos fiable.</div>
  </div>
  <div class="quad">`+CUAD.map(([t,pos,d])=>
   `<div class="qc"><div class="q-pos">${pos}</div>
    <div class="q-tit">${t}</div><div class="q-tx">${d}</div></div>`).join("")+
  `</div>
 </div></div>`;
}

/* ================= muestra por tecnico ================= */
function listaMuestra(pts,dt,rv){
 const nm=Math.max(...pts.map(p=>p.np));
 return `<div class="lista">`+pts.slice().sort((a,b)=>b.np-a.np).map(p=>{
  const act=p.n===dt||p.n===rv;
  return `<div class="item ${act?"on":""}" data-dt="${esc(p.n)}">
   <div class="it-tx"><div class="it-nom">${esc(p.n)}</div>
    <div class="it-sub">${p.et.toFixed(1)} acciones &middot; ${(p.rem*100).toFixed(1)} remates por 100</div></div>
   <div class="it-bar"><i data-w="${(p.np/nm*100).toFixed(1)}"
    style="background:${act?"var(--a1)":"var(--tx3)"}"></i></div>
   <div class="it-val">${(p.np/1000).toFixed(1)}k</div></div>`;}).join("")+`</div>`;
}

/* ================= armado de secciones ================= */
const vacio=(q,cmd)=>`<div class="vacio">Falta ${q} para esta pareja.<code>${cmd}</code></div>`;
const cab=(e,t,l)=>`<div class="eyebrow">${e}</div><h2>${t}</h2><div class="lead">${l}</div>`;


/* ============================ 05 · sin balón ============================ */
/* El reporte no muestra p-valores (principio del reto: la incertidumbre se
   dice en palabras). `fuerza` traduce el q a lenguaje. */
function fuerza(q){
 if(q===null||q===undefined)return{t:"sin contraste",c:"var(--tx3)"};
 if(q<=0.01) return{t:"muy sólido",c:"var(--a1)"};
 if(q<=0.05) return{t:"sólido, con margen estrecho",c:"var(--a1)"};
 if(q<=0.15) return{t:"insuficiente tras corregir",c:"var(--tx3)"};
 return{t:"no lo distinguimos del azar",c:"var(--tx3)"};
}

/* Mapa de Δπ. Rojo donde el foco presiona MÁS, azul donde presiona menos.
   Las zonas que sobreviven al FDR llevan borde continuo; el resto, punteado.
   Sin difuminar: el modelo estima una probabilidad constante por zona. */
function mapaPresion(zs,dt,rv){
 return pitch((s,w,h)=>{
  let vm=1e-9;zs.forEach(z=>vm=Math.max(vm,Math.abs(z.d)));
  let g="";
  zs.forEach(z=>{
   const v=Math.abs(z.d)/vm,x=z.ix*cw*s,y=z.iy*ch*s;
   const col=z.d>0?C_FOCO:C_NEG;
   const vive=z.q<=0.05;
   const tt=`<b>${esc(FRANJA[z.iy])}, tercio ${esc(TERCIO[z.ix])}</b>`+
    `${esc(ape(dt))} ${(z.pa*100).toFixed(1)}% · ${esc(ape(rv))} ${(z.pb*100).toFixed(1)}%`+
    (vive?" — diferencia que resiste la corrección":"");
   g+=`<g class="celda" data-tip="${tt}">
    <rect x="${x+2.5}" y="${y+2.5}" width="${cw*s-5}" height="${ch*s-5}" rx="8"
     fill="${col}" fill-opacity="${(.08+.62*v).toFixed(2)}"
     stroke="#fff" stroke-opacity="${vive?.85:.18}"
     stroke-width="${vive?2.2:1}" ${vive?"":'stroke-dasharray="4 4"'}/></g>`;
   if(v>.12)g+=`<text x="${x+cw*s/2}" y="${y+ch*s/2+4.5}" fill="#fff"
    font-size="12" font-weight="700" text-anchor="middle" pointer-events="none"
    font-family="var(--mono)" paint-order="stroke" stroke="rgba(0,0,0,.5)"
    stroke-width="2.6">${z.d>0?"+":""}${(z.d*100).toFixed(1)}</text>`;
  });
  return g;});
}

function barrasTercio(ts,dt,rv){
 if(!ts||!ts.length)return"";
 const vm=Math.max(...ts.map(t=>Math.abs(t.delta)),1e-9);
 return `<div class="lista">`+ts.map(t=>{
  const p=Math.abs(t.delta)/vm*100,pos=t.delta>0;
  return `<div class="item"><div class="it-tx">
   <div class="it-nom">tercio ${esc(t.tercio)}</div>
   <div class="it-sub">${(t.pi_a*100).toFixed(1)}% vs ${(t.pi_b*100).toFixed(1)}%</div></div>
   <div class="it-bar"><i data-w="${p.toFixed(1)}"
    style="background:${pos?C_FOCO:C_NEG}"></i></div>
   <div class="it-val">${pos?"+":""}${(t.delta*100).toFixed(1)}</div></div>`;
 }).join("")+`</div>`;
}

/* Mapa de NIVEL de un solo tecnico. Escala compartida entre los dos mapas
   (`vmax` se pasa desde fuera): con escalas independientes, dos mapas que
   parecen iguales pueden estar a niveles muy distintos. */
/* `col` nuevo: el foco va en el color del club y el rival en plata, igual que
   en la seccion de jugadores. Antes los dos mapas eran del mismo amarillo y
   solo el titulo de encima decia de quien era cada uno. */
function mapaNivel(zs,cual,vmax,nom,col){
 return pitch((s,w,h)=>{
  let g="";
  zs.forEach(z=>{
   const val=z[cual],v=Math.min(1,val/vmax),x=z.ix*cw*s,y=z.iy*ch*s;
   const tt=`<b>${esc(FRANJA[z.iy])}, tercio ${esc(TERCIO[z.ix])}</b>`+
    `Con ${esc(ape(nom))}, el ${(val*100).toFixed(1)}% de las acciones del rival `+
    `en esta zona se juegan con un defensor encima.`;
   g+=`<g class="celda" data-tip="${tt}">
    <rect x="${x+2.5}" y="${y+2.5}" width="${cw*s-5}" height="${ch*s-5}" rx="8"
     fill="${col||C_FOCO}" fill-opacity="${(.07+.72*v).toFixed(2)}"
     stroke="#fff" stroke-opacity="${(.14+.28*v).toFixed(2)}" stroke-width="1.1"/></g>`;
   if(v>.08)g+=`<text x="${x+cw*s/2}" y="${y+ch*s/2+4.5}" fill="#fff"
    font-size="12.5" font-weight="700" text-anchor="middle" pointer-events="none"
    font-family="var(--mono)" paint-order="stroke" stroke="rgba(0,0,0,.5)"
    stroke-width="2.6">${(val*100).toFixed(0)}%</text>`;
  });
  return g;});
}

/* Curva de decaimiento: la figura que explica el bloque de un vistazo.
   Dos lineas que se separan y no vuelven a juntarse cuentan una historia; dos
   que se cruzan seis veces cuentan otra, y ninguna tabla lo dice tan rapido. */
function curvaPresion(cv,dt,rv){
 if(!cv||cv.length<3)return"";
 const W=560,H=300,ml=52,mr=16,mt=18,mb=46;
 const iw=W-ml-mr,ih=H-mt-mb;
 const ks=cv.map(c=>c.k),k0=Math.min(...ks),k1=Math.max(...ks);
 let lo=1,hi=0;
 cv.forEach(c=>{lo=Math.min(lo,c.la,c.lb);hi=Math.max(hi,c.ha,c.hb);});
 lo=Math.max(0,lo-.02);hi=hi+.02;
 const X=k=>ml+(k-k0)/(k1-k0)*iw, Y=v=>mt+(1-(v-lo)/(hi-lo))*ih;
 let g=`<svg viewBox="0 0 ${W} ${H}">`;
 for(let t=0;t<=4;t++){
  const v=lo+(hi-lo)*t/4,y=Y(v);
  g+=`<line x1="${ml}" y1="${y}" x2="${W-mr}" y2="${y}" stroke="#fff"
   stroke-opacity=".07" stroke-width="1"/>
   <text x="${ml-9}" y="${y+4}" fill="var(--tx2)" font-size="12"
    text-anchor="end" font-family="var(--mono)">${(v*100).toFixed(0)}%</text>`;
 }
 ks.forEach(k=>{if(k%2===1||k===k1)g+=`<text x="${X(k)}" y="${H-mb+19}"
  fill="var(--tx2)" font-size="12" text-anchor="middle"
  font-family="var(--mono)">${k}</text>`;});
 [["a",C_FOCO,dt],["b",C_RIV,rv]].forEach(([su,col,nom])=>{
  const banda=cv.map(c=>`${X(c.k)},${Y(c["h"+su])}`).join(" ")+" "+
   cv.slice().reverse().map(c=>`${X(c.k)},${Y(c["l"+su])}`).join(" ");
  g+=`<polygon points="${banda}" fill="${col}" opacity=".15"/>`;
  g+=`<polyline points="${cv.map(c=>`${X(c.k)},${Y(c["p"+su])}`).join(" ")}"
   fill="none" stroke="${col}" stroke-width="2.4" stroke-linejoin="round"/>`;
  cv.forEach(c=>{g+=`<g class="celda" data-tip="<b>Toque ${c.k}</b>${esc(ape(nom))}:
   ${(c["p"+su]*100).toFixed(1)}% de esas acciones bajo presión">
   <circle cx="${X(c.k)}" cy="${Y(c["p"+su])}" r="3.6" fill="${col}"/>
   <circle cx="${X(c.k)}" cy="${Y(c["p"+su])}" r="9" fill="transparent"/></g>`;});
 });
 g+=`<text x="${ml+iw/2}" y="${H-5}" fill="var(--tx2)" font-size="11.5"
  text-anchor="middle" font-family="var(--mono)" letter-spacing="1.2">
  TOQUE DEL RIVAL DENTRO DE SU POSESIÓN</text>`;
 return g+`</svg>`;
}

function glosarioDefensa(n){
 return `<div class="card" style="padding:1.5rem 1.7rem;margin-bottom:1.3rem">
  <div class="eq">Cómo leer esta sección</div>
  <div class="nota" style="font-size:.92rem;max-width:none">
   <b style="color:var(--tx1)">Qué se mide.</b> Cada vez que el rival recupera
   el balón empieza una <em>posesión</em>: la cadena de pases y conducciones que
   encadena hasta que la pierde, la manda fuera o remata. Este bloque describe
   qué le hace el ${esc(n)} a esas cadenas — cuánto duran, cuánto peligro
   generan y en qué zonas encuentran oposición.
   <br><br>
   <b style="color:var(--tx1)">Cómo se mide.</b> Se sigue cada posesión rival
   acción por acción sobre una cuadrícula de veinte zonas, y se cuenta con qué
   frecuencia pasa de una zona a otra o se acaba. De ahí salen tres números con
   sentido futbolístico: cuántas acciones dura, con qué frecuencia acaba en
   remate, y qué proporción de las acciones del rival se juegan con un defensor
   encima. Todo está ajustado por los rivales que enfrentó cada técnico, para
   que un calendario más duro no se confunda con una idea de juego distinta.
   <br><br>
   <b style="color:var(--tx1)">Qué es un “punto porcentual” (pp).</b> La resta
   directa entre dos porcentajes. Si algo pasa de ocurrir el 20% de las veces a
   ocurrir el 31.6%, la diferencia son 11.6 pp. No es lo mismo que un 11.6% de
   aumento: aquí siempre son puntos, no porcentaje de porcentaje.
   <br><br>
   <b style="color:var(--tx1)">Qué significa “no distinguible del azar”.</b>
   Que con los partidos disponibles no podemos separar la diferencia del ruido
   normal entre partidos. <em>No</em> quiere decir que los dos técnicos sean
   iguales: quiere decir que si hay una diferencia, es más pequeña de lo que
   estos datos permiten ver.
   <br><br>
   <b style="color:var(--tx1)">Lo que esto no dice.</b> No dice quién defiende
   mejor. Describe <em>cómo</em> defiende cada uno; que una idea funcione
   depende de los jugadores, del rival y del marcador.
  </div></div>`;
}

function seccionDefensa(c,dt,rv,n,dir,eq){
 const D=c.defensa;
 const cmd18=`python scripts/18_campo_presion.py --club "${eq}" --a "${dt}" --b "${rv}" --n-perm 5000`;
 let h=cab("05 &middot; sin balón","Cuando el rival tiene el balón",
  `La otra mitad del juego. La misma maquinaria que describe cómo ataca el
   ${esc(n)}, aplicada a las posesiones <em>del rival</em>: cuánto le dejamos
   durar con el balón, cuánto peligro le concedemos, y en qué zonas del campo
   —y hasta qué momento de la jugada— lo presionamos.`);
 if(!D)return h+vacio("el bloque defensivo",cmd18);
 h+=glosarioDefensa(n);

 const p=D.pares[dt+"|"+rv]||D.pares[rv+"|"+dt];
 const inv=!D.pares[dt+"|"+rv]&&!!D.pares[rv+"|"+dt];

 const ins=D.instrumento[dt];
 if(ins){
  h+=`<div class="card flat" style="margin-bottom:1.2rem">
   <div class="c-lab">Presionar cambia el juego</div>
   <div class="c-val" style="color:var(--a1)">+<span data-num="${(ins.efecto*100).toFixed(1)}"
    data-dec="1">0</span><span style="color:var(--tx3);font-size:1.5rem"> puntos</span></div>
   <div class="c-pie">Antes de comparar técnicos hay que comprobar que
    presionar sirva de algo. Sirve: cuando el rival juega una acción con un
    defensor encima, la probabilidad de que esa sea la <b>última</b> acción de
    su posesión sube ${(ins.efecto*100).toFixed(1)} puntos porcentuales frente a
    la misma acción, en la misma zona, sin presión. Es decir, casi el doble.
    Comprobado en las cuatro etapas analizadas de los dos clubes.</div></div>`;
 }

 if(!p){return h+vacio("el contraste defensivo de esta pareja",cmd18);}
 if(inv)h+=`<div class="aviso">Los datos de esta pareja se calcularon en el
  orden inverso; los signos están referidos a ${esc(ape(rv))}.</div>`;

 if(p.concede){
  const cc=p.concede,da=cc.acciones.a-cc.acciones.b,dr=cc.remate.a-cc.remate.b;
  h+=`<div class="grid duo">
   <div class="card flat"><div class="c-lab">Acciones que le concede al rival</div>
    <div class="c-val">${cc.acciones.a.toFixed(2)}</div>
    <div class="c-pie">Pases y conducciones que el rival encadena, de media,
     antes de perder el balón. Con ${esc(ape(rv))} eran ${cc.acciones.b.toFixed(2)}.
     ${cc.acciones.sig?`La diferencia, ${Math.abs(da).toFixed(2)} acciones por
     posesión, se mantiene después de ajustar por los rivales que enfrentó cada
     uno.`:"La diferencia es demasiado pequeña para separarla del azar."}</div></div>
   <div class="card flat"><div class="c-lab">Posesiones del rival que acaban en remate</div>
    <div class="c-val">${(cc.remate.a*100).toFixed(1)}<span
     style="color:var(--tx3);font-size:1.5rem">%</span></div>
    <div class="c-pie">De cada 100 veces que el rival tiene el balón, termina
     rematando ${(cc.remate.a*100).toFixed(0)}. Con ${esc(ape(rv))},
     ${(cc.remate.b*100).toFixed(0)}.
     ${cc.remate.sig?`Diferencia de ${Math.abs(dr*100).toFixed(1)} puntos
     porcentuales.`:"La diferencia no es distinguible del azar."}</div></div></div>`;
 }

 /* --- ¿hasta cuándo aprieta? Ahora CON la curva. --- */
 if(p.nivel||p.curva){
  h+=`<div class="card" style="margin-top:1.2rem;padding:1.5rem 1.7rem">
   <div class="eq">¿Hasta cuándo aprieta?</div>
   <div class="nota" style="font-size:.95rem">Casi todos los equipos aprietan el
    primer toque del rival.
    Lo que separa a unos de otros es si siguen apretando cuando el rival ya ha
    encadenado dos o tres pases.</div>`;
  if(p.curva){
   h+=`<div class="titular">Cuanto más a la derecha sigue alta una línea,
     <b>más lejos persigue ese técnico</b> <span class="gris">la jugada del
     rival.</span></div>
    <div style="margin-top:1rem">${curvaPresion(p.curva,dt,rv)}</div>
    ${leyenda(SW(C_FOCO,esc(ape(dt))),SW(C_RIV,esc(ape(rv))))}
    <div class="nota">El eje de abajo es el número de toque dentro de la
     posesión del rival: 1 es el primer balón que juega tras recuperarlo, 5 es el
     quinto. Cada punto es qué proporción de esas acciones se jugó con un
     defensor encima. La banda alrededor es el margen de error: <b>donde las dos
     bandas se solapan, no podemos separar a los dos técnicos en ese toque.</b>
     El primer toque casi nunca lleva presión porque muchas posesiones del rival
     nacen de un saque o una falta, con el balón ya parado.</div>`;
  }
  if(p.nivel){
   const nv=p.nivel,f=fuerza(nv.q);
   h+=`<div class="grid duo" style="margin-top:1.1rem;align-items:stretch">
    <div class="card flat"><div class="c-lab">${esc(ape(dt))} · desde el toque ${nv.k0}</div>
     <div class="c-val">${(nv.pa*100).toFixed(1)}<span
      style="color:var(--tx3);font-size:1.5rem">%</span></div>
     <div class="c-pie">de ${nv.na.toLocaleString("es")} acciones del rival</div></div>
    <div class="card flat"><div class="c-lab">${esc(ape(rv))} · desde el toque ${nv.k0}</div>
     <div class="c-val">${(nv.pb*100).toFixed(1)}<span
      style="color:var(--tx3);font-size:1.5rem">%</span></div>
     <div class="c-pie">de ${nv.nb.toLocaleString("es")} acciones del rival</div></div></div>
    <div class="nota">Diferencia:
     <b style="color:var(--tx1)">${nv.dif>0?"+":""}${(nv.dif*100).toFixed(1)} puntos
     porcentuales</b> a favor de ${esc(ape(nv.dif>0?dt:rv))}.
     <b style="color:${f.c}">Resultado ${f.t}.</b></div>
    <div class="pie">Este número solo mira las posesiones rivales que llegaron al
     toque ${nv.k0}. Comprobamos que la presión no acaba las jugadas
     desproporcionadamente antes, así que el sesgo que eso podría introducir es
     pequeño — pero existe y conviene decirlo.</div>`;
  }
  h+=`</div>`;
 }

 /* --- dónde: los DOS mapas de nivel, y debajo el de diferencia --- */
 if(p.zonas&&p.zonas.length){
  const viven=p.zonas.filter(z=>z.q<=0.05);
  let vmax=1e-9;p.zonas.forEach(z=>vmax=Math.max(vmax,z.pa,z.pb));
  h+=`<div class="card" style="margin-top:1.2rem;padding:1.5rem 1.7rem">
   <div class="eq">¿Dónde aprieta?</div>
   <div class="titular">De cada 100 balones que el rival juega en esa casilla,
    <b>cuántos los juega con un defensor encima.</b> <span class="gris">Es la
    forma de ver en qué parte del campo cada técnico decide ir a por el balón en
    vez de esperar.</span></div>
   <div class="grid par">
    <div class="panel">${cap(C_FOCO,"Con "+ape(dt),"el técnico analizado")}
     ${mapaNivel(p.zonas,"pa",vmax,dt,C_FOCO)}</div>
    <div class="panel">${cap(C_RIV,"Con "+ape(rv),"la comparación")}
     ${mapaNivel(p.zonas,"pb",vmax,rv,C_RIV)}</div></div>
   ${leyenda(rampa(C_FOCO,"aprieta poco","aprieta mucho"),
    "Escala compartida: el mismo tono es el mismo porcentaje en los dos mapas.")}
   <div class="nota">El campo está visto desde el ${esc(n)}: su portería a la
    izquierda, la del rival a la derecha. Apretar en el tercio de la derecha es
    presión alta; hacerlo en el de la izquierda es defender cerca de casa.</div></div>
   <div class="grid duo" style="margin-top:1rem;align-items:stretch">
    <div class="card" style="padding:1.4rem">
     <div class="eq">La diferencia, en un solo mapa</div>
     <div class="titular">Los dos mapas de arriba, restados: <b>dónde aprieta más
      ${esc(ape(dt))}</b> <span class="gris">y dónde aprieta menos.</span></div>
     <div style="margin-top:.7rem">${mapaPresion(p.zonas,dt,rv)}</div>
     ${leyenda(SW(C_FOCO,esc(ape(dt))+" aprieta más ahí"),
      SW(C_NEG,esc(ape(rv))+" aprieta más ahí"),
      `<span class="leg"><i style="background:none;box-shadow:inset 0 0 0 2px #fff"></i>
       borde marcado = diferencia sólida</span>`)}
     <div class="nota">El número es la diferencia en
      <span class="term" data-tip="<b>Punto porcentual (pp)</b>La resta directa entre dos porcentajes. Pasar del 20% al 31.6% son 11.6 puntos, no un 11.6% de aumento.">puntos porcentuales</span>.
      El borde marcado señala las casillas cuya diferencia aguanta el hecho de
      mirar veinte casillas a la vez: cuantas más se miran, más fácil es que
      alguna parezca distinta por pura casualidad.</div></div>
    <div class="card flat"><div class="eq">Por franjas del campo</div>
     <div class="nota" style="margin-top:.5rem;margin-bottom:.9rem">El mismo dato
      agrupado en tres franjas: el tercio de la portería propia, el del medio y
      el de la portería rival. Con menos divisiones hay más partidos detrás de
      cada número, así que es más fiable que casilla por casilla.</div>
     ${barrasTercio(p.tercios,dt,rv)}
     <div class="nota">${viven.length?`${viven.length} casilla${viven.length>1?"s":""}
      con una diferencia que aguanta esa corrección.`:`Ninguna casilla la aguanta
      por separado. Si hay una diferencia de dónde se aprieta, está en el
      agregado por franjas, no en una casilla concreta.`}</div></div></div>`;
 } else {
  h+=`<div class="vacio" style="margin-top:1.2rem">Falta el mapa de presión para
   esta pareja: el contraste por zonas todavía no se ha calculado.
   <code>${cmd18}</code></div>`;
 }

 h+=`<div class="pie"><b style="color:var(--tx2)">Sobre el dato de presión.</b>
  La marca la anota el proveedor cuando un defensor entra en el radio de acción
  del rival. Va con una advertencia: un defensor consigue acercarse más cuando
  el rival ya ha hecho un mal control o está incómodo, así que parte de lo que
  aquí se lee como “presionar provoca la pérdida” puede ser en realidad “la
  pérdida estaba a punto de pasar y por eso el defensor llegó”. Los datos no
  permiten separar del todo las dos cosas.</div>`;
 return h;
}

/* ================= sección 06 · pruébalo tú ================= */
let SIM=null;
/* El tablero ya NO es una sección aparte: se inserta dentro de la 02, debajo
   de la huella táctica, que es donde se habla de territorio. */
function tableroHTML(c,dt,rv){
 const C=(c.cadena||{})[dt];
 if(!C||!C.zmat||!Object.keys(C.zmat).length) return "";
 const esClub=rv==="__CLUB__";
 const otro=esClub?null:(c.cadena||{})[rv];
 if(!esClub&&(!otro||!otro.zmat)) return "";
 const nomRv=esClub?"el club sin él":ape(rv);
 return `<div class="card" style="padding:1.4rem;margin-top:1rem">
  <div class="eq">La tabla que hay detrás de todo</div>
  <div class="titular">Todo el reporte sale de una sola pregunta:
   <b>desde cada casilla del campo, ¿a dónde va el balón después?</b>
   <span class="gris">Toca una casilla y verás las salidas de los dos, con sus
   porcentajes.</span></div>
  <div class="modo" id="modoMapa">
   <button data-m="vol" class="on">Dónde vive</button>
   <button data-m="REMATE">De dónde nace el remate</button>
   <button data-m="GOL">…y el gol</button>
  </div>
  <div class="titular" id="tituloMapa"></div>
  <div class="duocampo">
   <div><div class="campo-tit"><i style="background:${C_FOCO}"></i>
     ${esc(ape(dt))}<s id="nA"></s></div><div id="canchaA"></div></div>
   <div><div class="campo-tit"><i style="background:${C_RIV}"></i>
     ${esc(nomRv)}<s id="nB"></s></div><div id="canchaB"></div></div>
  </div>
  <div id="leyMapa"></div>
  <div id="panel" style="margin-top:1rem"></div>

  <div style="border-top:1px solid var(--brd2);margin-top:1.4rem;padding-top:1.2rem">
   <div class="eq">Y ahora, que el balón juegue solo</div>
   <div class="titular">Cada salto es una acción real de ${esc(ape(dt))},
    <span class="gris">sorteada con la frecuencia con la que su equipo la
    hizo.</span></div>
   <div class="sim">
    <div><div id="cancha"></div>
     <div class="btns">
      <button class="btn pri" id="b1">Una jugada</button>
      <button class="btn" id="b100">100 de golpe</button>
      <button class="btn" id="b1000">1,000</button>
      <button class="btn" id="bR">Reiniciar</button>
     </div>
     <div class="tira" id="tira"></div>
     <div id="relato" class="regla"></div></div>
    <div id="marcador"></div>
   </div>
   ${leyenda(SW(C_FOCO,"jugadas simuladas que pasan por ahí"),
     "La ficha blanca es el balón.")}
  </div></div>`;
}

/* --- pintado y estado del simulador --- */
/* Restos mayores: los enteros mostrados suman 100 EXACTO.
   Redondear cada casilla por separado hacia acumular +-2 puntos sobre 20
   casillas — no era la matriz, era el redondeo. */
function enteros100(vals){
 const cr=vals.map(v=>100*v), base=cr.map(x=>Math.floor(x));
 let falta=100-base.reduce((a,b)=>a+b,0);
 const orden=cr.map((x,i)=>[x-base[i],i]).sort((a,b)=>b[0]-a[0]);
 for(let k=0;k<Math.max(0,falta);k++) base[orden[k%orden.length][1]]++;
 return base;
}
function arrancaSim(c,dt,rv){
 const C=(c.cadena||{})[dt]; if(!C||!C.zmat) return;
 const esClub=rv==="__CLUB__";
 const B=esClub?(C.resto||null):((c.cadena||{})[rv]||null);
 if(!B||!B.zmat) return;
 const NXs=C.nx||NX, NYs=C.ny||NY, NZ=NXs*NYs;
 const nomB=esClub?"el club sin él":ape(rv);
 const est={n:0,T:0,g:0,s:0,calor:new Array(NZ).fill(0),
            anim:null,sel:null,ruta:null,paso:0,modo:"vol"};
 SIM=est;
 const $$=id=>document.getElementById(id);
 const zi=(ix,iy)=>ix*NYs+iy;
 const cen=(ix,iy,sc)=>[(ix+.5)*(L/NXs)*sc,(iy+.5)*(A/NYs)*sc];
 const finNom=k=>C.fin[String(k)]||"FIN";
 const finDe=i=>finNom(C.estados[i]);
 const nomZ=z=>`${FRANJA[Math.min(z[1],3)]}, ${TERCIO[Math.min(z[0],4)]}`;
 const nf=Math.max(1,(C.fases||[]).length);
 const FASENOM={open:"juego abierto",transition:"transición",
   restart:"reinicio",set_piece:"balón parado"};
 const TIPONOM={Pass:"pase",Carry:"conducción",Shot:"remate"};
 const faseDe=i=>{const f=(C.fases||[])[(+C.estados[i])%nf];
   return f?(FASENOM[f]||f):"";};

 /* ---------- las dos canchas de arriba ---------- */
 /* El lift usa gradiente DIVERGENTE: 1.00 es «lo normal» y se ve neutro; por
    encima se calienta, por debajo se enfria. Con la rampa secuencial del mapa
    de volumen, una zona de lift 1.0 pareceria un hallazgo. */
 /* Por encima de este cociente todas las casillas se pintan igual. Ver la
    nota de la leyenda: se declara, no se esconde. */
 const TOPE_LIFT=2.5;
 const liftDe=(DATA,i)=>{
  const L=(DATA.lift||{})[est.modo];
  if(!L||L.bloqueado) return undefined;
  const v=L.lift[i]; return (v===null||v===undefined)?null:v;
 };
 const pintaMapa=(cont,DATA,color,otros)=>{
  const esLift=est.modo!=="vol";
  const val=i=>DATA.zvis[i]||0;
  const enteros=enteros100(Array.from({length:NZ},(_,i)=>val(i)));
  const mx=Math.max(...Array.from({length:NZ},(_,i)=>val(i)),1e-9);
  $$(cont).innerHTML=pitch((sc,w,hh)=>{
   const cw2=(L/NXs)*sc, ch2=(A/NYs)*sc;
   let g=`<defs><marker id="fl${cont}" viewBox="0 0 10 10" refX="9" refY="5"
     markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
     <path d="M0,1 L10,5 L0,9 z" fill="#fff"/></marker></defs>`;
   for(let ix=0;ix<NXs;ix++)for(let iy=0;iy<NYs;iy++){
    const i=zi(ix,iy), sel=est.sel===i;
    let relleno=color, alfa, txt, opTxt=1, tip;
    if(esLift){
     const lf=liftDe(DATA,i);
     if(lf===null||lf===undefined){
      /* sin soporte: la casilla va VACIA. Pintarla tenue se leeria como
         «poco», y lo correcto es «no lo sabemos». */
      relleno="none"; alfa=0; txt="";
      tip=`<b>${esc(nomZ([ix,iy]))}</b>Sin datos suficientes para esta casilla: menos de 10 jugadas de las que acabaron así pasaron por aquí.`;
     }else{
      /* Escala LOGARITMICA recortada en TOPE_LIFT. El lift es un cociente:
         2x y 0.5x estan igual de lejos de 1 en sentido multiplicativo, y en
         escala lineal el lado bajo se comprimiria a la mitad.
         El recorte existe porque el centro del area da ~4x para todos los
         tecnicos —hay que llegar al area para rematar— y esas dos casillas
         tapaban las diferencias de las zonas intermedias, que es donde esta la
         firma tactica. El NUMERO impreso sigue siendo el lift real. */
      const d=Math.min(1,Math.abs(Math.log(Math.max(lf,1e-6)))/Math.log(TOPE_LIFT));
      relleno=lf>=1?color:C_RIV; alfa=.05+.62*d;
      txt=lf.toFixed(2)+"×"; opTxt=.55+.45*d;
      tip=`<b>${esc(nomZ([ix,iy]))}</b>Las jugadas que acaban en ${est.modo==="GOL"?"gol":"remate"} pasan por aquí <b>${lf.toFixed(2)} veces</b> ${lf>=1?"más":"menos"} que una jugada cualquiera.`;
     }
    }else{
     const v=val(i)/mx; alfa=.05+.62*v; txt=enteros[i]+"%"; opTxt=.55+.45*v;
     tip=`<b>${esc(nomZ([ix,iy]))}</b>El equipo pasa aquí el ${(100*val(i)).toFixed(1)}% de sus acciones. Toca para ver a dónde va el balón desde aquí.`;
    }
    g+=`<g class="celda-cl" data-z="${i}" data-tip="${tip}">
     <rect x="${ix*cw2+2.5}" y="${iy*ch2+2.5}" width="${cw2-5}" height="${ch2-5}"
      rx="9" fill="${relleno}" fill-opacity="${alfa.toFixed(3)}"
      stroke="#fff" stroke-opacity="${sel?.95:(.10+.24*(alfa)).toFixed(3)}"
      stroke-width="${sel?2.6:1.1}"/></g>`;
    if(txt){const [cx,cy]=cen(ix,iy,sc);
     g+=`<text x="${cx}" y="${cy+5}" text-anchor="middle" fill="#fff"
      font-size="${esLift?12:(11+5*val(i)/mx).toFixed(1)}" font-weight="700"
      font-family="var(--mono)" pointer-events="none" paint-order="stroke"
      stroke="rgba(0,0,0,.55)" stroke-width="3"
      opacity="${opTxt.toFixed(2)}">${txt}</text>`;}
   }
   if(!esLift&&est.sel!==null&&DATA.zmat[est.sel]){
    const a=cen(Math.floor(est.sel/NYs),est.sel%NYs,sc);
    DATA.zmat[est.sel].dest.forEach(([b,pr])=>{
     if(b===est.sel||pr<0.02) return;
     const q=cen(Math.floor(b/NYs),b%NYs,sc);
     const dx=q[0]-a[0],dy=q[1]-a[1],d=Math.hypot(dx,dy)||1;
     const mx2=(a[0]+q[0])/2-dy/d*d*.16, my2=(a[1]+q[1])/2+dx/d*d*.16;
     g+=`<path d="M${a[0]},${a[1]} Q${mx2},${my2} ${q[0]},${q[1]}" fill="none"
       stroke="#fff" stroke-opacity="${(.28+.62*Math.min(1,pr/.3)).toFixed(2)}"
       stroke-width="${(1.3+4.5*Math.min(1,pr/.3)).toFixed(1)}"
       stroke-linecap="round" marker-end="url(#fl${cont})"/>
      <text x="${mx2}" y="${my2-4}" text-anchor="middle" fill="#fff"
       font-size="12" font-weight="700" font-family="var(--mono)"
       paint-order="stroke" stroke="rgba(0,0,0,.7)" stroke-width="3.2"
       pointer-events="none">${(100*pr).toFixed(0)}%</text>`;
    });
   }
   return g;});
  $$(cont).querySelectorAll("[data-z]").forEach(el=>{
   el.onclick=()=>{const z=+el.dataset.z;
     est.sel=(est.sel===z?null:z); pintaDuo(); panel();};});
 };
 const pintaDuo=()=>{pintaMapa("canchaA",C,C_FOCO); pintaMapa("canchaB",B,C_RIV);};

 /* Bloqueo del modo GOL: se desactiva DICIENDO POR QUE y con el n real, en vez
    de mostrar cocientes calculados sobre veinte goles. */
 const bloqueo=D_=>{const L=(D_.lift||{})[est.modo];
   return (L&&L.bloqueado)?L:null;};

 const modoMapa=m=>{
  est.modo=m; est.sel=null;
  document.querySelectorAll("#modoMapa button").forEach(b=>
   b.classList.toggle("on",b.dataset.m===m));
  const bA=bloqueo(C), bB=bloqueo(B);
  const T=$$("tituloMapa"), LY=$$("leyMapa");
  if(m==="vol"){
   T.innerHTML=`<b>Dónde vive el equipo.</b> <span class="gris">El % de sus
    acciones en cada casilla. Toca una para ver a dónde manda el balón desde
    ahí.</span>`;
   LY.innerHTML=leyenda(rampa(C_FOCO,"pasa poco por ahí","mucho"),
     "Los números suman 100.");
  }else if(bA||bB){
   const q=bA||bB, quien=bA?ape(dt):nomB;
   T.innerHTML=`<b>No hay muestra suficiente.</b> <span class="gris">${esc(quien)}
    tiene <b>${q.n}</b> jugadas que acabaron en ${m==="GOL"?"gol":"remate"}, y
    hacen falta ${q.minimo}. Con menos, el cociente de una casilla lo deciden
    dos o tres jugadas y parece un hallazgo sin serlo.</span>`;
   LY.innerHTML="";
  }else{
   const nom=m==="GOL"?"gol":"remate";
   T.innerHTML=`<b>Por dónde pasan las jugadas que acaban en ${nom}</b>,
    <span class="gris">comparado con una jugada cualquiera del mismo equipo.
    <b>1.00×</b> es lo normal; por encima, esa casilla aparece más en las
    jugadas peligrosas.</span>`;
   LY.innerHTML=leyenda(SW(C_FOCO,"aparece MÁS en las jugadas de "+nom),
     SW(C_RIV,"aparece menos"),
     `<span class="leg"><i style="background:none;box-shadow:inset 0 0 0 1px rgba(255,255,255,.25)"></i>sin datos suficientes</span>`,
     `el color satura en ${TOPE_LIFT}×`)+
    `<div class="nota"><b>Por qué el color se corta en ${TOPE_LIFT}×.</b> El
     centro del área da alrededor de 4× para <em>cualquier</em> técnico: para
     rematar hay que llegar ahí. Si el color llegara hasta 4×, esas dos casillas
     se comerían toda la escala y los dos mapas saldrían idénticos. Cortando en
     ${TOPE_LIFT}× el contraste se desplaza a las zonas intermedias, que es
     donde se ve <b>por qué banda construye cada uno</b>.
     <b>El número de cada casilla sigue siendo el valor real</b>: solo cambia el
     color, no el dato.</div>`+
    `<div class="nota"><b>No es causal.</b> Que una jugada pase por aquí no
     provoca el ${nom}: puede ser que las jugadas que ya iban bien lleguen a esta
     zona. El modelo señala rutas asociadas al peligro, no relaciones de causa.</div>`;
  }
  pintaDuo(); panel();
 };

 /* ---------- el desglose comparado ---------- */
 const panel=()=>{
  const P=$$("panel"); if(!P) return;
  if(est.modo!=="vol"){
   P.innerHTML=`<div class="regla">Cada casilla dice <b>cuántas veces más (o
    menos)</b> pasan por ahí las jugadas peligrosas frente a una cualquiera.
    Vuelve a «Dónde vive» para explorar las salidas de cada casilla.</div>`;
   return;}
  if(est.sel===null||!C.zmat[est.sel]){
   P.innerHTML=`<div class="regla">Toca cualquier casilla de las dos canchas.
    Verás <b>a dónde manda el balón desde ahí</b> cada uno, y con qué frecuencia
    la jugada termina en ese punto.</div>`; return;}
  const z=est.sel, za=C.zmat[z], zb=B.zmat[z];
  const nom=nomZ([Math.floor(z/NYs),z%NYs]);
  const fila=(et,a,b)=>`<div class="fila"><span>${esc(et)}</span>
    <span class="bar"><i style="width:${Math.min(100,a*100).toFixed(0)}%;background:${C_FOCO}"></i></span>
    <b>${(100*a).toFixed(1)}%</b>
    <span class="bar"><i style="width:${Math.min(100,b*100).toFixed(0)}%;background:${C_RIV}"></i></span>
    <b>${(100*b).toFixed(1)}%</b></div>`;
  const claves=[...new Set([...Object.keys(za.fin),
    ...(zb?Object.keys(zb.fin):[])])].sort((x,y)=>
      (zb?(za.fin[y]||0)+(zb.fin[y]||0):(za.fin[y]||0))-
      (zb?(za.fin[x]||0)+(zb.fin[x]||0):(za.fin[x]||0)));
  P.innerHTML=`<div class="eq">${esc(nom)}</div>
   <div class="desg" style="margin-top:.7rem">
    <div class="fila" style="color:var(--tx3);font-size:.78rem">
     <span></span><span></span><b>${esc(ape(dt))}</b><span></span><b>${esc(nomB)}</b></div>
    ${fila("sigue jugando",za.sigue,zb?zb.sigue:0)}
    ${claves.map(k=>fila(finNom(k).toLowerCase(),za.fin[k]||0,
       zb?(zb.fin[k]||0):0)).join("")}</div>
   <div class="nota">Las flechas de cada cancha son las salidas más frecuentes
    desde esta casilla. <b>${za.n.toLocaleString("es-MX")}</b> acciones detrás
    del reparto de ${esc(ape(dt))}${zb?`, <b>${zb.n.toLocaleString("es-MX")}</b>
    del de ${esc(nomB)}`:""}.</div>`;
 };

 /* ---------- el simulador de abajo ---------- */
 const pintaSim=()=>{
  const tot=est.calor.reduce((a,b)=>a+b,0)||1;
  const mx=Math.max(...est.calor,1);
  $$("cancha").innerHTML=pitch((sc,w,hh)=>{
   const cw2=(L/NXs)*sc, ch2=(A/NYs)*sc; let g="";
   for(let ix=0;ix<NXs;ix++)for(let iy=0;iy<NYs;iy++){
    const i=zi(ix,iy), v=est.calor[i]/mx;
    g+=`<rect x="${ix*cw2+2.5}" y="${iy*ch2+2.5}" width="${cw2-5}"
      height="${ch2-5}" rx="9" fill="${C_FOCO}"
      fill-opacity="${(.04+.62*v).toFixed(3)}" stroke="#fff"
      stroke-opacity="${(.09+.2*v).toFixed(3)}" stroke-width="1.1"/>`;
    if(est.n>=50&&est.calor[i]/tot>.004){const [cx,cy]=cen(ix,iy,sc);
     g+=`<text x="${cx}" y="${cy+5}" text-anchor="middle" fill="#fff"
       font-size="12" font-weight="700" font-family="var(--mono)"
       paint-order="stroke" stroke="rgba(0,0,0,.5)" stroke-width="3"
       opacity="${(.5+.45*v).toFixed(2)}">${(100*est.calor[i]/tot).toFixed(0)}%</text>`;}
   }
   if(est.ruta){
    const pts=est.ruta.ruta.slice(0,est.paso).map(i=>C.zonas[i]).filter(Boolean)
      .map(z=>cen(z[0],z[1],sc));
    for(let k=1;k<pts.length;k++)
     g+=`<line x1="${pts[k-1][0]}" y1="${pts[k-1][1]}" x2="${pts[k][0]}"
       y2="${pts[k][1]}" stroke="#fff"
       stroke-opacity="${(.25+.5*k/pts.length).toFixed(2)}" stroke-width="2.4"
       stroke-linecap="round"/>`;
    const b=pts[pts.length-1];
    if(b) g+=`<circle cx="${b[0]}" cy="${b[1]}" r="15" fill="#fff"
      fill-opacity=".13"/><circle class="bola" cx="${b[0]}" cy="${b[1]}" r="8.5"
      fill="#fff" stroke="${C_FOCO}" stroke-width="3"/>`;
   }
   return g;});
 };

 /* El TIPO de accion se sortea de la mezcla real de esa zona; la FASE sale
    EXACTA del estado, porque el estado es (zona x fase). */
 const tipoEn=(i,termina)=>{
  const z=C.zonas[i]; if(!z) return "";
  const m=((C.ztipo||{})[zi(z[0],z[1])]||{})[termina?"fin":"sigue"];
  if(!m) return "";
  let u=Math.random(), a=0, ult="";
  for(const k in m){a+=m[k]; ult=k; if(u<=a) return TIPONOM[k]||k.toLowerCase();}
  return TIPONOM[ult]||ult.toLowerCase();
 };

 const tira=()=>{
  const t=$$("tira"); if(!t) return;
  if(!est.ruta){t.innerHTML="";return;}
  const vis=est.ruta.ruta.slice(0,est.paso); let o="";
  vis.forEach((i,k)=>{const z=C.zonas[i]; if(!z)return;
   if(k) o+=`<span class="flecha">&rsaquo;</span>`;
   const tp=est.ruta.tipos[k];
   o+=`<span class="fx${k===vis.length-1?" on":""}">${esc(nomZ(z))}${
     tp?` · ${esc(tp)}`:""}</span>`;});
  const u=est.ruta.ruta[est.paso-1];
  if(est.paso===est.ruta.ruta.length&&C.abs[u]){
   const et=finDe(u), malo=!/GOL|REMATE/.test(et);
   o+=`<span class="flecha">&rsaquo;</span><span class="fx fin${malo?" mal":""}">${esc(et)}</span>`;}
  t.innerHTML=o;
 };

 const marcador=()=>{
  const M=$$("marcador"); if(!M) return;
  if(!est.n){M.innerHTML=`<div class="regla">Pulsa <b>Una jugada</b> y mira el
   balón moverse. Verás de dónde salen la duración media y la probabilidad de
   gol del reporte.</div>`; return;}
  const pg=est.g/est.n, ps=est.s/est.n;
  M.innerHTML=`<div class="eq">Después de ${est.n.toLocaleString("es-MX")} jugadas</div>
   <div class="cifra" style="margin-top:.8rem"><u>DURACIÓN MEDIA</u>
    <b>${(est.T/est.n).toFixed(2)}</b><i>acciones por jugada</i></div>
   <div class="cifra"><u>ACABAN EN REMATE</u>
    <b class="sm">${(100*ps).toFixed(1)}%</b></div>
   <div class="cifra"><u>ACABAN EN GOL</u>
    <b class="sm">${(100*pg).toFixed(1)}%</b>
    <i>${pg>0?`una de cada ${Math.round(1/pg).toLocaleString("es-MX")}`:""}</i></div>
   <div class="nota">${est.n<200
    ? "Con pocas jugadas estos números bailan mucho. Simula 1,000."
    : `Ya casi no se mueven. Por eso el reporte usa
       <b>${(C.n_pos||0).toLocaleString("es-MX")}</b> jugadas reales.`}</div>`;
 };

 const unaJugada=()=>{
  const r=simulaUna(C);
  r.tipos=r.ruta.map((i,k)=>tipoEn(i,k===r.ruta.length-2));
  est.n++; est.T+=r.largo;
  if(r.gol) est.g++;
  if(r.remate) est.s++;
  r.ruta.forEach(i=>{const z=C.zonas[i]; if(z) est.calor[zi(z[0],z[1])]++;});
  return r;
 };

 const anima=r=>{
  clearInterval(est.anim); est.ruta=r; est.paso=1;
  ["b1","b100","b1000"].forEach(i=>$$(i)&&($$(i).disabled=true));
  const f0=faseDe(r.ruta[0]);
  const tic=()=>{
   pintaSim(); tira();
   $$("relato").innerHTML=`Jugada nacida en <b>${esc(f0||"juego abierto")}</b>
     &mdash; así empezó la posesión, y es la otra mitad del estado del modelo
     junto con la zona.`;
   if(est.paso>=r.ruta.length){
    clearInterval(est.anim);
    $$("relato").innerHTML=`Jugada nacida en <b>${esc(f0||"juego abierto")}</b>.
      Duró <b>${r.largo}</b> ${r.largo===1?"acción":"acciones"} y acabó en
      <b>${esc(r.fin)}</b>.`;
    ["b1","b100","b1000"].forEach(i=>$$(i)&&($$(i).disabled=false));
    return;}
   est.paso++;};
  tic(); est.anim=setInterval(tic,340);
 };

 const corre=(k,animar)=>{
  let u=null; for(let i=0;i<k;i++) u=unaJugada();
  if(animar) anima(u);
  else{clearInterval(est.anim); est.ruta=null; est.paso=0; pintaSim(); tira();
   $$("relato").innerHTML=`Se simularon <b>${k.toLocaleString("es-MX")}</b>
     jugadas. Los números de las casillas son ahora las simuladas: compáralos
     con los reales de las canchas de arriba.`;}
  marcador();
 };

 $$("b1").onclick=()=>corre(1,true);
 $$("b100").onclick=()=>corre(100,false);
 $$("b1000").onclick=()=>corre(1000,false);
 $$("bR").onclick=()=>{clearInterval(est.anim);
  est.n=est.T=est.g=est.s=0; est.calor.fill(0); est.ruta=null; est.paso=0;
  $$("relato").textContent=""; ["b1","b100","b1000"].forEach(i=>$$(i)&&($$(i).disabled=false));
  pintaSim(); tira(); marcador();};

 document.querySelectorAll("#modoMapa button").forEach(b=>
  b.onclick=()=>modoMapa(b.dataset.m));
 if($$("nA")) $$("nA").textContent=(C.n_pos||0).toLocaleString("es-MX")+" jugadas";
 if($$("nB")) $$("nB").textContent=(B.n_pos||0).toLocaleString("es-MX")+" jugadas";
 modoMapa("vol"); pintaSim(); marcador();
}

/* --- prueba de permutación interactiva --- */
function arrancaNula(c,dt,rv){
 const par=c.pares[`${dt}|${rv}`]||c.pares[`${rv}|${dt}`];
 const $$=id=>document.getElementById(id);
 if(!par||!par.et||!$$("nula")) return;
 const real=Math.abs(par.et.diff_pct||0);
 // Escala de la nula a partir del IC ya calculado: el semiancho es ~1.96 sigma,
 // asi que sigma ~ semiancho/1.96. No se re-estima nada, se REPRESENTA lo que
 // el bootstrap ya midio.
 const sig=Math.max(1e-6,((par.et.hi_pct-par.et.lo_pct)/2)/1.96);
 const nul=[];
 const pinta=()=>{
  const W=430,H=170,mb=28,mx=Math.max(real*1.35,3*sig);
  const X=v=>W/2+v/mx*(W/2-14);
  const bins=new Array(31).fill(0);
  nul.forEach(v=>{const b=Math.round((v/mx)*15)+15;
    if(b>=0&&b<31)bins[b]++;});
  const my=Math.max(...bins,1);
  let g=`<svg viewBox="0 0 ${W} ${H}">`;
  bins.forEach((c,i)=>{const x=X((i-15)/15*mx);
   g+=`<rect x="${x-5}" y="${H-mb-c/my*(H-mb-24)}" width="10"
     height="${c/my*(H-mb-24)}" fill="var(--riv)" fill-opacity=".5" rx="1.5"/>`;});
  g+=`<line x1="${X(real)}" y1="14" x2="${X(real)}" y2="${H-mb}"
    stroke="${C_FOCO}" stroke-width="2.5"/>
   <text x="${X(real)}" y="10" fill="${C_FOCO}" font-size="11.5"
    text-anchor="middle" font-weight="700" font-family="var(--mono)">real
    ${real.toFixed(1)}%</text>
   <line x1="8" y1="${H-mb}" x2="${W-8}" y2="${H-mb}" stroke="var(--brd)"/>
   <text x="${W/2}" y="${H-8}" fill="var(--tx2)" font-size="11"
    text-anchor="middle" font-family="var(--mono)" letter-spacing="1">
    DIFERENCIA AL BARAJAR (%)</text></svg>`;
  $$("nula").innerHTML=g;
  if(nul.length>=20){
   const fuera=nul.filter(v=>Math.abs(v)>=real).length;
   $$("nulaTx").innerHTML=`De <b>${nul.length}</b> barajadas,
    <b>${fuera}</b> dieron una diferencia tan grande como la real
    (${real.toFixed(1)}%). ${fuera===0
     ? "Ninguna. Por eso decimos que la diferencia no es casualidad."
     : fuera/nul.length<0.05
      ? "Muy pocas: la diferencia real es difícil de explicar por azar."
      : "Bastantes: con estos datos no podemos separarla del azar."}`;
  }
 };
 const baraja=k=>{for(let i=0;i<k;i++){
   // normal por Box-Muller, centrada en 0: la hipotesis nula es que el
   // entrenador no importa y la diferencia observada es ruido de muestreo
   const u=Math.random()||1e-9, v=Math.random();
   nul.push(sig*Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v));} pinta();};
 pinta();
 $$("bP").onclick=()=>baraja(1);
 $$("bP200").onclick=()=>baraja(200);
}

function render(){
 const n=$("selClub").value,c=DATOS.clubes[n];
 const dt=$("selDT").value,rv=$("selRival").value;

 /* «El club, sin el» solo aplica al tablero de la seccion 02. Las demas
    secciones contrastan DOS ERAS CONCRETAS con intervalo de confianza, y esos
    artefactos (ic_*, plantel_*, campo_presion_*) se generan por pareja: no
    existen para "el resto del club". En vez de inventarlos o de romperse, se
    dice por que no aplican. */
 if(rv==="__CLUB__"){
  $("s1").innerHTML=cab("02 &middot; el territorio","Frente al club, sin él",
   `Estás comparando a ${esc(ape(dt))} con <b>las demás etapas de ${esc(n)}</b>,
    no con otro técnico. Abajo tienes su tabla de decisiones frente a la del
    club sin él.`)+tableroHTML(c,dt,rv);
  try{arrancaSim(c,dt,rv);}catch(e){console.error("tablero:",e);}
  const aviso=(id,t2)=>{$(id).innerHTML=`<div class="vacio">${t2}</div>`;};
  ["s0","s2","s3","s4"].forEach(id=>aviso(id,
   `Esta sección compara <b>dos etapas concretas</b> con su intervalo de
    confianza, y esos contrastes se calculan por pareja de técnicos.
    Elige un técnico en «frente a» para verla.`));
  return;
 }

 const par=c.pares[dt+"|"+rv];
 const pts=perfiles(c);
 /* La ruta y el equipo vienen de los datos, no de un ternario con dos
    clubes escritos a mano: este texto es un comando que el lector copia y
    pega, y apuntar al club equivocado es peor que no mostrarlo. */
 const dir=c.dir||"data/processed";
 const eq=c.team||n;

 /* ---- 01 el ritmo ---- */
 let h=cab("01 &middot; el ritmo","Cara a cara",
  `Tres números resumen cómo se comporta el ${n} con cada técnico, sobre miles
   de posesiones. El anillo sitúa a ${ape(dt)} dentro del rango de todo el club.`);
 if(par){
  h+=`<div class="grid gm">`+METRICAS.map(m=>{
   const vals=pts.map(p=>m.esc(p[m.k]));
   return `<div class="card lift">${anillo(m,m.esc(par[m.k].a),
    m.esc(par[m.k].b),Math.min(...vals),Math.max(...vals),dt,rv)}</div>`;
  }).join("")+`</div>
  <div class="card flat" style="margin-top:1rem">
   <div class="eq">¿La diferencia sobrevive al azar?</div>
   <div class="titular">Si la barra <b>no toca la línea del cero</b>, la
    diferencia es real. <span class="gris">Si la cruza, no la distinguimos del
    vaivén normal entre partidos.</span></div>
   ${intervalos(par,dt,rv)}</div>
  <div class="pie">Cada diferencia se recalculó mil veces sobre muestras
   distintas de partidos. La barra es el rango de valores compatibles con los
   datos: si toca la línea del cero, no distinguimos la diferencia del azar.
   ${par.n_a.toLocaleString("es-MX")} posesiones de ${ape(dt)} contra
   ${par.n_b.toLocaleString("es-MX")} de ${ape(rv)}.</div>`;
 } else h+=vacio("el análisis de duración",
   `python scripts/08_ic_derivados.py --a "${dt}" --b "${rv}" --club "${eq}" --indir ${dir}`);
 $("s0").innerHTML=h;

 /* ---- 02 el territorio ---- */
 const top=c.huella[dt];
 h=cab("02 &middot; el territorio","Dónde se le nota",
  `El campo está partido en veinte casillas. Estas son las únicas en las que
   ${ape(dt)} hace algo distinto de lo que hacen los demás técnicos del club —
   distinto de verdad, más de lo que explicaría la variación normal entre
   partidos. Las etiquetas dicen en qué tipo de jugada se le nota.`);
 if(top&&top.length){
  h+=`<div class="grid duo">
   <div class="pega"><div class="card" style="padding:1.1rem">
    ${huellaSVG(top)}</div></div>
   <div class="card flat">
    <div class="eq">Señal frente a ruido</div>
    ${barrasHuella(top,dt)}</div></div>
   <div class="eq" style="margin-top:2rem">Cómo se lee el mapa</div>
   <div class="grid g2">`+EXPLICA.map(([et,t,d])=>
    `<div class="card flat" style="padding:1rem 1.2rem">
     <div style="font-size:.87rem;font-weight:700;margin-bottom:.3rem">
      <span style="font-size:.72rem;color:#0b0b0e;background:var(--a1);
       border-radius:6px;padding:.16rem .5rem;margin-right:.5rem">${et}</span>${t}</div>
     <div style="font-size:.79rem;font-weight:300;color:var(--tx2);line-height:1.45">${d}</div>
    </div>`).join("")+`
    <div class="card flat" style="padding:1rem 1.2rem">
     <div class="c-lab">dos etiquetas</div>
     <div style="font-size:.79rem;font-weight:300;color:var(--tx2);line-height:1.45;margin-top:.4rem">Cuando una zona muestra dos o más, ese técnico se distingue ahí en varios tipos de jugada a la vez.</div></div>
    <div class="card flat" style="padding:1rem 1.2rem">
     <div class="c-lab">más brillante</div>
     <div style="font-size:.79rem;font-weight:300;color:var(--tx2);line-height:1.45;margin-top:.4rem">Cuanto más intenso el color, más se separa esa zona de lo que hacen los demás técnicos del club.</div></div>
   </div>
   ${leyenda(rampa(C_FOCO,"se separa poco","se separa mucho"),
    "Solo se pintan las zonas donde la diferencia supera al azar.")}
   <div class="pie">El resto del campo lo juegan casi igual: las casillas vacías
   no son un hueco en los datos, son zonas donde ${esc(ape(dt))} hace lo mismo
   que los demás técnicos del club. Toca o señala una barra de la derecha para
   encender su casilla en el campo.</div>`;
 } else h+=vacio("la huella táctica",
   `python scripts/09_huella_efecto.py --unit coach --value "${dt}" --baseline other_coaches --club "${eq}" --indir ${dir}`);
 $("s1").innerHTML=h+tableroHTML(c,dt,rv);
 try{arrancaSim(c,dt,rv);}catch(e){console.error("tablero:",e);}

 /* ---- 03 el factor humano ---- */
 h=cab("03 &middot; el factor humano","No son los fichajes",
  `La objeción evidente a todo lo anterior: quizá el equipo no cambió porque
   cambiara el técnico, sino porque llegaron otros jugadores. Así que miramos
   solo a los futbolistas que jugaron con los dos, y comparamos a cada uno
   <em>consigo mismo</em>.`);
 if(par&&par.plantel){const p=par.plantel;
  h+=`<div class="grid g3">
   <div class="card lift" data-tip="<b>Jugadores compartidos</b>Futbolistas con datos suficientes en las dos etapas.">
    <div class="c-lab">En común</div>
    <div class="c-val" data-num="${p.compartidos}" data-dec="0">0</div>
    <div class="c-pie">de ${p.jugadores_a} que usó ${ape(dt)}</div></div>
   <div class="card lift" data-tip="<b>Acciones heredadas</b>Porcentaje de las acciones de ${esc(ape(dt))} ejecutadas por jugadores que ya estaban con ${esc(ape(rv))}.">
    <div class="c-lab">Acciones heredadas</div>
    <div class="c-val"><span data-num="${p.pct}" data-dec="0">0</span>%</div>
    <div class="c-pie">del plantel de ${ape(rv)}</div></div>
   <div class="card lift" data-tip="<b>Cambiaron su juego</b>Cada jugador se compara CONSIGO MISMO. Por azar se esperaria menos de uno.">
    <div class="c-lab">Cambiaron su juego</div>
    <div class="c-val" style="color:var(--a1)"><span data-num="${p.cambian}"
     data-dec="0">0</span><span style="color:var(--tx3);font-size:1.5rem">/${p.total}</span></div>
    <div class="c-pie">mismos futbolistas, otro patrón</div></div></div>`;
  if(p.pct<45)h+=`<div class="aviso">Solapamiento bajo (${p.pct.toFixed(0)}%):
   con pocos jugadores en común este contraste pierde fuerza.</div>`;
  if(p.lista.length){
   const vm=Math.max(...p.lista.map(j=>j.exceso),1e-9);
   const ninguno=p.cambian===0;
   /* Dos filas horizontales: arriba las dos canchas del jugador lado a lado,
      abajo el mapa de diferencia junto a la lista. Apiladas en una columna
      estrecha las canchas quedaban diminutas y la comparacion se perdia. */
   h+=`<div id="mapas" style="margin-top:1.8rem"></div>
   <div class="grid duo" style="margin-top:1rem;align-items:stretch">
    <div id="delta"></div>
    <div class="card flat"><div class="eq">${ninguno
       ? "Cuánto se movió cada uno" : "Quién cambió más"}</div>
     <div class="lista">`+p.lista.map((j,i)=>
      `<div class="item ${i===0?"on":""}" data-jug="${j.id}">
       <div class="it-tx"><div class="it-nom">${esc(j.nombre)}${
         j.cambio?` <span style="color:var(--a1)">&#9679;</span>`:""}</div>
        <div class="it-sub">${j.cambio
          ? "cambió de forma detectable · clic para sus mapas"
          : "clic para ver sus mapas"}</div></div>
       <div class="it-bar"><i data-w="${(j.exceso/vm*100).toFixed(1)}"
        style="background:${j.cambio?"var(--a1)":"var(--riv)"}"></i></div>
       <div class="it-val">${j.exceso.toFixed(3)}</div></div>`).join("")+
     `</div><div class="nota">El número es cuánto se movió el patrón de juego de
      ese futbolista, <b>descontando</b> lo que ya se movería solo por azar.
      ${ninguno
       ? `<b>Ninguno supera ese umbral aquí</b>, así que este orden es solo
          descriptivo: no dice que el primero cambiara y el último no. Lo que
          dice el conjunto es que, con estos partidos, no detectamos que ningún
          futbolista cambiara su patrón al cambiar de técnico. Puedes abrir
          cualquiera y comprobarlo: sus dos mapas se parecen.`
       : `El punto marca a los que cruzan el umbral tras corregir por mirar a
          todos a la vez; los demás salen para que se vea dónde está la
          frontera.`}
      Toca un nombre para ver sus dos mapas.</div></div></div>`;
  }
 } else h+=vacio("el control de plantel",
   `python scripts/11_confusion_plantel.py --a "${dt}" --b "${rv}" --club "${eq}" --indir ${dir}`);
 $("s2").innerHTML=h;
 jugSel=null;pintaMapas();

 /* ---- 04 el matiz ---- */
 h=cab("04 &middot; el matiz","Durar no es hacer daño",
  `Durar mucho con el balón y hacer daño no son lo mismo. Cada punto es un
   técnico: a la derecha, los que alargan las posesiones; arriba, los que rematan
   más. Un técnico puede estar arriba sin estar a la derecha, y ninguna de las
   cuatro esquinas es mejor que otra.`);
 if(pts.length>1){
  /* La grafica va a ancho completo: encogida a un tercio, las etiquetas de los
     ejes quedaban por debajo de 9 px reales. La lectura se movio abajo. */
  h+=`<div class="card" style="padding:1.5rem 1.7rem">${cuadrante(pts,dt,rv,c.ref_rivales)}
   ${c.ref_rivales&&c.ref_rivales.rem!=null?leyenda(
     SW(C_FOCO,"el técnico que analizas"),SW(C_RIV,"los demás del club"),
     `<span class="leg"><i style="background:none;box-shadow:inset 0 0 0 2px ${C_RIV}"></i>los rivales enfrentados</span>`)
    +`<div class="nota"><b>Sobre la referencia de los rivales.</b> Son
      ${c.ref_rivales.np.toLocaleString("es-MX")} posesiones de los
      ${c.ref_rivales.equipos||17} equipos que jugaron contra ${esc(n)} en esta
      ventana. <b>No es el promedio de la Liga MX</b>, y la diferencia importa:
      cada una de esas posesiones se jugó <em>contra</em> ${esc(n)}, así que la
      cifra habla también de cómo juega él. Si el club aprieta mucho, las
      posesiones rivales salen cortas por eso, no porque esos equipos jueguen
      corto en general. Sirve como punto de referencia, no como retrato de la
      liga.</div>`
    +(pts.every(p=>p.et>c.ref_rivales.et)
      ? `<div class="nota"><b>Y dice algo.</b> Los
         ${c.ref_rivales.equipos||17} rivales promedian
         <b>${c.ref_rivales.et.toFixed(2)}</b> acciones por posesión, y
         <b>los ${pts.length} técnicos de ${esc(n)} están por encima</b> — el que
         menos retiene, ${pts.reduce((a,b)=>a.et<b.et?a:b).et.toFixed(2)}. Por eso
         la referencia queda fuera del gráfico, marcada en el margen: no cabe en
         el rango que abarcan los técnicos.</div>`
      : "")
    :""}</div>
   <div class="grid duo" style="margin-top:1rem;align-items:stretch">
    ${refCuadrantes(pts,n)}
    <div class="card flat"><div class="eq">Muestra por técnico</div>
     ${listaMuestra(pts,dt,rv)}
     <div class="nota">La barra es cuántas posesiones hay detrás de cada técnico.
      Una barra corta significa pocos partidos y, por tanto, más incertidumbre en
      su punto. Toca un nombre para analizarlo.</div></div></div>
   <div class="pie">Cada punto es un técnico del ${n}. Ninguna posición es
   mejor que otra: la gráfica separa <em>durar</em> de <em>hacer daño</em>, que
   son dos dimensiones distintas del estilo.</div>`;
 }
 $("s3").innerHTML=h;

 /* ---- 05 sin balon ---- */
 $("s4").innerHTML=seccionDefensa(c,dt,rv,n,dir,eq);

 /* ---------- 06 · pruébalo tú ---------- */


 conecta();
 animaTodo();
}

/* ---- mapas del jugador seleccionado ---- */
let jugSel=null;
function pintaMapas(){
 const cont=$("mapas"),cd=$("delta");if(!cont||!cd)return;
 const c=DATOS.clubes[$("selClub").value];
 const dt=$("selDT").value,rv=$("selRival").value;
 const par=c.pares[dt+"|"+rv];
 const limpia=()=>{cont.innerHTML="";cd.innerHTML="";};
 if(!par||!par.plantel||!par.plantel.lista.length)return limpia();
 if(jugSel===null)jugSel=String(par.plantel.lista[0].id);
 const j=c.jugadores[jugSel];
 if(!j)return limpia();
 /* fila 1: las dos etapas del mismo futbolista, lado a lado.
    ESCALA COMPARTIDA: el maximo es el de los dos mapas juntos. Con cada uno
    normalizado a su propio maximo, un jugador que concentro el 30% en una zona
    y otro que concentro el 12% se pintaban con el mismo amarillo. */
 const vmaxJ=Math.max(...j.mapas[dt].flat(),...j.mapas[rv].flat(),1e-9);
 /* El foco va SIEMPRE a la izquierda, aunque sea el segundo en el tiempo: la
    vista compara de izquierda a derecha y el foco es el sujeto de la frase. */
 cont.innerHTML=`<div class="card" style="padding:1.4rem">
  <div style="display:flex;align-items:baseline;gap:.7rem;flex-wrap:wrap;
   margin-bottom:.4rem">
   <span style="font-size:1.15rem;font-weight:700;letter-spacing:-.02em">${esc(j.nombre)}</span>
   <span style="font-size:.88rem;font-weight:400;color:var(--tx2)">el mismo
   futbolista, con un técnico y con el otro</span></div>
  <div class="titular">De cada 100 balones que tocó, cuántos tocó en cada zona.
   <span class="gris">Mismo jugador, mismo campo, distinto reparto: eso es lo que
   cambió el técnico.</span></div>
  <div class="grid par">
   <div class="panel">${cap(C_FOCO,"Con "+ape(dt),"el técnico analizado")}
    ${mapaSVG(j.mapas[dt],C_FOCO,"con "+ape(dt),vmaxJ)}</div>
   <div class="panel">${cap(C_RIV,"Con "+ape(rv),"la comparación")}
    ${mapaSVG(j.mapas[rv],C_RIV,"con "+ape(rv),vmaxJ)}</div>
  </div>
  ${leyenda(rampa(C_FOCO,"pocos balones","muchos"),
   "Los dos mapas comparten escala: el mismo tono significa el mismo porcentaje en los dos.")}
  </div>`;
 /* fila 2: la resta de los dos mapas */
 cd.innerHTML=`<div class="card" style="padding:1.4rem">
  <div class="eq">La diferencia, en un solo mapa</div>
  <div class="titular">Dos mapas obligan a comparar de memoria. Este ya está
   restado: <b>enseña dónde ganó presencia</b> <span class="gris">y dónde la
   perdió.</span></div>
  ${mapaDelta(j.mapas[dt],j.mapas[rv],dt,rv)}
  ${leyenda(SW(C_FOCO,"tocó más el balón ahí con "+esc(ape(dt))),
   SW(C_NEG,"lo tocaba más con "+esc(ape(rv))))}
  <div class="nota">Los números son <span class="term" data-tip="<b>Punto porcentual (pp)</b>La resta directa entre dos porcentajes. Pasar del 8% al 12% son 4 puntos, no un 4% de aumento.">puntos porcentuales</span>:
   la resta directa entre los dos mapas de arriba.</div></div>`;
}

/* ---- interacciones que dependen del HTML recien pintado ---- */
function conecta(){
 /* barra de zona <-> celda de la cancha */
 document.querySelectorAll("[data-zona]").forEach(el=>{
  el.addEventListener("mouseenter",()=>{
   const z=el.dataset.zona;
   document.querySelectorAll("#s1 .celda[data-zona]").forEach(cl=>
    cl.classList.toggle("dim",cl.dataset.zona!==z));});
  el.addEventListener("mouseleave",()=>{
   document.querySelectorAll("#s1 .celda").forEach(cl=>cl.classList.remove("dim"));});
 });
 /* clic en un punto o en la lista -> ese tecnico pasa a ser el foco */
 document.querySelectorAll("[data-dt]").forEach(el=>{
  el.style.cursor="pointer";
  el.addEventListener("click",()=>{
   const v=el.dataset.dt;if(v===$("selDT").value)return;
   $("selDT").value=v;cambiaDT();});});
 /* clic en un jugador */
 document.querySelectorAll("[data-jug]").forEach(el=>{
  el.addEventListener("click",()=>{
   jugSel=el.dataset.jug;
   document.querySelectorAll("[data-jug]").forEach(o=>o.classList.remove("on"));
   el.classList.add("on");pintaMapas();});});
}

/* ================= selectores ================= */
function pintaSel(){
 const clubes=Object.keys(DATOS.clubes),seg=$("segClub");
 seg.innerHTML=`<div class="pill"></div>`+clubes.map(c=>
  `<button data-club="${esc(c)}">${esc(c)}</button>`).join("");
 seg.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{
  $("selClub").value=b.dataset.club;cambiaClub();}));
 /* select oculto: mantiene el estado en un solo sitio y el segmentado solo lo
    refleja. Antes el club vivia en el DOM del boton y era facil desincronizar. */
 const s=document.createElement("select");s.id="selClub";s.style.display="none";
 s.innerHTML=clubes.map(c=>`<option>${esc(c)}</option>`).join("");
 seg.parentNode.appendChild(s);
 cambiaClub();
 /* si el navegador no trae IntersectionObserver, las secciones se muestran
    igual: nunca deben quedarse invisibles por un detalle de animacion. */
 if(typeof IntersectionObserver==="function"){
  const io=new IntersectionObserver(es=>es.forEach(e=>{
   if(e.isIntersecting)e.target.classList.add("on");}),{threshold:.08});
  document.querySelectorAll(".rev").forEach(s=>io.observe(s));
 } else document.querySelectorAll(".rev").forEach(s=>s.classList.add("on"));
}
function pintaPill(){
 const seg=$("segClub"),act=$("selClub").value;
 const b=[...seg.querySelectorAll("button")].find(x=>x.dataset.club===act);
 seg.querySelectorAll("button").forEach(x=>x.classList.toggle("on",x===b));
 if(b){const p=seg.querySelector(".pill");
  p.style.left=b.offsetLeft+"px";p.style.width=b.offsetWidth+"px";}
}
function cambiaClub(){
 const n=$("selClub").value,c=DATOS.clubes[n],t=TEMA[n]||TEMA["Cruz Azul"];
 const R=document.documentElement.style;
 R.setProperty("--a1",t.a1);R.setProperty("--a2",t.a2);
 $("aura").style.background=
  `radial-gradient(1200px 700px at 8% -12%,${t.aura} 0%,transparent 62%),
   radial-gradient(900px 560px at 96% 4%,${t.aura2} 0%,transparent 58%)`;
 $("kick").textContent=n+" · "+c.entrenadores.length+" etapas";
 pintaPill();
 $("selDT").innerHTML=c.entrenadores.map(d=>`<option>${esc(d)}</option>`).join("");
 cambiaDT();
}
/* Las opciones de «frente a», en UN SOLO SITIO. Estaban duplicadas en
   `cambiaDT` y en `swap`, y al añadir «el club, sin el» a la primera, la
   segunda lo borraba al intercambiar. Es el bug #2 del proyecto: dos recetas
   para lo mismo que divergen en silencio.

   El club va al FINAL: si fuera la primera opcion el reporte abriria en modo
   club y las secciones de pareja saldrian con su aviso, que es justo lo que no
   debe ver quien llega. */
function opcionesRival(c,excluye){
 $("selRival").innerHTML=c.entrenadores.filter(d=>d!==excluye)
  .map(d=>`<option>${esc(d)}</option>`).join("")+
  `<option value="__CLUB__">&mdash; el club, sin él &mdash;</option>`;
}

function cambiaDT(){
 const c=DATOS.clubes[$("selClub").value],dt=$("selDT").value;
 const prev=$("selRival").value;
 /* «El club sin el» entra al selector de arriba, no solo al tablero: es una
    comparacion de primer nivel. Se etiqueta "sin el" y no "el club" porque
    `12_API_STATSBOMB.md` §6 advierte que la base del club CONTIENE al foco. */
 opcionesRival(c,dt);
 if(prev==="__CLUB__") $("selRival").value="__CLUB__";
 else if(prev&&prev!==dt&&c.entrenadores.includes(prev))$("selRival").value=prev;
 render();
}
$("selDT").onchange=cambiaDT;
$("selRival").onchange=render;
$("swap").onclick=()=>{
 const a=$("selDT").value,b=$("selRival").value;
 if(b==="__CLUB__") return;          // no se puede invertir "el club, sin el"
 $("selDT").value=b;
 const c=DATOS.clubes[$("selClub").value];
 opcionesRival(c,b);
 $("selRival").value=a;render();};
window.addEventListener("resize",pintaPill);
/* El boton de la barra devuelve a la guia: en una pagina larga, quien se pierde
   en la seccion 5 no va a subir a buscarla. */
$("btnGuia").onclick=()=>{
 const g=$("guia");g.open=true;
 g.scrollIntoView({behavior:"smooth",block:"start"});};
pintaSel();
</script></body></html>"""

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reporte.html")
    args = ap.parse_args()

    datos = recolecta()
    if not datos["clubes"]:
        sys.exit("Sin datos. Corre `dtdecoder phase0` y `bash scripts/generar_todo.sh`.")

    salida = Path(args.out)
    salida.write_text(
        HTML.replace("__DATOS__", json.dumps(datos, ensure_ascii=False)),
        encoding="utf-8")
    kb = salida.stat().st_size / 1024
    print(f"\nescrito: {salida.resolve()}  ({kb:.0f} KB)")
    print("Abrelo con doble clic. No necesita servidor ni conexion.")


if __name__ == "__main__":
    main()
