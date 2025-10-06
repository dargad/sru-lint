from sru_lint.common.launchpad_helper import get_launchpad_helper
from sru_lint.common.patches import combine_added_lines
from sru_lint.plugins.plugin_base import Plugin

from debian import changelog 


class PublicationHistory(Plugin):
    """Validates whether the version in debian/changelog has been already published in Ubuntu."""

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, patched_file):
        print("PublicationHistory")

        content = combine_added_lines(patched_file)

        for k in content:
            cl = changelog.Changelog(content[k])
            
            self.check_version(cl.get_package(), cl.full_version)

    def check_version(self, package_name: str, version_to_check: str):
        print(f"check_version {package_name} {version_to_check}")

        publications = self.lp_helper.archive.getPublishedSources(
            source_name=package_name,
            exact_match=True
        )

        found = False

        for pub in publications:
            if pub.source_package_version == version_to_check:
                print(f"✅ Found in {pub.distro_series.name} / {pub.pocket} / {pub.status}")
                found = True

        if not found:
            print(f"❌ Version '{version_to_check}' of '{package_name}' was NOT found in publishing history.")