"""
Helper module for Launchpad integration.
Provides cached Launchpad connection and utility functions.
"""
from launchpadlib.launchpad import Launchpad
from typing import Optional, List
import re


class LaunchpadHelper:
    """Singleton helper class for Launchpad interactions."""
    
    _instance: Optional['LaunchpadHelper'] = None
    _launchpad: Optional[Launchpad] = None
    
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