from __future__ import annotations

import structlog

from app.core.assets.module_interface import AgentTool, IAssetModule

log = structlog.get_logger()

_modules: dict[str, IAssetModule] = {}


def register_module(module: IAssetModule) -> None:
    if module.asset_type in _modules:
        log.warning("module_already_registered", asset_type=module.asset_type)
        return
    _modules[module.asset_type] = module
    log.info("module_registered", asset_type=module.asset_type, display_name=module.display_name)


def get_module(module_id: str) -> IAssetModule | None:
    return _modules.get(module_id)


def list_modules() -> list[IAssetModule]:
    return list(_modules.values())


def get_modules_for_asset_type(asset_type: str) -> list[IAssetModule]:
    module = _modules.get(asset_type)
    return [module] if module else []


def get_tools_for_context(
    caller_permissions: list[str],
    module_id: str | None = None,
) -> list[AgentTool]:
    tools: list[AgentTool] = []
    modules = [_modules[module_id]] if module_id and module_id in _modules else _modules.values()
    for mod in modules:
        for tool in mod.get_agent_tools():
            if any(p in caller_permissions for p in tool.required_permissions) or not tool.required_permissions:
                tools.append(tool)
    return tools


def clear_registry() -> None:
    """Clear all registered modules — for testing."""
    _modules.clear()
