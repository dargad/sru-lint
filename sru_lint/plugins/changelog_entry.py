from sru_lint.plugin_base import Plugin
from sru_lint.patches import make_filename_matcher, match_hunks

from debian import changelog
from launchpadlib.launchpad import Launchpad


DEBIAN_CHANGELOG = "debian/changelog"

class ChangelogEntry(Plugin):
    """Plugin to check for changelog entry in the patch (implementation pending)."""
    def process(self, patches):
        print("ChangelogEntry")

        cachedir = "~/.launchpadlib/cache"
        launchpad = Launchpad.login_anonymously("check-version", "production", cachedir)
        ubuntu = launchpad.distributions["ubuntu"]
        archive = ubuntu.main_archive

        for patch in patches:
            for hunk in patch:
                print(f"Processing hunk in file: {patch.path}")
                if patch.path == DEBIAN_CHANGELOG:
                    print(f"Found changelog entry in patch: {patch.path}")
                    # Extract the content of the changelog from the hunk

        content = match_hunks(patches, make_filename_matcher(DEBIAN_CHANGELOG))

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