from __future__ import annotations

from typing import Any, Protocol


class Plugin(Protocol):
    name: str
    description: str

    def execute(self, client: Any, config: dict, **kwargs) -> dict:
        ...
