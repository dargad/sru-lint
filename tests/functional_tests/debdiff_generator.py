"""
Debdiff generation utilities for sru-lint tests.
"""

import os
import re
from datetime import UTC, datetime

from . import launchpad_helper


class DebdiffGenerator:
    """Generates minimal valid debdiffs for testing."""

    @staticmethod
    def get_published_version(package, series):
        """Query the current published source version via Launchpad API."""
        lp = launchpad_helper.LaunchpadHelper()
        return lp.get_published_version(package, series)

    @staticmethod
    def bump_ubuntu_revision(version):
        """Bump the trailing revision number.

        Examples:
            1.2-1ubuntu2         -> 1.2-1ubuntu3
            1.1.2-8ubuntu1~24.04.2 -> 1.1.2-8ubuntu1~24.04.3
        """
        match = re.match(r"^(.+)(\d+)$", version)
        if match:
            return f"{match.group(1)}{int(match.group(2)) + 1}"
        raise ValueError(f"Cannot bump version: {version}")

    @classmethod
    def generate(cls, package, series, lp_bug, maintainer="Test User <test@example.com>"):
        """
        Generate a minimal valid debdiff with the latest version.

        Queries the current published version via Launchpad API and
        produces a debdiff that bumps the ubuntu revision by one.
        """
        current_version = cls.get_published_version(package, series)
        new_version = cls.bump_ubuntu_revision(current_version)
        upstream_version = current_version.rsplit("-", 1)[0]
        timestamp = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
        patch_name = f"lp{lp_bug}-test-fix.patch"

        return (
            f"diff -Nru {package}-{upstream_version}/debian/changelog"
            f" {package}-{upstream_version}/debian/changelog\n"
            f"--- {package}-{upstream_version}/debian/changelog\n"
            f"+++ {package}-{upstream_version}/debian/changelog\n"
            f"@@ -1,3 +1,9 @@\n"
            f"+{package} ({new_version}) {series}; urgency=medium\n"
            f"+\n"
            f"+  * d/p/{patch_name}: fix issue (LP: #{lp_bug})\n"
            f"+\n"
            f"+ -- {maintainer}  {timestamp}\n"
            f"+\n"
            f" {package} ({current_version}) {series}; urgency=medium\n"
            f" \n"
            f"   * previous change entry\n"
            f"diff -Nru {package}-{upstream_version}/debian/patches/"
            f"{patch_name}"
            f" {package}-{upstream_version}/debian/patches/{patch_name}\n"
            f"--- {package}-{upstream_version}/debian/patches/"
            f"{patch_name}\n"
            f"+++ {package}-{upstream_version}/debian/patches/"
            f"{patch_name}\n"
            f"@@ -0,0 +1,12 @@\n"
            f"+Description: fix issue\n"
            f"+Origin: upstream, https://github.com/example/commit/abc123\n"
            f"+Bug-Ubuntu: https://launchpad.net/bugs/{lp_bug}\n"
            f"+---\n"
            f"+ src/example.c | 1 +\n"
            f"+ 1 file changed, 1 insertion(+)\n"
            f"+\n"
            f"+--- a/src/example.c\n"
            f"++++ b/src/example.c\n"
            f"+@@ -1,3 +1,4 @@\n"
            f"+ existing line\n"
            f"++new fix line\n"
            f"diff -Nru {package}-{upstream_version}/debian/patches/series"
            f" {package}-{upstream_version}/debian/patches/series\n"
            f"--- {package}-{upstream_version}/debian/patches/series\n"
            f"+++ {package}-{upstream_version}/debian/patches/series\n"
            f"@@ -1,2 +1,3 @@\n"
            f" existing-patch.patch\n"
            f" another-patch.patch\n"
            f"+{patch_name}\n"
        )

    @classmethod
    def generate_to_file(  # pylint: disable=too-many-arguments
        cls,
        output_dir,
        filename,
        package,
        series,
        lp_bug,
        **kwargs,
    ):
        """
        Generate a debdiff and write it to a file.

        Returns the path to the written file.
        """
        debdiff = cls.generate(package, series, lp_bug, **kwargs)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(debdiff)
        return filepath
