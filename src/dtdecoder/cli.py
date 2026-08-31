"""CLI: `dtdecoder <comando>`. Cada comando es una fase del plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import polars as pl

from . import eras as eras_mod
from . import ingest, plots
from .absorbing import AbsorbingChain, empirical_start_distribution
from .config import Config
from .estimate import count_matrix, cv_lambda, error_curve, shrink, sparsity_report
from .grid import StateSpace
from .inference import bootstrap_diff, context_contrast, tactical_fingerprint
from .possessions import build_transitions, coordinate_sanity
from .synth import synth_events

pl.Config.set_tbl_rows(30)
pl.Config.set_tbl_width_chars(160)


def _dtdecoder_version() -> str | None:
    """Version del paquete, con import LOCAL.

    A nivel de modulo, `from . import __version__` arriesga un ciclo de
    importacion: __init__.py puede importar cli. Dentro de la funcion el
    ciclo ya esta resuelto cuando esto corre.
    """
    try:
        from . import __version__
        return __version__
    except Exception:
        try:
            from importlib.metadata import version
            return version("dtdecoder")
        except Exception:
            return None


DEFAULT_CONFIG = "config/default.yaml"


def _provenance(config_path: str | None = None) -> dict:
    """Hash del config + commit de git, para cada reporte.

    POR QUE EXISTE ESTO
    -------------------
    Sin procedencia, una figura o un JSON no es trazable a los parametros que
    lo produjeron. Ya paso en este proyecto: una `cv_lambda.png` generada en
    v0.3 (rejilla hasta 500, lambda*=50) sobrevivio al arreglo de la fuga de
    prior y siguio en `figures/` diciendo un numero que ningun resultado
    posterior respaldaba. Una diapositiva con esa figura habria presentado un
    valor falso sin que nada avisara.

    Es la mejora recomendada en 08_REPRODUCIBILITY.md §9.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or None
    except Exception:
        commit = None
    # Los subparsers de fase no definen --config: `Config.load(None)` cae al
    # default, asi que aqui hay que hacer lo mismo o el hash apunta a nada.
    path = config_path or DEFAULT_CONFIG
    try:
        cfg_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    except (OSError, TypeError, ValueError):
        cfg_hash = None
    return {
        "config_sha256": cfg_hash,
        "config_path": str(path),
        "git_commit": commit,
        "dtdecoder_version": _dtdecoder_version(),
    }


def _abort(msg: str) -> int:
    print(f"[error] {msg}", file=sys.stderr)
    return 1


def _check_matrices_identity(mats, args) -> str | None:
    """Verifica que P_matrices.npz corresponde a la unidad pedida.

    EL BUG QUE ESTO CIERRA
    ----------------------
    `phase2` y `phase3` leen la matriz de transicion del .npz que dejo la
    ULTIMA corrida de phase1, pero reciben --unit/--value propios y los usan
    para rotular figuras y reportes. Corriendo

        dtdecoder phase1 --value "Fernando Ortiz"
        dtdecoder phase2 --value "Andre Jardine"

    se modelaba a ORTIZ y se rotulaba "Andre Jardine", sin ningun aviso.
    Salieron figuras con el nombre equivocado impreso encima y un
    expected_length_mean 5% distinto que parecia ruido numerico.

    Es el patron de riesgo dominante del proyecto (05_VALIDATION §1): no
    falla, miente.

    Devuelve None si todo cuadra, o el mensaje de error.
    """
    campos = (
        ("unit", args.unit),
        ("value", args.value),
        # `perspective` entra al contrato desde este parche. Sin ella:
        #     phase1 --unit coach_faced --value X --perspective defense
        #     phase2 --unit coach_faced --value X          (default: attack)
        # `unit` coincide, `value` coincide, el guardarrail PASA, y phase2
        # calcula la cadena ofensiva rotulando las figuras como defensivas.
        # Es el bug #7 exacto, con el campo que faltaba.
        ("perspective", getattr(args, "perspective", "attack")),
    )
    for campo, esperado in campos:
        if campo not in mats:
            return (
                f"P_matrices.npz no declara '{campo}': lo genero una version "
                "anterior de phase1. Vuelve a correr phase1."
            )
        hallado = str(mats[campo])
        if hallado != esperado:
            return (
                f"P_matrices.npz es de {campo}='{hallado}' pero se pidio "
                f"'{esperado}'.\n"
                f"  Corre primero: dtdecoder phase1 --unit {args.unit} "
                f"--value '{args.value}' --baseline {args.baseline} "
                f"--perspective {getattr(args, 'perspective', 'attack')}\n"
                "  Sin esta verificacion se modela una unidad y se rotulan "
                "las figuras con otra, en silencio."
            )
    return None


