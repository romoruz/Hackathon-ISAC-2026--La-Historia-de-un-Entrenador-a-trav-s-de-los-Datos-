"""Figuras minimas: mapa de campo, curva de error, huella tactica."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .grid import StateSpace  # noqa: E402


def _pitch(ax, space: StateSpace) -> None:
    ax.set_xlim(0, space.length)
    ax.set_ylim(0, space.width)
    ax.set_aspect("equal")
    ax.plot([space.length / 2] * 2, [0, space.width], color="k", lw=0.8, alpha=0.5)
    for x0, x1 in ((0, 18), (space.length - 18, space.length)):
        ax.plot([x0, x1, x1, x0], [18, 18, space.width - 18, space.width - 18],
                color="k", lw=0.6, alpha=0.4)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(space.length * 0.5, -4, "sentido de ataque \u2192", ha="center", fontsize=8)


def zone_heatmap(
    values_zone: np.ndarray,
    space: StateSpace,
    title: str,
    outpath: str | Path,
    cmap: str = "viridis",
    fmt: str = "{:.3f}",
) -> Path:
    """`values_zone` con forma (nx, ny)."""
    fig, ax = plt.subplots(figsize=(8, 5.4))
    _pitch(ax, space)
    grid = values_zone.T  # imshow espera (filas=y, cols=x)
    im = ax.imshow(
        grid,
        extent=(0, space.length, 0, space.width),
        origin="lower",
        cmap=cmap,
        alpha=0.85,
        aspect="auto",
    )
    for ix in range(space.nx):
        for iy in range(space.ny):
            cx, cy = space.zone_centroid(ix * space.ny + iy)
            ax.text(cx, cy, fmt.format(values_zone[ix, iy]), ha="center", va="center",
                    fontsize=8, color="w")
    ax.set_title(title, fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.tight_layout()
    p = Path(outpath)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def cv_curve(grid: np.ndarray, scores: np.ndarray, lam_star: float, outpath: str | Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(grid, scores, marker="o")
    ax.axvline(lam_star, color="crimson", ls="--", label=f"$\\lambda^*$ = {lam_star:g}")
    ax.set_xscale("symlog")
    ax.set_xlabel("$\\lambda$ (pseudo-conteos)")
    ax.set_ylabel("log-verosimilitud OOS\n(nats por transicion)")
    ax.set_title("Seleccion de $\\lambda$ por validacion cruzada por posesion")
    ax.legend()
    fig.tight_layout()
    p = Path(outpath)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def error_vs_n(df, outpath: str | Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 3.6))
    agg = df.group_by("n_possessions").agg(
        [
            __import__("polars").col("err_weighted").mean().alias("mean"),
            __import__("polars").col("err_weighted").std().alias("sd"),
        ]
    ).sort("n_possessions")
    x = agg["n_possessions"].to_numpy()
    m = agg["mean"].to_numpy()
    s = np.nan_to_num(agg["sd"].to_numpy())
    ax.plot(x, m, marker="o")
    ax.fill_between(x, m - s, m + s, alpha=0.2)
    ax.set_xscale("log")
    ax.set_xlabel("posesiones de entrenamiento")
    ax.set_ylabel("error $\\|\\hat{p}-p_{full}\\|_\\infty$ ponderado")
    ax.set_title("Curva error-vs-N: cuanta malla aguantan tus datos")
    fig.tight_layout()
    p = Path(outpath)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def fingerprint_map(fp, space: StateSpace, outpath: str | Path) -> Path:
    """Colapsa G2 por zona (max sobre fases) y lo pinta sobre el campo."""
    g2 = fp.g2_obs.reshape(space.n_zones, len(space.phases)).max(axis=1)
    rej = fp.rejected.reshape(space.n_zones, len(space.phases)).any(axis=1)
    vals = g2.reshape(space.nx, space.ny)

    fig, ax = plt.subplots(figsize=(8, 5.4))
    _pitch(ax, space)
    im = ax.imshow(vals.T, extent=(0, space.length, 0, space.width), origin="lower",
                   cmap="magma", alpha=0.85, aspect="auto")
    for z in range(space.n_zones):
        ix, iy = divmod(z, space.ny)
        cx, cy = space.zone_centroid(z)
        mark = "\u2605" if rej[z] else ""
        ax.text(cx, cy, f"{vals[ix, iy]:.0f}{mark}", ha="center", va="center",
                fontsize=8, color="w")
    ax.set_title("Huella tactica: $G^2$ vs liga  ($\\star$ = significativo tras FDR)", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.tight_layout()
    p = Path(outpath)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p
