import re
from os.path import expanduser
from launchpadlib.launchpad import Launchpad
from debian import changelog

from sru_lint.patches import make_filename_matcher, match_hunks
from sru_lint.plugin_base import Plugin
from sru_lint.plugins.changelog_entry import DEBIAN_CHANGELOG
from sru_lint.shared import parse_distributions_field, REVIEW_STATES

class UploadQueue(Plugin):
    def __init__(self):
        cache_dir = expanduser("~/.cache/launchpadlib-devel")
        self._lp = Launchpad.login_anonymously(
            "check-version", "production", version="devel"
        )
        self._ubuntu = self._lp.distributions["ubuntu"]
        self._archive = self._ubuntu.main_archive

    def process(self, patches):
        print("UploadQueue")
        content = match_hunks(patches, make_filename_matcher(DEBIAN_CHANGELOG))
        for k in content:
            cl = changelog.Changelog(content[k])
            suites = parse_distributions_field(str(cl.distributions))
            self.check_upload_queue(cl.get_package(), suites, cl.full_version)

    def check_upload_queue(self, package_name: str, suites: list[str], version_to_check: str):
        print(f"check_upload_queue {package_name} {suites} {version_to_check}")

        for suite in suites:
            base = suite.split("-", 1)[0]             # 'jammy-proposed' -> 'jammy'
            ds = self._ubuntu.getSeries(name_or_version=base)  # IDistroSeries

            # NOTE: getPackageUploads is on *distro series*, with 'archive' as a filter.
            uploads = ds.getPackageUploads(
                archive=self._archive,
                name=package_name,        # package or file name; pair with exact_match if desired
                exact_match=True,         # optional; narrows 'name' to exact package
            )

            waiting = [u for u in uploads if getattr(u, "status", None) in REVIEW_STATES]
            if waiting:
                for u in waiting:
                    print(f"✅ {package_name}: {ds.name} / {u.pocket} / {u.status} ({u.self_link})")
            else:
                print(f"— no review-queue uploads for {package_name} in {ds.name}")
