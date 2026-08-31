"""Carga de configuracion. Un solo punto de verdad para todo parametro."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        p = Path(path) if path is not None else _DEFAULT
        if not p.exists():
            raise FileNotFoundError(
                f"No encuentro config en {p}. Pasa --config con la ruta correcta."
            )
        with open(p) as fh:
            return cls(raw=yaml.safe_load(fh))
