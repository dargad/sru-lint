from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.patches import combine_added_lines
from sru_lint.common.launchpad_helper import LaunchpadHelper

from debian import changelog


class ChangelogEntry(Plugin):
    """Checks the changelog entry."""

    def __init__(self):
        """Initialize the plugin and Launchpad helper."""
        super().__init__()
        self.lp_helper = LaunchpadHelper()

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, patched_file):
        """
        Checks done in the changelog entry:
        - Check if the distribution is valid (e.g., 'jammy', 'jammy-proposed', etc.)
        - Check if the version number is valid.
        - If there is an LP bug number mentioned (LP: #123456), check if
          the bug exists and if it is targeted at the correct package and
          distribution.
        """
        print("ChangelogEntry")

        content = combine_added_lines(patched_file)

        for k in content:
            cl = changelog.Changelog(content[k])
            print(f"{cl.get_package()}:{cl.distributions}:{cl.full_version}")
            print(f"Author: {cl.author} Date: {cl.date}")

            # Extract LP bug numbers using the helper
            lpbugs = self.lp_helper.extract_lp_bugs(str(cl))

            if lpbugs:
                for lpbug in lpbugs:
                    print(f"LP Bug: LP: #{lpbug}")
                    
                    # Get bug tasks using the helper
                    bug_tasks = self.lp_helper.get_bug_tasks(lpbug)
                    
                    targeted = False
                    for task in bug_tasks:
                        print(f"  Task: {task.target.name} / {task.bug_target_name} / {task.status}")
                        # Normalize distribution names for comparison
                        package_match = task.target.name == cl.get_package()
                        # Check if cl.distributions is in bug_target_name (case-insensitive)
                        dist_match = cl.distributions.lower() in task.bug_target_name.lower()
                        if package_match and dist_match:
                            targeted = True
                            print(f"Bug LP: #{lpbug} is targeted at {cl.get_package()} and {cl.distributions}")
                    
                    if not targeted:
                        print(f"Bug {lpbug} is NOT targeted at {cl.get_package()} and {cl.distributions}")
                    
                    # Alternative: Use the helper's convenience method
                    # is_targeted = self.lp_helper.is_bug_targeted(lpbug, cl.get_package(), cl.distributions)
                    # if not is_targeted:
                    #     print(f"Bug {lpbug} is NOT targeted at {cl.get_package()} and {cl.distributions}")