from sru_lint.dep3_checker import check_dep3_compliance
from sru_lint.patches import combine_added_lines, make_contains_filename_matcher, match_hunks
from sru_lint.plugin_base import Plugin
import re

from sru_lint.shared import DEBIAN_PATCHES


class PatchFormat(Plugin):
    """Checks the compliance of the patches in debian/patches to the DEP-3."""

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/patches/*")

    def process_file(self, patched_file):
        print("PatchFormat")

        content = combine_added_lines(patched_file)
        
        print(f"Found {len(content)} patches in {DEBIAN_PATCHES}")

        for patch_path, patch_content in content.items():
            if not patch_path.endswith('/series'):
                self.check_format(patch_content, patch_path)

    def check_format(self, patch_content, patch_path):
        print(f"Checking format of patch: {patch_path}")
        print(f"{check_dep3_compliance(patch_content)}")