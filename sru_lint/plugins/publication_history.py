from sru_lint.patches import make_filename_matcher, match_hunks
from sru_lint.plugin_base import Plugin

from debian import changelog 
from launchpadlib.launchpad import Launchpad

DEBIAN_CHANGELOG = "debian/changelog"

class PublicationHistory(Plugin):
    """Plugin to validate publication history in the patch (implementation pending)."""

    def __init__(self):
        self._cachedir = "~/.launchpadlib/cache"
        self._launchpad = Launchpad.login_anonymously("check-version", "production", self._cachedir)
        self._ubuntu = self._launchpad.distributions["ubuntu"]
        self._archive = self._ubuntu.main_archive

    def process(self, patches):
        print("PublicationHistory")

        content = match_hunks(patches, make_filename_matcher(DEBIAN_CHANGELOG))
        for k in content:
            cl = changelog.Changelog(content[k])
            
            self.check_version(cl.get_package(), cl.full_version)

    def check_version(self, package_name: str, version_to_check: str):
        print(f"check_version {package_name} {version_to_check}")

        publications = self._archive.getPublishedSources(
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