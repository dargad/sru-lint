import re

from debian import changelog

from sru_lint.common.doc_links import DocLinks
from sru_lint.common.errors import ErrorCode
from sru_lint.common.feedback import Severity
from sru_lint.plugins.plugin_base import Plugin

UCA_VERSION_SUFFIX_RE = re.compile(r"~cloud(\d+)$")


class UCAPlugin(Plugin):
    """Checks debdiffs targeted at the Ubuntu Cloud Archive."""

    def register_file_patterns(self):
        self.add_file_pattern("debian/changelog")

    def process_file(self, processed_file) -> None:
        self.logger.info("Processing UCA changelog entry")

        source_span = processed_file.source_span
        added_content = "\n".join(line.content for line in source_span.lines_added)
        if not added_content.strip():
            return

        try:
            cl = changelog.Changelog(added_content)
        except Exception as e:
            self.logger.error(f"Failed to parse changelog: {e}")
            return

        version = str(cl.version) if cl.version is not None else ""
        if "~cloud" not in version:
            self.logger.debug(f"Version '{version}' has no ~cloud suffix; not a UCA debdiff")
            return

        self.check_version_suffix(source_span, version)
        self.check_distribution(source_span, str(cl.distributions))
        self.check_bug_targeting(source_span, cl, str(cl.distributions))

    def check_version_suffix(self, source_span, version: str) -> None:
        """Ensure the version ends in ~cloudN where N is a non-negative integer."""
        if UCA_VERSION_SUFFIX_RE.search(version):
            return
        self.create_line_feedback(
            message=(
                f"UCA version '{version}' must end in '~cloudN' where N is a non-negative integer"
            ),
            rule_id=ErrorCode.UCA_INVALID_VERSION_SUFFIX,
            severity=Severity.ERROR,
            source_span=source_span,
            target_line_content=version,
            doc_url=DocLinks.VERSION_STRING_FORMAT,
        )

    def check_distribution(self, source_span, distribution: str) -> None:
        """Ensure the distribution is a valid <series>-<openstack> UCA pocket."""
        is_valid, reason = self.lp_helper.is_valid_uca_distribution(distribution)
        if is_valid:
            return

        if reason == ErrorCode.UCA_UNKNOWN_OPENSTACK_RELEASE:
            message = f"Unknown OpenStack release in UCA distribution '{distribution}'"
        elif reason == ErrorCode.UCA_INVALID_PAIRING:
            message = (
                f"UCA distribution '{distribution}' is not a valid "
                f"Ubuntu series / OpenStack release pairing"
            )
        else:
            message = (
                f"UCA distribution '{distribution}' is not of the form "
                f"<ubuntu-series>-<openstack-release>"
            )

        self.create_line_feedback(
            message=message,
            rule_id=reason,
            severity=Severity.ERROR,
            source_span=source_span,
            target_line_content=distribution,
            doc_url=DocLinks.LIST_OF_UBUNTU_RELEASES,
        )

    def check_bug_targeting(self, source_span, cl, distribution: str) -> None:
        """Ensure LP bugs are targeted at cloud-archive/<openstack-release>."""
        if "-" not in distribution:
            return
        _, _, openstack = distribution.rpartition("-")
        if not openstack:
            return

        lpbugs = self.lp_helper.extract_lp_bugs(str(cl))
        for lpbug in lpbugs:
            has_project, has_series = self.lp_helper.get_uca_bug_targeting(lpbug, openstack)
            if not has_project:
                self.create_line_feedback(
                    message=(
                        f"Bug LP: #{lpbug} has no task on the cloud-archive Launchpad project"
                    ),
                    rule_id=ErrorCode.UCA_BUG_NOT_TARGETED,
                    severity=Severity.WARNING,
                    source_span=source_span,
                    target_line_content=f"LP: #{lpbug}",
                )
            elif not has_series:
                self.create_line_feedback(
                    message=(f"Bug LP: #{lpbug} has no task for cloud-archive/{openstack}"),
                    rule_id=ErrorCode.UCA_BUG_SERIES_NOT_TARGETED,
                    severity=Severity.WARNING,
                    source_span=source_span,
                    target_line_content=f"LP: #{lpbug}",
                )