def _space(cfg: Config) -> StateSpace:
    """El espacio de estados se deriva del config, incluidas las fases.

    Las fases salen de `config.phase_order`, no del orden de las llaves de
    `config.phases`: ese orden fija los indices del espacio de estados y por
    tanto el layout de P, N, B y de todo lo que se guarde en disco.
    """
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def _read_trans(indir: str) -> pl.DataFrame:
    """Lee transitions.parquet, con respaldo al directorio padre.

    La conjugada escribe sus artefactos en un subdirectorio
    (data/processed/def) para no pisar el P_matrices.npz ofensivo, pero
    `transitions.parquet` es UNICO y vive en el padre. Sin este respaldo habria
    que duplicarlo, y dos copias que pueden divergir son justo lo que este
    parche evita.
    """
    p = Path(indir) / "transitions.parquet"
    if not p.exists():
        alt = Path(indir).parent / "transitions.parquet"
        if alt.exists():
            p = alt
    if not p.exists():
        raise SystemExit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    return pl.read_parquet(p)


def _apply_perspective(trans: pl.DataFrame, args) -> pl.DataFrame:
    """Selecciona las filas de la perspectiva pedida.

    `transitions.parquet` contiene las posesiones de los 18 equipos: las del
    club (fase con balon) y las de los 17 rivales (fase sin balon, la cadena
    conjugada). La perspectiva es un FILTRO sobre ese artefacto unico.

      attack  -- posesiones del club. Comportamiento historico EXACTO cuando no
                 se pasa --perspective.
      defense -- posesiones de los rivales en los partidos del club. La cadena
                 se estima en el marco NATIVO del rival: StatsBomb normaliza por
                 ejecutante (verificado el 2026-08-24: remates x~103 y saques de
                 meta x~7 en ambos lados). El espejo se aplica al PRESENTAR, con
                 StateSpace.mirror_zone. Reflejar coordenadas aqui rompería
                 `coordinate_sanity` sin que nada estuviera mal.
    """
    persp = getattr(args, "perspective", "attack")
    if persp == "attack":
        return trans
    if persp != "defense":
        raise SystemExit(f"perspective desconocida: {persp!r}")
    if not getattr(args, "club", None):
        raise SystemExit("--perspective defense requiere --club")

    if args.unit == "coach":
        raise SystemExit(
            "En perspectiva defensiva las filas son del RIVAL, y `attach_coach`\n"
            "  deja `coach` en null para todo lo que no sea el club. Con\n"
            "  --unit coach la seleccion saldria VACIA y el error apuntaria al\n"
            "  lugar equivocado.\n"
            "  Usa: --unit coach_faced   (que DT dirigia al club en ese partido)"
        )
    if "coach_faced" not in trans.columns:
        raise SystemExit(
            "transitions.parquet no trae `coach_faced`: lo genero una version\n"
            "  anterior de phase0. Vuelve a correr phase0 con --club."
        )
    out = trans.filter(pl.col("team") != args.club)
    if out.height == 0:
        raise SystemExit(f"Cero transiciones de rivales para club={args.club!r}.")
    return out


def _uniform(space: StateSpace) -> np.ndarray:
    return np.full((space.n_transient, space.n_states), 1.0 / space.n_states)


