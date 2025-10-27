"""
Helper module for Launchpad integration.
Provides cached Launchpad connection and utility functions.
"""
from launchpadlib.launchpad import Launchpad
from typing import Optional, List, Set
import re

from sru_lint.common.logging import get_logger


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
            self.logger = get_logger("launchpad_helper")
            
            self.logger.info("Initializing Launchpad connection")
            cachedir = "~/.launchpadlib/cache"
            self._launchpad = Launchpad.login_anonymously(
                "sru-lint", 
                "production", 
                cachedir,
                version="devel"
            )
            self._ubuntu = self._launchpad.distributions["ubuntu"]
            self._archive = self._ubuntu.main_archive
            self.logger.debug("Launchpad connection established")
    
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
            self.logger.debug(f"Fetching bug #{bug_number}")
            bug = self._launchpad.bugs[bug_number]
            self.logger.debug(f"Successfully fetched bug #{bug_number}")
            return bug
        except Exception as e:
            self.logger.error(f"Error fetching bug #{bug_number}: {e}")
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
        
        self.logger.debug(f"Checking if bug #{bug_number} is targeted at {package} in {distribution}")
        
        for task in bug.bug_tasks:
            self.logger.debug(f"Checking task: package={task.target.name}, bug_target_name={task.bug_target_name}")
            # Normalize distribution names for comparison
            package_match = task.target.name == package
            # Check if distribution is in bug_target_name (case-insensitive)
            dist_match = distribution.lower() in task.bug_target_name.lower()
            if package_match and dist_match:
                self.logger.debug(f"Bug #{bug_number} is targeted at {package} in {distribution}")
                return True
        
        self.logger.debug(f"Bug #{bug_number} is NOT targeted at {package} in {distribution}")
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
        
        tasks = list(bug.bug_tasks)
        self.logger.debug(f"Bug #{bug_number} has {len(tasks)} tasks")
        return tasks
    
    def search_series(self, series_name: str):
        """
        Search for a distribution series by name.
        
        Args:
            series_name: The series name (e.g., 'jammy', 'focal')
            
        Returns:
            The series object, or None if not found
        """
        try:
            self.logger.debug(f"Searching for series '{series_name}'")
            series = self._ubuntu.getSeries(name_or_version=series_name)
            self.logger.debug(f"Found series '{series_name}'")
            return series
        except Exception as e:
            self.logger.error(f"Error fetching series '{series_name}': {e}")
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
            self.logger.debug(f"Using cached distributions ({len(self._valid_distributions)} items)")
            return self._valid_distributions
        
        self.logger.info(f"Fetching valid distributions (include_pockets={include_pockets})")
        
        distributions = set()
        pockets = ['', '-proposed', '-updates', '-security', '-backports'] if include_pockets else ['']
        
        try:
            # Get all series (including current and supported releases)
            series_count = 0
            for series in self._ubuntu.series:
                # Only include series that are current or supported
                if series.active:
                    series_name = series.name
                    self.logger.debug(f"Adding active series: {series_name}")
                    for pocket in pockets:
                        distributions.add(f"{series_name}{pocket}")
                    series_count += 1
            
            # Cache the full set (with pockets) for future use
            if include_pockets:
                self._valid_distributions = distributions
            
            self.logger.info(f"Fetched {series_count} active series, generated {len(distributions)} distribution names")
                
        except Exception as e:
            self.logger.error(f"Error fetching valid distributions: {e}")
            self.logger.warning("Using fallback distribution list")
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
        is_valid = distribution in valid_distributions
        self.logger.debug(f"Distribution '{distribution}' is {'valid' if is_valid else 'invalid'}")
        return is_valid
    
    @staticmethod
    def extract_lp_bugs(text: str) -> List[int]:
        """
        Extract Launchpad bug numbers from text.
        
        Args:
            text: The text to search for bug numbers (e.g., changelog entry)
            
        Returns:
            List of bug numbers found in the text
        """
        logger = get_logger("launchpad_helper")
        matches = re.findall(r"LP:\s*#(\d+)", text)
        bug_numbers = [int(match) for match in matches]
        logger.debug(f"Extracted {len(bug_numbers)} LP bug numbers from text: {bug_numbers}")
        return bug_numbers
    
    @staticmethod
    def get_upload_queue_url(package_name: str, distribution: str) -> str:
        """
        Construct the Launchpad upload queue URL for a package and distribution.
        
        Args:
            package_name: The package name
            distribution: The distribution name (e.g., 'jammy', 'focal')
        Returns:
            The URL string to the upload queue page
        """
        return f"https://launchpad.net/ubuntu/{distribution}/+queue?queue_state=1&queue_text={package_name}"
    
    def get_publishing_history_url(package_name: str) -> str:
        """
        Construct the Launchpad publishing history URL for a package.
        
        Args:
            package_name: The package name
        Returns:
            The URL string to the publishing history page
        """
        return f"https://launchpad.net/ubuntu/+source/{package_name}/+publishinghistory"
    
    def has_sru_template(self, bug_number: int) -> bool:
        """
        Check if a bug has the SRU template applied in its description.
        
        Args:
            bug_number: The Launchpad bug number
        Returns:
            True if the SRU template is found, False otherwise
        """
        bug = self.get_bug(bug_number)
        if not bug:
            return False
        
        self.logger.debug(f"Checking SRU template for bug #{bug_number}")
        description = bug.description or ""
        
        # Check for SRU template keywords with flexible spacing around square brackets
        # Patterns match with and without spaces after/before square brackets
        sru_keyword_patterns = [
            r'\[\s*Impact\s*\]',
            r'\[\s*Test\s+Plan\s*\]',
            r'\[\s*Where\s+problems\s+could\s+occur\s*\]'
        ]

        keywords_found = 0
        
        for pattern in sru_keyword_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                self.logger.debug(f"Found SRU template keyword pattern '{pattern}' in bug #{bug_number}")
                keywords_found += 1

        self.logger.debug(f"LP: #{bug_number} has {keywords_found} SRU template keywords")
        return keywords_found > 1

# Create a single global instance
_launchpad_helper = None

def get_launchpad_helper() -> LaunchpadHelper:
    """
    Get the global LaunchpadHelper instance.
    
    Returns:
        The singleton LaunchpadHelper instance
    """
    global _launchpad_helper
    if _launchpad_helper is None:
        logger = get_logger("launchpad_helper")
        logger.debug("Creating new LaunchpadHelper instance")
        _launchpad_helper = LaunchpadHelper()
    return _launchpad_helper