import pathlib
import typing as t

import yaml


class ConfigLoader:
    """Small helper around a YAML config with dotted key access."""

    def __init__(self, path: t.Union[str, pathlib.Path]):
        self.path = pathlib.Path(path)
        with self.path.open("r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

    def get(self, dotted_key: str, default: t.Any = None) -> t.Any:
        parts = dotted_key.split(".")
        current = self._data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    @property
    def data(self) -> dict:
        return self._data