def _build_prior(
    trans: pl.DataFrame,
    space: StateSpace,
    mode: str = "exclude_focus",
    exclude: pl.DataFrame | None = None,
) -> np.ndarray:
    """Prior empirico `q` para el encogimiento.

    FUGA QUE ESTO CORRIGE
    ---------------------
    Con un archivo centrado en un solo club, ese club puede ser >50% de las
    transiciones. Si el prior se calcula sobre TODO el archivo, el foco se
    encoge hacia un promedio que YA LO CONTIENE. Consecuencias:

      1. La validacion cruzada elige lambda enorme (el prior predice bien los
         datos retenidos porque son suyos) y lambda* se pega al tope de la
         rejilla. Deja de significar "cuantas observaciones para que la
         evidencia del DT domine a la referencia".
      2. En la comparacion DT vs DT, ambas eras se encogen hacia un prior que
         contiene a las dos: el efecto que quieres medir se diluye por
         construccion.

    Modos:
      exclude_focus : prior sobre todo MENOS el foco. Default y el correcto
                      para casi todo.
      pooled        : todo el archivo. Solo para exploracion rapida.
      baseline      : prior = la propia linea base. Encogimiento maximo hacia
                      el comparador; conservador, util como analisis de
                      sensibilidad.

    El prior es `q`, NO la linea base del contraste. El prior estabiliza
    renglones ralos; la linea base define contra quien comparas.
    """
    if mode == "pooled" or exclude is None:
        src = trans
    elif mode in ("exclude_focus", "baseline"):
        src = exclude
    else:
        raise ValueError(f"prior desconocido: {mode}")
    return shrink(count_matrix(src, space), _uniform(space), 1.0)


def _warn_boundary(cv, grid) -> None:
    if cv.lam_star >= max(grid) - 1e-9:
        print(
            f"\n[AVISO] lambda* = {cv.lam_star:g} esta en el TOPE de la rejilla. "
            "La CV quiere mas encogimiento del que le ofreces: extiende "
            "`estimation.lambda_grid` en el config, o revisa si el prior "
            "contiene al foco (usa --prior exclude_focus).",
            file=sys.stderr,
        )
    elif cv.lam_star <= min(grid) + 1e-9 and len(grid) > 1:
        print(
            f"\n[AVISO] lambda* = {cv.lam_star:g} esta en el PISO de la rejilla: "
            "los datos rechazan todo encogimiento. Revisa que el prior sea una "
            "referencia razonable.",
            file=sys.stderr,
        )


# ==========================================================================
def cmd_convert(args) -> int:
    out = ingest.to_parquet(args.src, args.dst, partition_by=args.partition_by)
    print(f"[ok] parquet normalizado -> {out}")
    return 0


def cmd_eras_template(args) -> int:
    p = eras_mod.write_template(args.out)
    print(f"[ok] plantilla de eras -> {p}")
    print("\nVERIFICA las fechas antes de usarlas: son aproximaciones a partir")
    print("de los anos de Wikipedia. Usa `dtdecoder regimes` para validarlas.")
    return 0


