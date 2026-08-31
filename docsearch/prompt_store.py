"""Load versioned YAML prompts from disk so they can change without code deploys."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from docsearch.config import get_settings


class PromptStore:
    def __init__(self, directory: Path, hot_reload: bool = True) -> None:
        self.directory = Path(directory)
        self.hot_reload = hot_reload
        self._mtime: dict[str, float] = {}
        self._cache: dict[str, dict[str, Any]] = {}

    def list_prompts(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.yaml"))

    def get(self, name: str) -> dict[str, Any]:
        path = self.directory / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        mtime = path.stat().st_mtime
        if (
            not self.hot_reload
            and name in self._cache
            and self._mtime.get(name) == mtime
        ):
            return self._cache[name]
        if name in self._cache and self._mtime.get(name) == mtime:
            return self._cache[name]
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        self._cache[name] = payload
        self._mtime[name] = mtime
        return payload

    def render(self, name: str, **values: Any) -> str:
        spec = self.get(name)
        template = spec.get("template")
        if not template:
            raise ValueError(f"Prompt '{name}' is missing a template field")
        return str(template).format(**values)

    def system_role(self, name: str) -> str:
        return str(self.get(name).get("system", "")).strip()


@lru_cache
def get_prompt_store() -> PromptStore:
    settings = get_settings()
    return PromptStore(settings.prompts_dir, hot_reload=settings.prompt_hot_reload)
