from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.patches import combine_added_lines
from sru_lint.common.launchpad_helper import LaunchpadHelper

from debian import changelog


class ChangelogEntry(Plugin):
    """Checks the changelog entry."""

    def __init__(self):
        """Initialize the plugin and Launchpad helper."""
        super().__init__()
        self.lp_helper = LaunchpadHelper()

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
                                start_line=patched_file[0].target_start,
                                start_col=1,
                                end_line=patched_file[0].target_start + patched_file[0].target_length,
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
