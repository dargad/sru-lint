from sru_lint.plugin_base import Plugin
from sru_lint.patches import make_filename_matcher, match_hunks

from debian import changelog


DEBIAN_CHANGELOG = "debian/changelog"

class ChangelogEntry(Plugin):
    """Plugin to check for changelog entry in the patch (implementation pending)."""
    def process(self, patches):
        print("ChangelogEntry")

        content = match_hunks(patches, make_filename_matcher(DEBIAN_CHANGELOG))

        for k in content:
            cl = changelog.Changelog(content[k])
            print(f"{cl.get_package()}:{cl.distributions}:{cl.full_version}")
            print(f"Author: {cl.author} Date: {cl.date}")

            self.search_for_lpbug(str(cl))

    def search_for_lpbug(self, changelog: str):
        print("Searching for LP bug number in the changelog")