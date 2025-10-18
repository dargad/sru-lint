from sru_lint.common.deb_changelog import DebianChangelogHeader, parse_header
from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.patches import combine_added_lines

from debian import changelog
from debian.debian_support import Version


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

        feedback = []

        content = combine_added_lines(patched_file)
        content_with_context = combine_added_lines(patched_file, include_context=True)

        changelog_headers = []
        for k in content_with_context:
            file_content = content_with_context[k]
            for line in file_content.splitlines():
                try:
                    header = parse_header(line)
                    changelog_headers.append(header)
                except ValueError:
                    continue

        if len(changelog_headers) > 1:
            try:
                self.assert_version_order(changelog_headers)
                print("✅ Changelog version order is correct.")
            except AssertionError as e:
                print(f"❌ Changelog version order is incorrect: {e}")

        print(f"Found {len(changelog_headers)} changelog headers: {changelog_headers}")

        for k in content:
            cl = changelog.Changelog(content[k])

            if not self.check_distribution(cl.distributions):
                feedback.append(FeedbackItem(
                    message=f"Invalid distribution '{cl.distributions}'",
                    span=SourceSpan(
                        path=patched_file.path,
                        start_line=1,
                        start_col=1,
                        end_line=1,
                        end_col=1,
                        start_offset=0,
                        end_offset=0
                    ),
                    rule_id="CHANGELOG001",
                    severity=Severity.ERROR
                ))
                print(f"❌ Invalid distribution in changelog: '{cl.distributions}'")

            print(f"{cl.get_package()}:{cl.distributions}:{cl.full_version}")
            print(f"Author: {cl.author} Date: {cl.date}")

            # Extract LP bug numbers using the helper
            lpbugs = self.lp_helper.extract_lp_bugs(str(cl))

            if lpbugs:
                for lpbug in lpbugs:
                    print(f"LP Bug: LP: #{lpbug}")
                    
                    is_targeted = self.lp_helper.is_bug_targeted(lpbug, cl.get_package(), cl.distributions)
                    if not is_targeted:
                        feedback.append(FeedbackItem(
                            message=f"Bug LP: #{lpbug} is not targeted at {cl.get_package()} and {cl.distributions}",
                            span=SourceSpan(
                                path=patched_file.path,
                                start_line=1,
                                start_col=1,
                                end_line=1,
                                end_col=1,
                                start_offset=0,
                                end_offset=0
                            ),
                            rule_id="CHANGELOG002",
                            severity=Severity.ERROR
                        ))
                        print(f"Bug {lpbug} is NOT targeted at {cl.get_package()} and {cl.distributions}")
        return feedback

    def check_distribution(self, distributions):
        """Check if the distribution field in the changelog is valid."""
        return self.lp_helper.is_valid_distribution(distributions)

    def assert_version_order(self, headers: list[DebianChangelogHeader]):
        for idx, (prev, curr) in enumerate(zip(headers, headers[1:])):
            v_prev = Version(prev.version)
            v_curr = Version(curr.version)
            if not (v_prev > v_curr):
                raise AssertionError(
                    f"Version order error at index {idx}: "
                    f"{prev.version} <= {curr.version}"
                )