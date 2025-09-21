from abc import ABC, abstractmethod

class Plugin(ABC):
    """Base class for plugins that process patches (parsed by unidiff)."""
    
    @abstractmethod
    def process(self, patches):
        """Process the given patches and perform plugin-specific actions."""
        raise NotImplementedError("Subclasses must implement this method")
