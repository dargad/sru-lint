import importlib
import inspect
import pkgutil
import sys
from sru_lint.plugin_base import Plugin
import sru_lint.plugins  # import the plugins module or package


class PluginManager:
    """Manager to discover and instantiate all Plugin subclasses in sru_lint.plugins."""
    
    @staticmethod
    def load_plugins():
        """Discover all Plugin subclasses in sru_lint.plugins and its submodules and return a list of their instances."""
        plugins = []
        discovered_classes = set()

        # If sru_lint.plugins is a package, iterate through its submodules and import them
        if hasattr(sru_lint.plugins, "__path__"):  # indicates it's a namespace package
            for finder, name, ispkg in pkgutil.iter_modules(sru_lint.plugins.__path__, sru_lint.plugins.__name__ + "."):
                importlib.import_module(name)  # import each submodule (ensures all plugin classes are loaded)

        # Inspect sru_lint.plugins for Plugin subclasses
        for _, obj in inspect.getmembers(sru_lint.plugins, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin:
                if obj not in discovered_classes:
                    plugins.append(obj())
                    discovered_classes.add(obj)

        # Inspect submodules for Plugin subclasses
        if hasattr(sru_lint.plugins, "__path__"):
            for module_name, module in list(sys.modules.items()):
                if module_name.startswith(sru_lint.plugins.__name__ + "."):
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, Plugin) and obj is not Plugin and obj not in discovered_classes:
                            plugins.append(obj())
                            discovered_classes.add(obj)
        return plugins