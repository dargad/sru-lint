"""
Helper module for Launchpad integration.
Provides cached Launchpad connection and utility functions.
"""
from launchpadlib.launchpad import Launchpad
from typing import Optional, List, Set
import re


class LaunchpadHelper:
    """Singleton helper class for Launchpad interactions."""
    
    _instance: Optional['LaunchpadHelper'] = None
    _launchpad: Optional[Launchpad] = None
    _valid_distributions: Optional[Set[str]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the LaunchpadHelper (only once due to singleton pattern)."""
        if self._launchpad is None:
            cachedir = "~/.launchpadlib/cache"
            self._launchpad = Launchpad.login_anonymously(
                "sru-lint", 
                "production", 
                cachedir,
                version="devel"
            )
            self._ubuntu = self._launchpad.distributions["ubuntu"]
            self._archive = self._ubuntu.main_archive
    
    @property
    def launchpad(self) -> Launchpad:
        """Get the Launchpad instance."""
        return self._launchpad
    
    @property
    def ubuntu(self):
        """Get the Ubuntu distribution object."""
        return self._ubuntu
    
    @property
    def archive(self):
        """Get the Ubuntu main archive object."""
        return self._archive
    
    def get_bug(self, bug_number: int):
        """
        Get a bug by its number.
        
        Args:
            bug_number: The Launchpad bug number
            
        Returns:
            The bug object from Launchpad, or None if not found
        """
        try:
            return self._launchpad.bugs[bug_number]
        except Exception as e:
            print(f"Error fetching bug #{bug_number}: {e}")
            return None
    
    def is_bug_targeted(self, bug_number: int, package: str, distribution: str) -> bool:
        """
        Check if a bug is targeted at a specific package and distribution.
        
        Args:
            bug_number: The Launchpad bug number
            package: The package name
            distribution: The distribution name (e.g., 'jammy', 'focal')
            
        Returns:
            True if the bug is targeted at the package and distribution, False otherwise
        """
        bug = self.get_bug(bug_number)
        if not bug:
            return False
        
        for task in bug.bug_tasks:
            print(f"Checking task: package={task.target.name}, bug_target_name={task.bug_target_name}")
            # Normalize distribution names for comparison
            package_match = task.target.name == package
            # Check if distribution is in bug_target_name (case-insensitive)
            dist_match = distribution.lower() in task.bug_target_name.lower()
            if package_match and dist_match:
                return True
        return False
    
    def get_bug_tasks(self, bug_number: int) -> List:
        """
        Get all bug tasks for a bug.
        
        Args:
            bug_number: The Launchpad bug number
            
        Returns:
            List of bug tasks, or empty list if bug not found
        """
        bug = self.get_bug(bug_number)
        if not bug:
            return []
        return list(bug.bug_tasks)
    
    def search_series(self, series_name: str):
        """
        Search for a distribution series by name.
        
        Args:
            series_name: The series name (e.g., 'jammy', 'focal')
            
        Returns:
            The series object, or None if not found
        """
        try:
            return self._ubuntu.getSeries(name_or_version=series_name)
        except Exception as e:
            print(f"Error fetching series '{series_name}': {e}")
            return None
    
    def get_valid_distributions(self, include_pockets: bool = True) -> Set[str]:
        """
        Get a set of valid Ubuntu distribution names.
        
        This method caches the result to avoid repeated API calls.
        
        Args:
            include_pockets: If True, includes pocket suffixes like -proposed, -updates, -security
            
        Returns:
            Set of valid distribution names (e.g., {'jammy', 'focal', 'jammy-proposed', ...})
        """
        if self._valid_distributions is not None and include_pockets:
            return self._valid_distributions
        
        distributions = set()
        pockets = ['', '-proposed', '-updates', '-security', '-backports'] if include_pockets else ['']
        
        try:
            # Get all series (including current and supported releases)
            for series in self._ubuntu.series:
                # Only include series that are current or supported
                if series.active:
                    series_name = series.name
                    for pocket in pockets:
                        distributions.add(f"{series_name}{pocket}")
            
            # Cache the full set (with pockets) for future use
            if include_pockets:
                self._valid_distributions = distributions
                
        except Exception as e:
            print(f"Error fetching valid distributions: {e}")
            # Return a minimal set of known distributions as fallback
            distributions = {
                'questing', 'questing-proposed', 'questing-updates', 'questing-security',
                'plucky', 'plucky-proposed', 'plucky-updates', 'plucky-security',
                'noble', 'noble-proposed', 'noble-updates', 'noble-security',
                'jammy', 'jammy-proposed', 'jammy-updates', 'jammy-security',
                'focal', 'focal-proposed', 'focal-updates', 'focal-security',
            }
        
        return distributions
    
    def is_valid_distribution(self, distribution: str) -> bool:
        """
        Check if a distribution name is valid.
        
        Args:
            distribution: The distribution name to check (e.g., 'jammy', 'jammy-proposed')
            
        Returns:
            True if the distribution is valid, False otherwise
        """
        valid_distributions = self.get_valid_distributions()
        return distribution in valid_distributions
    
    @staticmethod
    def extract_lp_bugs(text: str) -> List[int]:
        """
        Extract Launchpad bug numbers from text.
        
        Args:
            text: The text to search for bug numbers (e.g., changelog entry)
            
        Returns:
            List of bug numbers found in the text
        """
        matches = re.findall(r"LP:\s*#(\d+)", text)
        return [int(match) for match in matches]