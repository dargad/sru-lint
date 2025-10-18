import re
from os.path import expanduser
from debian import changelog

from sru_lint.common.patches import combine_added_lines, make_end_filename_matcher, match_hunks
from sru_lint.common.shared import DEBIAN_CHANGELOG, parse_distributions_field, REVIEW_STATES
from sru_lint.plugins.plugin_base import Plugin

class UploadQueue(Plugin):
    """Checks if the version in debian/changelog is already in the upload queue for review."""

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, patched_file):
        print("UploadQueue")

        content = combine_added_lines(patched_file)
        
        for k in content:
            cl = changelog.Changelog(content[k])
            suites = parse_distributions_field(str(cl.distributions))
            self.check_upload_queue(cl.get_package(), suites, cl.full_version)

    def check_upload_queue(self, package_name: str, suites: list[str], version_to_check: str):
        print(f"check_upload_queue {package_name} {suites} {version_to_check}")

        for suite in suites:
            base = suite.split("-", 1)[0]             # 'jammy-proposed' -> 'jammy'
            ds = self.lp_helper.ubuntu.getSeries(name_or_version=base)  # IDistroSeries

            # NOTE: getPackageUploads is on *distro series*, with 'archive' as a filter.
            uploads = ds.getPackageUploads(
                archive=self.lp_helper.archive,
                name=package_name,        # package or file name; pair with exact_match if desired
                exact_match=True,         # optional; narrows 'name' to exact package
            )

            waiting = [u for u in uploads if getattr(u, "status", None) in REVIEW_STATES]
            if waiting:
                for u in waiting:
                    print(f"✅ {package_name}: {ds.name} / {u.pocket} / {u.status} ({u.self_link})")
            else:
                print(f"— no review-queue uploads for {package_name} in {ds.name}")