def cmd_phase0(args) -> int:
    cfg = Config.load(args.config)
    space = _space(cfg)
    trans = build_transitions(
        ingest.load(args.src), space, cfg.raw, team=None, club=args.club
    )
    if trans.height == 0:
        raise SystemExit("Cero transiciones. Revisa el esquema del archivo fuente.")

    coach_info: dict = {"attached": False}
    if args.eras and args.match_dates:
        if not args.club:
            raise SystemExit("--club es obligatorio cuando pasas --eras")
        eras = eras_mod.load_eras(args.eras)
        md = eras_mod.load_match_dates(args.match_dates)
        mc = eras_mod.match_coach_table(md, eras, args.club)
        trans = eras_mod.attach_coach(trans, mc, args.club)
        # `coach` (ejecutante, null en rivales) y `coach_faced` (DT del club
        # en ese partido, no nulo en ninguna fila mapeada) son preguntas
        # distintas. La conjugada necesita la segunda.
        trans = eras_mod.attach_coach_faced(trans, mc)
        cov = eras_mod.coverage_report(trans, args.club)
        gaps = eras_mod.unmapped_matches(trans, args.club)
        coach_info = {
            "attached": True,
            "club": args.club,
            "coverage": cov.to_dicts(),
            "unmapped_matches": gaps.height,
        }
    elif args.eras or args.match_dates:
        print("[aviso] --eras y --match-dates van juntos; se ignoran.", file=sys.stderr)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    trans.write_parquet(outdir / "transitions.parquet")

    sanity = coordinate_sanity(trans, space)

    # Diagnostico de la cadena conjugada. Un `coordinate_sanity` global promedia
    # las dos mitades y podria tapar un problema en una sola de ellas.
    sanity_def = None
    defense_info = None
    if args.club:
        riv = trans.filter(pl.col("team") != args.club)
        if riv.height:
            # En marco NATIVO el rival tambien ataca hacia x=120, asi que la
            # correlacion debe ser POSITIVA tambien aqui. Si sale negativa,
            # alguien reflejo coordenadas aguas arriba.
            sanity_def = coordinate_sanity(riv, space)
            reales = riv.filter(pl.col("action_type") != "TERMINAL")
            pcfg = cfg["possession"]
            defense_info = {
                "n_transitions": riv.height,
                "n_possessions": riv["poss_uid"].n_unique(),
                "n_teams": riv["team"].n_unique(),
                "min_actions_attack": int(pcfg["min_actions"]),
                "min_actions_defense": int(
                    pcfg.get("min_actions_defense", pcfg["min_actions"])
                ),
                # Primer numero de D1: si sale 0.0 o 1.0, el fill_null quedo mal.
                "pressure_rate": (
                    float(reales["under_pressure"].mean()) if reales.height else None
                ),
            }
    report = {
        "n_transitions": trans.height,
        "n_possessions": trans["poss_uid"].n_unique(),
        "n_matches": trans["match_id"].n_unique(),
        "teams": trans["team"].n_unique(),
        "state_space": {
            "n_transient": space.n_transient,
            "n_absorbing": space.n_absorbing,
            "nx": space.nx,
            "ny": space.ny,
            "phases": list(space.phases),
        },
        "coordinate_sanity": sanity,
        "coordinate_sanity_defense": sanity_def,
        "defense": defense_info,
        "coaches": coach_info,
        "by_score_state": trans.group_by("score_state").len().to_dicts(),
        "by_phase": trans.group_by("phase").len().to_dicts(),
        "provenance": _provenance(args.config),
    }
    (outdir / "phase0_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))

    if coach_info["attached"]:
        print("\n== Cobertura por era ==")
        print(eras_mod.coverage_report(trans, args.club))
        if coach_info["unmapped_matches"]:
            print(
                f"\n[AVISO] {coach_info['unmapped_matches']} partidos del club sin era "
                "asignada. Hay huecos en el CSV de eras.",
                file=sys.stderr,
            )
    if sanity_def is not None and not sanity_def["ok"]:
        print(
            f"\n[AVISO] La cadena conjugada no pasa el chequeo de coordenadas "
            f"(corr={sanity_def['corr']:.3f}). En marco NATIVO deberia ser "
            "positiva. NO interpretes nada defensivo hasta resolverlo.",
            file=sys.stderr,
        )
    if defense_info and defense_info["pressure_rate"] is not None:
        pr = defense_info["pressure_rate"]
        if pr <= 0.001 or pr >= 0.999:
            print(
                f"\n[AVISO] pressure_rate = {pr:.4f}. Un valor pegado a 0 o a 1 "
                "significa que `under_pressure` se leyo mal: es una BANDERA "
                "(true / ausente), no un booleano. Revisa el fill_null.",
                file=sys.stderr,
            )
    if not sanity["ok"]:
        print(
            f"\n[AVISO] P(gol) no crece con la columna de zona (corr={sanity['corr']:.3f}). "
            "Revisa la orientacion de coordenadas antes de interpretar nada.",
            file=sys.stderr,
        )
    return 0


def cmd_regimes(args) -> int:
    cfg = Config.load(args.config)
    space = _space(cfg)
    trans = _read_trans(args.indir)
    rc = eras_mod.detect_regime_changes(trans, space, args.club, window=args.window)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rc.write_parquet(outdir / "regime_changes.parquet")
    print("== Mayores quiebres estructurales (verifica contra tus fechas de era) ==")
    print(rc.sort("tv_weighted", descending=True).head(15))
    return 0


def cmd_phase1(args) -> int:
    cfg = Config.load(args.config)
    space = _space(cfg)
    trans = _read_trans(args.indir)
    trans = _apply_perspective(trans, args)
    focus, base = eras_mod.select_units(trans, args.unit, args.value, args.baseline, args.club)
    prior_src = base if args.prior == "baseline" else _not_focus(
        trans, args.unit, args.value)
    prior = _build_prior(trans, space, args.prior, prior_src)

    ecfg = cfg["estimation"]
    cv = cv_lambda(focus, space, prior, ecfg["lambda_grid"],
                   k=ecfg["cv_folds"], seed=ecfg["cv_seed"])
    C_focus = count_matrix(focus, space)
    C_base = count_matrix(base, space)
    P_focus = shrink(C_focus, prior, cv.lam_star)
    P_base = shrink(C_base, prior, cv.lam_star)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    # Los metadatos de identidad NO son decorativos: son la mitad que hace
    # verificable el contrato. `phase2` y `phase3` los exigen antes de usar
    # estas matrices (ver _check_matrices_identity). Sin ellos, un .npz de
    # otra unidad se consume en silencio y las figuras salen mal rotuladas.
    np.savez_compressed(
        outdir / "P_matrices.npz",
        P_focus=P_focus, P_base=P_base, prior=prior,
        C_focus=C_focus, C_base=C_base,
        unit=np.array(args.unit),
        value=np.array(args.value),
        baseline=np.array(args.baseline),
        prior_mode=np.array(args.prior),
        lam=np.array(cv.lam_star),
        perspective=np.array(getattr(args, "perspective", "attack")),
    )
    curve = error_curve(focus, space, prior, cv.lam_star)
    curve.write_parquet(outdir / "error_curve.parquet")
    plots.cv_curve(cv.grid, cv.scores, cv.lam_star, outdir / "figures" / "cv_lambda.png")
    plots.error_vs_n(curve, outdir / "figures" / "error_vs_n.png")

    sp = sparsity_report(C_focus)
    rep = {
        "unit": args.unit, "value": args.value, "baseline": args.baseline,
        "prior": args.prior,
        "lambda_star": cv.lam_star,
        "n_transitions_focus": int(C_focus.sum()),
        "n_transitions_base": int(C_base.sum()),
        "cv_scores": dict(zip(map(str, cv.grid), map(float, cv.scores))),
        "sparsity": sp,
        "provenance": _provenance(args.config),
    }
    (outdir / "phase1_report.json").write_text(json.dumps(rep, indent=2))
    print(f"{args.unit} = {args.value}   |   baseline = {args.baseline}   |   "
          f"prior = {args.prior}")
    print(cv.summary())
    _warn_boundary(cv, ecfg["lambda_grid"])
    print(json.dumps(sp, indent=2))
    if sp["frac_below_min"] > 0.30:
        print(
            f"\n[AVISO] {sp['frac_below_min']:.0%} de los renglones tienen menos de 30 "
            "observaciones. Baja nx/ny en config antes de seguir.",
            file=sys.stderr,
        )
    return 0


def cmd_phase2(args) -> int:
    cfg = Config.load(args.config)
    space = _space(cfg)
    trans = _read_trans(args.indir)
    trans = _apply_perspective(trans, args)
    focus, _ = eras_mod.select_units(trans, args.unit, args.value, args.baseline, args.club)
    mats = np.load(Path(args.indir) / "P_matrices.npz")
    err = _check_matrices_identity(mats, args)
    if err:
        return _abort(err)

    chain = AbsorbingChain(P=mats["P_focus"], space=space)
    checks = chain.check()
    if not checks["rho_ok"]:
        print(f"[error] rho(Q) = {checks['rho_Q']:.6f} >= 1: la cadena no absorbe.",
              file=sys.stderr)
        return 1

    xt = chain.xt()
    length = chain.expected_length()
    nu = chain.visit_distribution(empirical_start_distribution(focus, space))
    w = mats["C_focus"].sum(axis=1)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(outdir / "phase2.npz", xt=xt, length=length, nu=nu,
                        B=chain.absorption())

    tag = args.value
    plots.zone_heatmap(chain.zone_weighted(xt, w), space,
                       f"xT propio -- {tag}", outdir / "figures" / "xt.png")
    plots.zone_heatmap(chain.zone_weighted(length, w), space,
                       f"Acciones esperadas antes de absorber -- {tag}",
                       outdir / "figures" / "expected_length.png",
                       cmap="cividis", fmt="{:.2f}")
    plots.zone_heatmap(chain.zone_weighted(nu, w), space,
                       f"Distribucion de visitas $\\nu$ -- {tag}",
                       outdir / "figures" / "visits.png", cmap="magma", fmt="{:.3f}")

    rep = {"unit": args.unit, "value": args.value,
           "checks": {k: (v if isinstance(v, bool) else float(v)) for k, v in checks.items()},
           "xt_max": float(xt.max()), "xt_mean": float((xt * nu).sum()),
           # OJO: ponderado por nu (distribucion de visitas), NO por la
           # distribucion inicial alpha. E[T] de una posesion es alpha @ N @ 1
           # y da un numero distinto; no confundirlos al reportar.
           "expected_length_mean": float((length * nu).sum()),
           "provenance": _provenance(args.config)}
    (outdir / "phase2_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    return 0


def cmd_phase3(args) -> int:
    cfg = Config.load(args.config)
    space = _space(cfg)
    trans = _read_trans(args.indir)
    trans = _apply_perspective(trans, args)
    focus, base = eras_mod.select_units(trans, args.unit, args.value, args.baseline, args.club)
    mats = np.load(Path(args.indir) / "P_matrices.npz")
    err = _check_matrices_identity(mats, args)
    if err:
        return _abort(err)
    P_base, prior = mats["P_base"], mats["prior"]
    # lam sale del .npz, ya verificado como perteneciente a esta unidad. El
    # JSON de phase1 podria ser de otra corrida: misma clase de bug.
    lam = float(mats["lam"]) if "lam" in mats else json.loads(
        (Path(args.indir) / "phase1_report.json").read_text())["lambda_star"]

    icfg = cfg["inference"]
    n_boot = args.n_boot or icfg["n_boot"]

    fp = tactical_fingerprint(focus, base, space, P_base, n_boot=n_boot,
                              seed=icfg["boot_seed"], min_row_count=icfg["min_row_count"],
                              alpha=icfg["fdr_alpha"])
    ci = bootstrap_diff(focus, base, space, prior, lam,
                        n_boot=min(n_boot, 500), seed=icfg["boot_seed"])
    ctx = context_contrast(focus, space, prior, lam)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fp.to_frame(space).write_parquet(outdir / "fingerprint.parquet")
    ci.top_cells(space, k=40).write_parquet(outdir / "significant_cells.parquet")
    ctx.write_parquet(outdir / "context_contrast.parquet")
    plots.fingerprint_map(fp, space, outdir / "figures" / "fingerprint.png")

    print(f"\n=== {args.unit} = {args.value}   vs   baseline = {args.baseline} ===")
    print("\n== Huella tactica (top 10 estados por G2) ==")
    print(fp.to_frame(space).head(10))
    print(f"\nEstados testeados: {int(fp.tested.sum())} | rechazos tras FDR: "
          f"{int(fp.rejected.sum())}")
    print("\n== Celdas con IC de la diferencia que excluye el cero ==")
    print(ci.top_cells(space, k=12))
    print("\n== Contraste entre contextos (filosofia vs reactividad) ==")
    print(ctx)
    return 0


def cmd_compare(args) -> int:
    """Compara dos eras entre si. El entregable central con datos de un club."""
    cfg = Config.load(args.config)
    space = _space(cfg)
    trans = _read_trans(args.indir)
    trans = _apply_perspective(trans, args)
    # El prior debe ser neutral a las DOS unidades comparadas: si contuviera a
    # cualquiera de ellas, el encogimiento las acercaria artificialmente y
    # subestimaria la diferencia que buscas medir.
    neutral = trans.filter(
        (pl.col(args.unit) != args.a) & (pl.col(args.unit) != args.b)
        | pl.col(args.unit).is_null()
    )
    if neutral.height == 0:
        raise SystemExit("El prior neutral quedo vacio: no hay datos fuera de A y B.")
    prior = _build_prior(trans, space, "exclude_focus", neutral)
    lam = float(args.lam)

    a = trans.filter(pl.col(args.unit) == args.a)
    b = trans.filter(pl.col(args.unit) == args.b)
    for name, df in ((args.a, a), (args.b, b)):
        if df.height == 0:
            raise SystemExit(f"Sin transiciones para '{name}'")

    Pa = shrink(count_matrix(a, space), prior, lam)
    Pb = shrink(count_matrix(b, space), prior, lam)
    icfg = cfg["inference"]
    fp = tactical_fingerprint(a, b, space, Pb, n_boot=args.n_boot, seed=icfg["boot_seed"],
                              min_row_count=icfg["min_row_count"], alpha=icfg["fdr_alpha"])
    ci = bootstrap_diff(a, b, space, prior, lam, n_boot=min(args.n_boot, 500),
                        seed=icfg["boot_seed"])

    ch_a = AbsorbingChain(P=Pa, space=space)
    ch_b = AbsorbingChain(P=Pb, space=space)
    wa = count_matrix(a, space).sum(axis=1)
    denom = max(wa.sum(), 1e-12)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tag = f"{_slug(args.a)}_vs_{_slug(args.b)}"
    fp.to_frame(space).write_parquet(outdir / f"compare_{tag}.parquet")
    ci.top_cells(space, k=40).write_parquet(outdir / f"compare_cells_{tag}.parquet")
    plots.zone_heatmap(
        ch_a.zone_weighted(ch_a.xt(), wa) - ch_b.zone_weighted(ch_b.xt(), wa),
        space, f"$\\Delta$ xT:  {args.a}  \u2212  {args.b}",
        outdir / "figures" / f"delta_xt_{tag}.png", cmap="RdBu_r",
    )

    print(f"\n=== {args.a}  vs  {args.b} ===")
    print(f"xT medio      : {float((ch_a.xt() * wa).sum() / denom):.5f}  vs  "
          f"{float((ch_b.xt() * wa).sum() / denom):.5f}")
    print(f"long. esperada: {float((ch_a.expected_length() * wa).sum() / denom):.3f}  vs  "
          f"{float((ch_b.expected_length() * wa).sum() / denom):.3f}")
    print(f"\nEstados con diferencia significativa tras FDR: {int(fp.rejected.sum())} "
          f"de {int(fp.tested.sum())} testeados")
    print("\n== Estados donde mas difieren ==")
    print(fp.to_frame(space).head(10))
    print("\n== Celdas con IC que excluye el cero ==")
    print(ci.top_cells(space, k=12))
    return 0


def _not_focus(trans: pl.DataFrame, unit: str, value: str) -> pl.DataFrame:
    return trans.filter((pl.col(unit) != value) | pl.col(unit).is_null())


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()


def cmd_demo(args) -> int:
    outdir = Path(args.outdir)
    (outdir / "raw").mkdir(parents=True, exist_ok=True)
    src = outdir / "raw" / "synth.parquet"
    synth_events(n_matches=args.n_matches, seed=13).write_parquet(src)
    print(f"[demo] datos sinteticos -> {src}")

    ns = argparse.Namespace(
        config=args.config, src=str(src), outdir=str(outdir), indir=str(outdir),
        unit="team", value="Club A", baseline="rest", club="Club A",
        prior="exclude_focus", eras=None, match_dates=None, n_boot=args.n_boot,
        perspective="attack",
    )
    for fn in (cmd_phase0, cmd_phase1, cmd_phase2, cmd_phase3):
        print(f"\n{'=' * 70}\n>>> {fn.__name__}\n{'=' * 70}")
        if fn(ns) != 0:
            return 1
    print(f"\n[demo] listo. Figuras en {outdir / 'figures'}")
    return 0


# ==========================================================================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dtdecoder", description=__doc__)
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_unit_args(p):
        p.add_argument("--unit", default="coach",
                       choices=["team", "coach", "coach_faced"])
        p.add_argument("--value", required=True, help="nombre del DT o del equipo")
        p.add_argument("--baseline", default="other_coaches",
                       choices=["rest", "other_coaches", "opponents"])
        p.add_argument("--club", default=None, help="equipo del DT focal")
        p.add_argument("--perspective", default="attack",
                       choices=["attack", "defense"],
                       help="attack = fase con balon (posesiones del club); "
                            "defense = cadena conjugada sobre las posesiones "
                            "del rival. Con defense usa --unit coach_faced.")
        p.add_argument("--prior", default="exclude_focus",
                       choices=["exclude_focus", "pooled", "baseline"],
                       help="de donde sale q, el prior del encogimiento")

    c = sub.add_parser("convert", help="volcado crudo -> parquet normalizado")
    c.add_argument("--src", required=True)
    c.add_argument("--dst", required=True)
    c.add_argument("--partition-by", default=None)
    c.set_defaults(func=cmd_convert)

    e = sub.add_parser("eras-template", help="genera CSV de eras de DT")
    e.add_argument("--out", default="data/coach_eras.csv")
    e.set_defaults(func=cmd_eras_template)

    p0 = sub.add_parser("phase0", help="cadenas de posesion, transiciones y eras")
    p0.add_argument("--src", required=True)
    p0.add_argument("--outdir", default="data/processed")
    p0.add_argument("--eras", default=None)
    p0.add_argument("--match-dates", default=None, dest="match_dates")
    p0.add_argument("--club", default=None,
                    help="club focal. Necesario para score_state_club, para "
                         "min_actions asimetrico y para coach_faced. Pasalo "
                         "SIEMPRE, tambien sin --eras.")
    p0.set_defaults(func=cmd_phase0)

    rg = sub.add_parser("regimes", help="verifica fronteras de era empiricamente")
    rg.add_argument("--indir", default="data/processed")
    rg.add_argument("--outdir", default="data/processed")
    rg.add_argument("--club", required=True)
    rg.add_argument("--window", type=int, default=8)
    rg.set_defaults(func=cmd_regimes)

    p1 = sub.add_parser("phase1", help="encogimiento + CV de lambda")
    p1.add_argument("--indir", default="data/processed")
    p1.add_argument("--outdir", default="data/processed")
    add_unit_args(p1)
    p1.set_defaults(func=cmd_phase1)

    p2 = sub.add_parser("phase2", help="cadena absorbente: N, B, xT, visitas")
    p2.add_argument("--indir", default="data/processed")
    p2.add_argument("--outdir", default="data/processed")
    add_unit_args(p2)
    p2.set_defaults(func=cmd_phase2)

    p3 = sub.add_parser("phase3", help="huella tactica: bootstrap, G2, FDR")
    p3.add_argument("--indir", default="data/processed")
    p3.add_argument("--outdir", default="data/processed")
    add_unit_args(p3)
    p3.add_argument("--n-boot", type=int, default=None, dest="n_boot")
    p3.set_defaults(func=cmd_phase3)

    cp = sub.add_parser("compare", help="DT contra DT (el entregable central)")
    cp.add_argument("--indir", default="data/processed")
    cp.add_argument("--outdir", default="data/processed")
    cp.add_argument("--unit", default="coach", choices=["team", "coach"])
    cp.add_argument("--a", required=True)
    cp.add_argument("--b", required=True)
    cp.add_argument("--lam", type=float, default=50.0)
    cp.add_argument("--n-boot", type=int, default=1000, dest="n_boot")
    cp.add_argument("--club", default=None)
    cp.add_argument("--perspective", default="attack",
                    choices=["attack", "defense"])
    cp.set_defaults(func=cmd_compare)

    d = sub.add_parser("demo", help="pipeline completo sobre datos sinteticos")
    d.add_argument("--outdir", default="reports/demo")
    d.add_argument("--n-matches", type=int, default=60, dest="n_matches")
    d.add_argument("--n-boot", type=int, default=300, dest="n_boot")
    d.set_defaults(func=cmd_demo)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
