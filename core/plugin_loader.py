"""
External Plugin Loader — auto-discover user agents from agents/user_plugins/

Place any .py file in agents/user_plugins/ with:
  NAME = "MyAgent"
  DESCRIPTION = "What it does"
  CAPABILITIES = ["capability_1", "capability_2"]
  def run(task: dict) -> dict: ...

The plugin is automatically registered as a new Agent endpoint and added to Commander/CEO routing.
"""
import importlib.util
import json, os, sys, uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PLUGIN_DIR = Path(__file__).parent.parent / "agents" / "user_plugins"
PLUGIN_DIR.mkdir(parents=True, exist_ok=True)


class ExternalPlugin:
    def __init__(self, path: Path):
        self.path = path
        self.id = path.stem
        self.name = self.id
        self.description = ""
        self.capabilities: List[str] = []
        self.run_fn: Optional[Callable] = None
        self._loaded = False

    def load(self) -> bool:
        if self._loaded: return True
        try:
            spec = importlib.util.spec_from_file_location(f"user_plugin_{self.id}", str(self.path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.name = getattr(mod, "NAME", self.id)
            self.description = getattr(mod, "DESCRIPTION", "")
            self.capabilities = getattr(mod, "CAPABILITIES", [])
            self.run_fn = getattr(mod, "run", None)
            self._loaded = self.run_fn is not None
        except Exception as e:
            print(f"[PluginLoader] Failed to load {self.path}: {e}")
        return self._loaded

    def run(self, task: Dict) -> Dict:
        if not self._loaded: self.load()
        if not self.run_fn:
            return {"ok": False, "error": f"Plugin {self.name} not loaded"}
        try:
            result = self.run_fn(task)
            return {
                "ok": True,
                "agent": f"plugin/{self.id}",
                "agent_name": self.name,
                "status": "completed",
                "data": result if isinstance(result, dict) else {"output": result},
                "meta": {"plugin_id": self.id},
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "agent": f"plugin/{self.id}"}


class PluginLoader:
    def __init__(self):
        self._plugins: Dict[str, ExternalPlugin] = {}
        self._discover()

    def _discover(self):
        self._plugins = {}
        for py_file in PLUGIN_DIR.glob("*.py"):
            if py_file.name.startswith("_"): continue
            plugin = ExternalPlugin(py_file)
            if plugin.load():
                self._plugins[plugin.id] = plugin

    def list_all(self) -> List[Dict]:
        self._discover()
        return [{"id": p.id, "name": p.name, "description": p.description,
                 "capabilities": p.capabilities} for p in self._plugins.values()]

    def get(self, plugin_id: str) -> Optional[ExternalPlugin]:
        self._discover()
        return self._plugins.get(plugin_id)

    def run(self, plugin_id: str, task: Dict) -> Dict:
        p = self.get(plugin_id)
        if not p: return {"ok": False, "error": f"Plugin not found: {plugin_id}"}
        return p.run(task)


_loader: Optional[PluginLoader] = None
def get_plugin_loader() -> PluginLoader:
    global _loader
    if _loader is None: _loader = PluginLoader()
    return _loader
