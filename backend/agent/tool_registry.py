from __future__ import annotations

from typing import Dict, Iterable, Optional

from .contracts import RetryPolicy, ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: Dict[str, ToolSpec] = {} # AI辅助生成：GLM-5, 2026-04-16

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, tool_name: str) -> Optional[ToolSpec]:
        return self._specs.get(str(tool_name or "").strip())

    def all_specs(self) -> Dict[str, ToolSpec]:
        return dict(self._specs)

    def has(self, tool_name: str) -> bool:
        return str(tool_name or "").strip() in self._specs


def build_default_registry(
    *,
    tool_names: Iterable[str],
    stage_map: Dict[str, str],
    retry_limits: Dict[str, int],
) -> ToolRegistry: # AI辅助生成：GLM-5, 2026-04-17
    registry = ToolRegistry()
    for name in sorted({str(x).strip() for x in tool_names if str(x).strip()}):
        stage = stage_map.get(name, "tooling")
        retry_max = int(retry_limits.get(name, 0))
        registry.register(
            ToolSpec(
                name=name,
                stage=stage,
                retry_policy=RetryPolicy(max_retries=retry_max),
            )
        )
    return registry

