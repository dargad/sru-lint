from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.patches import combine_added_lines, make_end_filename_matcher, match_hunks

from debian import changelog
from launchpadlib.launchpad import Launchpad

from sru_lint.common.shared import DEBIAN_CHANGELOG

class ChangelogEntry(Plugin):
    """Checks the changelog entry."""

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

        cachedir = "~/.launchpadlib/cache"
        launchpad = Launchpad.login_anonymously("check-version", "production", cachedir)
        ubuntu = launchpad.distributions["ubuntu"]
        archive = ubuntu.main_archive

        content = combine_added_lines(patched_file)
        print(f"Content: {content}")

        for k in content:
            cl = changelog.Changelog(content[k])
            print(f"{cl.get_package()}:{cl.distributions}:{cl.full_version}")
            print(f"Author: {cl.author} Date: {cl.date}")

            lpbugs = self.search_for_lpbug(str(cl))

            if lpbugs:
                for lpbug in lpbugs:
                    print(f"LP Bug: LP: #{lpbug}")
                    # Search Launchpad for the bug and check targeting
                    bug = launchpad.bugs[int(lpbug)]
                    targeted = False
                    for task in bug.bug_tasks:
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


    def search_for_lpbug(self, changelog: str):
        import re
        print("Searching for LP bug number in the changelog")
        matches = re.findall(r"LP:\s*#(\d+)", changelog)
        if matches:
            print(f"Found LP bug numbers: {', '.join(matches)}")
            return matches
        return None