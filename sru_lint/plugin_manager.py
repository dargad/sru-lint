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

        # If sru_lint.plugins is a package, recursively import all submodules
        if hasattr(sru_lint.plugins, "__path__"):  # indicates it's a namespace package
            PluginManager._import_submodules_recursively(sru_lint.plugins)

        # Inspect sru_lint.plugins for Plugin subclasses
        for _, obj in inspect.getmembers(sru_lint.plugins, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin:
                if obj not in discovered_classes:
                    plugins.append(obj())
                    discovered_classes.add(obj)

        # Inspect all submodules for Plugin subclasses
        for module_name, module in list(sys.modules.items()):
            if module_name.startswith(sru_lint.plugins.__name__ + "."):
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    try:
                        if issubclass(obj, Plugin) and obj is not Plugin and obj not in discovered_classes:
                            plugins.append(obj())
                            discovered_classes.add(obj)
                    except TypeError:
                        # obj might not be a class we can check with issubclass
                        pass
        return plugins
    
    @staticmethod
    def _import_submodules_recursively(package):
        """Recursively import all submodules and subpackages of a given package."""
        # Check if it's a package by looking for __path__ attribute
        if not hasattr(package, "__path__"):
            return
            
        for finder, name, ispkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            try:
                submodule = importlib.import_module(name)
                # If this is a package, recursively import its submodules
                if ispkg:
                    PluginManager._import_submodules_recursively(submodule)
            except (ImportError, Exception):
                # Silently continue with other modules if import fails
                pass