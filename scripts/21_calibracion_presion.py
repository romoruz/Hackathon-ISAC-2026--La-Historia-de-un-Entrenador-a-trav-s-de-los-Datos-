#!/usr/bin/env python3
"""
21_calibracion_presion.py — ¿la presion SIRVE? (version corregida)

EL BUG DE LA VERSION ANTERIOR
-----------------------------
`20_nivel_y_calibracion.py` definia el desenlace como

    absorbe = to_state >= n_transient

es decir "el to_state de ESTA accion es absorbente". Eso cubre remate, pase
fuera y pase incompleto, pero NO las muertes por acoso: un acarreo seguido de
`Dispossessed` tiene to_state transitorio y la posesion muere en la fila
TERMINAL, que el script excluia.

Medido sobre Cruz Azul: `Dispossessed` (3,407 eventos) y `Clearance` (6,355)
llevan under_pressure = 1.000 EXACTO -- es definicional, no una tasa. Ninguno
esta en `moving_types`, asi que ninguno genera transicion. La calibracion
media, por tanto, la eficacia de la presion CONDICIONADA a que la presion
fracaso en forzar el error tecnico. El signo salia invertido por construccion.

Es la leccion del bug #10: dos decisiones correctas por separado -- marcar la
absorcion por `to_state`, excluir las filas TERMINAL -- que juntas eliminan el
mecanismo que se quiere medir.

LA CORRECCION
-------------
El desenlace correcto es "¿es esta la ULTIMA accion real de la posesion?", o
sea k == L. Captura todas las formas de morir, incluidas las invisibles al
espacio de estados.

POR QUE NO SE TOCA LA CADENA
----------------------------
Se consideraron dos alternativas y se descartaron:

  1. Anadir estados absorbentes nuevos. Cambiaria n_states de 84 a 86,
     reindexaria P, N, B y todos los .npz, invalidaria los tests y obligaria a
     revalidar cobertura, bondad de ajuste y las cifras publicadas. Radio de
     explosion enorme para una pregunta de calibracion.

  2. Recodificarlos como LOSS. Ya esta hecho: `_append_terminal_absorption`
     manda la posesion a LOSS igualmente. La masa de absorcion esta
     contabilizada; lo que se pierde es la CAUSA, no el desenlace.

Y las dos comparten una trampa: `Dispossessed` tiene pi = 1 por definicion. Si
entra al lado de la EXPOSICION, comparar presionadas contra no presionadas es
circular. Aqui entra solo como DESENLACE.

DOS FUENTES DE CONFUSION QUE SE CONTROLAN
-----------------------------------------
  zona          -- la presion y la perdida son ambas mas probables cerca del
                   area propia del rival.
  action_type   -- pi(Carry) = 0.32 frente a pi(Pass) = 0.15, y un acarreo
                   tiene otra probabilidad de morir. Sin estratificar por tipo,
                   la calibracion mide en parte la mezcla de acciones.

Se estandariza por (zona x tipo) con la misma tecnica de ADR-44.

Uso:
  python scripts/21_calibracion_presion.py --club "Cruz Azul" \
      --a "Martin Anselmi" --b "Juan Reynoso"
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


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=tuple(cfg["phase_order"]))


def preparar(trans: pl.DataFrame, club: str, sp: StateSpace) -> pl.DataFrame:
    for c in ("coach_faced", "under_pressure"):
        if c not in trans.columns:
            sys.exit(f"Falta `{c}`. Corre phase0 con --club tras el parche D0.")

    sub = (trans.filter((pl.col("team") != club)
                        & pl.col("coach_faced").is_not_null())
                .sort(["poss_uid", "event_index"]))
    n_ph = len(sp.phases)
    reales = sub.filter(pl.col("action_type") != "TERMINAL").with_columns(
        (pl.int_range(pl.len()).over("poss_uid") + 1).alias("k"),
        pl.col("under_pressure").fill_null(False).cast(pl.Int8).alias("presion"),
        pl.col("coach_faced").alias("era"),
    )
    L = reales.group_by("poss_uid").agg(pl.len().alias("L"))
    reales = reales.join(L, on="poss_uid", how="left")
    z = sp.mirror_zone(reales["from_state"].to_numpy().astype(int) // n_ph)
    return reales.with_columns(
        pl.Series("zona", z, dtype=pl.Int32),
        # EL DESENLACE CORRECTO: ¿muere la posesion aqui, por la causa que sea?
        (pl.col("k") == pl.col("L")).cast(pl.Int8).alias("ultima"),
        # El desenlace ANTERIOR, para poder mostrar la diferencia.
        pl.col("to_state").ge(sp.n_transient).cast(pl.Int8).alias("absorbe_viejo"),
    )


def estandarizar(df: pl.DataFrame, campo: str, min_n: int) -> tuple[float, float]:
    """Diferencia presionada - no presionada, estandarizada por (zona, tipo).

    Pesos = exposicion total del estrato, comunes a los dos brazos. Solo entran
    estratos con al menos `min_n` acciones en CADA brazo: positividad.
    """
    g = df.group_by(["zona", "action_type", "presion"]).agg(
        pl.col(campo).mean().alias("y"), pl.len().alias("n"))
    tab = {(r["zona"], r["action_type"], r["presion"]): r for r in g.to_dicts()}
    claves = {(z, t) for z, t, _ in tab}
    num = den = 0.0
    usados = 0
    for z, t in claves:
        r1, r0 = tab.get((z, t, 1)), tab.get((z, t, 0))
        if not r1 or not r0 or r1["n"] < min_n or r0["n"] < min_n:
            continue
        w = r1["n"] + r0["n"]
        num += w * (r1["y"] - r0["y"]); den += w
        usados += 1
    return (num / max(den, _EPS)), usados


def permutar_presion(df: pl.DataFrame, campo: str, min_n: int,
                     n_perm: int, seed: int) -> float:
    """Nula: permutar la MARCA DE PRESION dentro de cada estrato (zona, tipo).

    Permutar la etiqueta de era no sirve aqui: la pregunta no es si dos DT
    difieren, sino si la presion se asocia al desenlace DENTRO de una era.
    Permutar dentro del estrato preserva exactamente la exposicion y la mezcla
    de acciones, asi que la nula aisla la asociacion presion-desenlace.
    """
    obs, _ = estandarizar(df, campo, min_n)
    z = df["zona"].to_numpy(); t = df["action_type"].to_numpy()
    clave = np.array([f"{a}|{b}" for a, b in zip(z, t)])
    p = df["presion"].to_numpy()
    grupos = {c: np.flatnonzero(clave == c) for c in np.unique(clave)}
    rng = np.random.default_rng(seed)

    nulo = np.empty(n_perm)
    base = df.drop("presion")
    for i in range(n_perm):
        pp = p.copy()
        for _, ix in grupos.items():
            pp[ix] = rng.permutation(pp[ix])
        d = base.with_columns(pl.Series("presion", pp))
        nulo[i], _ = estandarizar(d, campo, min_n)
    return float((1.0 + (np.abs(nulo) >= abs(obs)).sum()) / (1.0 + n_perm))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--indir", default=None)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--min-n", type=int, default=25, dest="min_n")
    ap.add_argument("--n-perm", type=int, default=500, dest="n_perm")
    ap.add_argument("--k0", type=int, default=3,
                    help="calibracion restringida a k >= k0 (0 = sin restringir)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config.load(args.config)
    sp = _space(cfg)
    indir = args.indir or ("data/processed" if args.club == "América"
                           else "data/processed_cruzazul")
    df = preparar(pl.read_parquet(Path(indir) / "transitions.parquet"),
                  args.club, sp)
    df = df.filter(pl.col("era").is_in([args.a, args.b]))
    if df.height == 0:
        sys.exit(f"Sin datos para {args.a!r} / {args.b!r}.")
    seed = int(cfg["inference"]["boot_seed"])

    print("=" * 90)
    print(" CALIBRACION: ¿una accion presionada muere antes?")
    print("=" * 90)
    print("  Desenlace = 'es la ULTIMA accion real de la posesion'.")
    print("  Captura las muertes por acoso (Dispossessed, Miscontrol) que el")
    print("  espacio de estados no ve. Estandarizado por (zona x tipo de accion).\n")

    res = {"club": args.club, "era_a": args.a, "era_b": args.b,
           "definicion_desenlace": "k == L (ultima accion real de la posesion)",
           "estratos": "zona x action_type", "min_n": args.min_n,
           "familia_fdr": "pi_e(z) — ADR-47", "eras": {}}

    print(f"  {'era':<22} {'desenlace CORREGIDO':>22} {'p':>8} "
          f"{'(desenlace viejo)':>20} {'estratos':>9}")
    print("  " + "-" * 86)
    for era in (args.a, args.b):
        d = df.filter(pl.col("era") == era)
        nuevo, us = estandarizar(d, "ultima", args.min_n)
        viejo, _ = estandarizar(d, "absorbe_viejo", args.min_n)
        p = permutar_presion(d, "ultima", args.min_n, args.n_perm, seed)
        print(f"  {era:<22} {nuevo:+22.4f} {p:>8.4f} {viejo:+20.4f} {us:>9}")
        res["eras"][era] = {"efecto_corregido": nuevo, "p": p,
                            "efecto_definicion_vieja": viejo,
                            "n_estratos": us, "n_acciones": d.height}

    vals = [res["eras"][e]["efecto_corregido"] for e in (args.a, args.b)]
    ps = [res["eras"][e]["p"] for e in (args.a, args.b)]
    print("\n  El 'desenlace viejo' es el que daba signo invertido: solo contaba")
    print("  remate, pase fuera y pase incompleto, nunca la perdida por acoso.")

    if all(v > 0.01 for v in vals) and all(pp <= 0.05 for pp in ps):
        print("\n  >> LA PRESION SIRVE, en las dos eras. Una accion rival")
        print("     presionada tiene mas probabilidad de ser la ultima de su")
        print("     posesion, a igualdad de zona y de tipo de accion.")
        print("     Con esto el bloque defensivo pasa de DESCRIBIR a EVALUAR.")
    elif all(abs(v) <= 0.01 for v in vals):
        print("\n  >> Sin efecto apreciable. El bloque describe DONDE y CUANDO")
        print("     presiona cada DT, no que esa presion sea eficaz. El verbo de")
        print("     cada frase del reporte tiene que ser descriptivo.")
    else:
        print("\n  >> Resultado mixto. Reportar por era, sin generalizar.")

    # --- restringido a k >= k0, que es donde vive el titular de Anselmi ----
    if args.k0 > 0:
        print("\n" + "=" * 90)
        print(f" LA MISMA PREGUNTA, RESTRINGIDA A k >= {args.k0}")
        print("=" * 90)
        print("  Es el tramo donde vive el titular de Anselmi. Si la presion")
        print("  sostenida no mata posesiones, 'sostiene la presion' describe un")
        print("  esfuerzo sin consecuencia.\n")
        print(f"  [!] CENSURA: condiciona a que la posesion llegara a k={args.k0}.")
        print("      Si la presion mata pronto, las mas presionadas no llegan, y")
        print("      el efecto medido aqui esta ATENUADO hacia cero. El marco que")
        print("      lo trata es riesgos competitivos (D2), no este contraste.\n")
        res["k0"] = args.k0
        res["eras_k0"] = {}
        for era in (args.a, args.b):
            d = df.filter((pl.col("era") == era) & (pl.col("k") >= args.k0))
            v, us = estandarizar(d, "ultima", args.min_n)
            p = permutar_presion(d, "ultima", args.min_n, args.n_perm, seed)
            print(f"  {era:<22} {v:+.4f}   p = {p:.4f}   ({us} estratos, "
                  f"{d.height:,} acciones)")
            res["eras_k0"][era] = {"efecto": v, "p": p, "n_estratos": us}

    print("\n  OJO: ES ASOCIACION, NO EFECTO CAUSAL.")
    print("  StatsBomb anota presion cuando un defensor se acerca, y se acerca")
    print("  mas cuando el rival ya esta en problemas. Parte de lo que se mide")
    print("  puede ir en esa direccion. El diseno no la separa.")

    out = Path(args.out or f"reports/calibracion_"
               f"{args.a.lower().replace(' ','')}_{args.b.lower().replace(' ','')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")


if __name__ == "__main__":
    main()
