#!/usr/bin/env python3
"""
20_nivel_y_calibracion.py — cierra el bloque de presion con tres contrastes.

POR QUE ESTE SCRIPT EXISTE
--------------------------
La pendiente de pi contra k resulto ser el estimando equivocado. Con kmin=2,
Anselmi y Reynoso decaen a ritmo parecido (-0.0060 vs -0.0102, p=0.077): lo que
las figuras muestran NO es una diferencia de tasa de decaimiento sino de NIVEL
mantenido. Desde k=3 la curva de Anselmi va 3-7 puntos por encima en nueve
puntos consecutivos.

Un contraste de pendiente no puede detectar eso: dos rectas paralelas
desplazadas tienen la misma pendiente. Hay que contrastar el nivel.

TRES CONTRASTES
---------------
1. NIVEL en k >= k0. El estimando que corresponde a lo que se ve.
2. L = 1 POR FASE. Jardine presiona +5.4 pp en posesiones rivales de una sola
   accion, la mayor diferencia de la tabla de Kitagawa. Pero muchas posesiones
   de una accion son despejes y saques: nacen de balon parado y mueren sin
   disputa. Separar juego abierto de reinicio decide si el efecto es real.
3. CALIBRACION. ¿La presion SIRVE? Todo el bloque mide si un DT presiona mas,
   sin haber comprobado nunca que presionar reduzca el peligro. Si pi no
   cambia nada, el analisis describe un comportamiento sin consecuencia.

LA LIMITACION QUE NO SE VA
--------------------------
El contraste de nivel en k >= k0 CONDICIONA a que la posesion haya sobrevivido
hasta k0. Si la presion provoca perdidas, las posesiones muy presionadas no
llegan, y pi(k) alto se estima sobre las que escaparon. Es censura dependiente
del tratamiento, el mismo esqueleto del bug #11.

Cambiar de estadistico no lo arregla. El marco que si lo trata es el de riesgos
competitivos (Kaplan-Meier para la supervivencia de la posesion rival, Cox para
el efecto del DT sobre la intensidad), que es D2 del plan. Este script reporta
el contraste con la limitacion DECLARADA; no la resuelve.

Uso:
  python scripts/20_nivel_y_calibracion.py --club "Cruz Azul" \
      --a "Martin Anselmi" --b "Juan Reynoso"
  python scripts/20_nivel_y_calibracion.py --club "América" \
      --a "Andre Jardine" --b "Santiago Solari" --k0 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12
ABIERTO = ("open", "transition")     # juego abierto
PARADO = ("restart", "set_piece")    # reinicio / balon parado


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=tuple(cfg["phase_order"]))


def preparar(trans: pl.DataFrame, club: str, sp: StateSpace) -> pl.DataFrame:
    """Acciones rivales con k, fase, zona (marco del club) y desenlace."""
    for c in ("coach_faced", "under_pressure"):
        if c not in trans.columns:
            sys.exit(f"Falta `{c}`. Corre phase0 con --club tras el parche D0.")

    sub = (trans.filter((pl.col("team") != club)
                        & pl.col("coach_faced").is_not_null())
                .sort(["poss_uid", "event_index"]))

    goal = sp.absorbing_index("GOAL")
    shot = sp.absorbing_index("SHOT_NOGOAL")
    n_ph = len(sp.phases)

    sub = sub.with_columns(
        pl.col("coach_faced").alias("era"),
        # `L` cuenta acciones REALES: la fila TERMINAL es artificial.
        (pl.col("action_type") != "TERMINAL").alias("real"),
        pl.col("to_state").is_in([goal, shot]).alias("acaba_en_remate"),
        (pl.col("to_state") == goal).alias("acaba_en_gol"),
        pl.col("to_state").ge(sp.n_transient).alias("absorbe"),
    )
    z = sp.mirror_zone(sub["from_state"].to_numpy().astype(int) // n_ph)
    sub = sub.with_columns(pl.Series("zona", z, dtype=pl.Int32))

    reales = sub.filter(pl.col("real")).with_columns(
        (pl.int_range(pl.len()).over("poss_uid") + 1).alias("k"),
        pl.col("under_pressure").fill_null(False).cast(pl.Int8).alias("presion"),
    )
    # L y desenlace de la posesion, propagados a cada accion
    resumen = sub.group_by("poss_uid").agg(
        pl.col("real").sum().alias("L"),
        pl.col("acaba_en_remate").any().alias("poss_remate"),
        pl.col("acaba_en_gol").any().alias("poss_gol"),
    )
    return reales.join(resumen, on="poss_uid", how="left")


# --------------------------------------------------------------------------
# Permutacion por partido: motor comun de los tres contrastes
# --------------------------------------------------------------------------
def permutar(df: pl.DataFrame, a: str, b: str, fn, n_perm: int, seed: int):
    """fn(mascara_a, mascara_b) -> escalar. Permuta la etiqueta ENTRE PARTIDOS.

    `coach_faced` es propiedad del partido. Permutar acciones destruiria la
    correlacion intra-partido y daria una nula demasiado angosta: se detectaria
    estilo donde solo hay agrupamiento.
    """
    part = df.group_by("match_id").agg(pl.col("era").first())
    mid = part["match_id"].to_numpy(); e0 = part["era"].to_numpy()
    pos = {m: i for i, m in enumerate(mid)}
    ii = np.array([pos[m] for m in df["match_id"].to_numpy()])

    es_a = (e0[ii] == a)
    obs = fn(es_a, ~es_a)
    rng = np.random.default_rng(seed)
    nulo = np.empty(n_perm)
    for t in range(n_perm):
        e = rng.permutation(e0)[ii]
        m = (e == a)
        nulo[t] = fn(m, ~m)
    p = float((1.0 + (np.abs(nulo) >= abs(obs)).sum()) / (1.0 + n_perm))
    return float(obs), p, nulo


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--indir", default=None)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--k0", type=int, default=3,
                    help="primer indice del contraste de nivel")
    ap.add_argument("--n-perm", type=int, default=2000, dest="n_perm")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config.load(args.config)
    sp = _space(cfg)
    indir = args.indir or ("data/processed" if args.club == "América"
                           else "data/processed_cruzazul")
    trans = pl.read_parquet(Path(indir) / "transitions.parquet")
    df = preparar(trans, args.club, sp)
    df = df.filter(pl.col("era").is_in([args.a, args.b]))
    if df.height == 0:
        sys.exit(f"Sin datos para {args.a!r} / {args.b!r}.")
    seed = int(cfg["inference"]["boot_seed"])
    res: dict = {"club": args.club, "era_a": args.a, "era_b": args.b, "k0": args.k0,
                 "n_perm": args.n_perm,
                 "familia_fdr": "pi_e(z) — ADR-47, corregir al final"}

    # ================================================================== 1
    print("=" * 88)
    print(f" 1. NIVEL DE PRESION EN k >= {args.k0}")
    print("=" * 88)
    print("  Las dos curvas decaen a ritmo parecido; lo que difiere es el NIVEL.")
    print("  Una pendiente no puede detectar dos rectas paralelas desplazadas.\n")

    d1 = df.filter(pl.col("k") >= args.k0)
    p_arr = d1["presion"].to_numpy().astype(float)

    def nivel(ma, mb):
        return (p_arr[ma].mean() if ma.any() else np.nan) - \
               (p_arr[mb].mean() if mb.any() else np.nan)

    obs1, p1, _ = permutar(d1, args.a, args.b, nivel, args.n_perm, seed)
    na = d1.filter(pl.col("era") == args.a).height
    nb = d1.filter(pl.col("era") == args.b).height
    pa = float(d1.filter(pl.col("era") == args.a)["presion"].mean())
    pb = float(d1.filter(pl.col("era") == args.b)["presion"].mean())
    print(f"  {args.a:<22} pi = {pa:.4f}   ({na:,} acciones)")
    print(f"  {args.b:<22} pi = {pb:.4f}   ({nb:,} acciones)")
    print(f"  diferencia de nivel = {obs1:+.4f}   p = {p1:.4f}")
    print(f"\n  [!] Este contraste CONDICIONA a que la posesion llegara a k={args.k0}.")
    print("      Si la presion provoca perdidas, las mas presionadas no llegan.")
    print("      Censura dependiente del tratamiento: declarada, no resuelta.")
    res["nivel"] = {"pi_a": pa, "pi_b": pb, "diff": obs1, "p": p1,
                    "n_a": na, "n_b": nb,
                    "caveat": "condicionado a supervivencia hasta k0"}

    # ================================================================== 2
    print("\n" + "=" * 88)
    print(" 2. POSESIONES DE UNA SOLA ACCION, SEPARADAS POR FASE")
    print("=" * 88)
    print("  Muchas posesiones rivales de una accion son despejes y saques:")
    print("  nacen de balon parado y mueren sin disputa. Mezclarlas con juego")
    print("  abierto confunde 'presiona y roba' con 'el rival despejo'.\n")

    res["L1"] = {}
    for etiqueta, fases in (("juego abierto", ABIERTO), ("balon parado", PARADO)):
        d2 = df.filter((pl.col("L") == 1) & pl.col("phase").is_in(list(fases)))
        if d2.height < 100:
            print(f"  {etiqueta:<14} muestra insuficiente ({d2.height})")
            continue
        pr = d2["presion"].to_numpy().astype(float)

        def nivel2(ma, mb, pr=pr):
            return (pr[ma].mean() if ma.any() else np.nan) - \
                   (pr[mb].mean() if mb.any() else np.nan)

        o, p, _ = permutar(d2, args.a, args.b, nivel2, args.n_perm, seed)
        aa = d2.filter(pl.col("era") == args.a)
        bb = d2.filter(pl.col("era") == args.b)
        print(f"  {etiqueta:<14} {args.a[:18]:<19} pi={float(aa['presion'].mean()):.4f} "
              f"({aa.height:,})")
        print(f"  {'':<14} {args.b[:18]:<19} pi={float(bb['presion'].mean()):.4f} "
              f"({bb.height:,})")
        print(f"  {'':<14} diferencia = {o:+.4f}   p = {p:.4f}\n")
        res["L1"][etiqueta] = {"pi_a": float(aa["presion"].mean()),
                               "pi_b": float(bb["presion"].mean()),
                               "diff": o, "p": p,
                               "n_a": aa.height, "n_b": bb.height}

    # ================================================================== 3
    print("=" * 88)
    print(" 3. CALIBRACION: ¿LA PRESION SIRVE?")
    print("=" * 88)
    print("  Todo lo anterior mide si un DT presiona mas. Nada comprueba que")
    print("  presionar reduzca el peligro. Si pi no cambia nada, el bloque")
    print("  describe un comportamiento sin consecuencia.\n")
    print("  Se compara, DENTRO de cada zona y era, el desenlace de las acciones")
    print("  presionadas contra las no presionadas, y se agrega estandarizando")
    print("  por zona -- misma tecnica que ADR-44, aqui sobre la exposicion.\n")

    res["calibracion"] = {}
    for era in (args.a, args.b):
        d3 = df.filter(pl.col("era") == era)
        g = d3.group_by(["zona", "presion"]).agg(
            pl.col("absorbe").mean().alias("perdida"),
            pl.col("poss_remate").mean().alias("remate"),
            pl.col("poss_gol").mean().alias("gol"),
            pl.len().alias("n"))
        tab = {(r["zona"], r["presion"]): r for r in g.to_dicts()}
        zonas = sorted({z for z, _ in tab})
        out = {}
        for campo in ("perdida", "remate", "gol"):
            num = den = 0.0
            for z in zonas:
                r1, r0 = tab.get((z, 1)), tab.get((z, 0))
                if not r1 or not r0 or r1["n"] < 30 or r0["n"] < 30:
                    continue
                w = r1["n"] + r0["n"]          # peso = exposicion de la zona
                num += w * (r1[campo] - r0[campo]); den += w
            out[campo] = num / max(den, _EPS)
        print(f"  {era:<22} presionada menos no presionada, estandarizado por zona:")
        print(f"    P(la accion termina la posesion) {out['perdida']:+.4f}")
        print(f"    P(la posesion acaba en remate)   {out['remate']:+.4f}")
        print(f"    P(la posesion acaba en gol)      {out['gol']:+.4f}")
        res["calibracion"][era] = out

    signos = [res["calibracion"][e]["perdida"] for e in (args.a, args.b)]
    # GUARDA DE MAGNITUD. Un signo positivo de +0.002 no es evidencia de nada:
    # es ruido. El veredicto exige que el efecto sea de un tamano que importe
    # futbolisticamente, no solo que apunte al lado correcto.
    UMBRAL = 0.01
    if all(s > UMBRAL for s in signos):
        print("\n  >> La presion SI aumenta la probabilidad de que la accion")
        print("     termine la posesion, en las dos eras. La etiqueta mide algo")
        print("     con consecuencia futbolistica, no solo una anotacion.")
    elif all(abs(s) <= UMBRAL for s in signos):
        print(f"\n  >> [!] El efecto es menor a {UMBRAL:.2f} en las dos eras: la")
        print("     presion no cambia de forma apreciable el desenlace inmediato.")
        print("     Eso no invalida el analisis, pero cambia lo que se puede")
        print("     afirmar: se describe DONDE y CUANDO presiona cada DT, no que")
        print("     esa presion sea eficaz. Hay que decirlo en el reporte.")
    else:
        print("\n  >> [!] El efecto difiere entre eras. Antes de interpretar")
        print("     cualquier diferencia de pi hay que explicar esto: o la")
        print("     etiqueta no mide lo mismo en las dos, o la presion de un DT")
        print("     funciona y la del otro no. Las dos lecturas son reportables;")
        print("     asumir la primera sin comprobarla, no.")

    print("\n  OJO: es asociacion, no efecto causal. StatsBomb anota presion")
    print("  cuando un defensor se acerca, y se acerca mas cuando el rival esta")
    print("  en problemas. Parte de la asociacion puede ir en esa direccion.")

    out = Path(args.out or f"reports/nivel_calibracion_"
               f"{args.a.lower().replace(' ','')}_{args.b.lower().replace(' ','')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")


if __name__ == "__main__":
    main()
