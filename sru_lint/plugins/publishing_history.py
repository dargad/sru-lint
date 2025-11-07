from sru_lint.common.launchpad_helper import LaunchpadHelper
from sru_lint.common.parse import UNRELEASED_DISTRIBUTION, parse_distributions_field
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.feedback import Severity, SourceSpan, SourceLine
from sru_lint.common.errors import ErrorCode
from sru_lint.common.logging import get_logger
from debian import changelog


class PublishingHistory(Plugin):
    """Validates whether the version in debian/changelog has been already published in Ubuntu."""

    def __init__(self):
        super().__init__()
        self.logger = get_logger("plugins.publishing-history")

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, processed_file):
        """Process a debian/changelog file to check publishing history."""
        self.logger.info(f"Processing changelog file: {processed_file.path}")
        
        # Get the added content from the changelog file
        added_lines = processed_file.source_span.content
        if not added_lines:
            self.logger.debug(f"No added lines in {processed_file.path}")
            return
        
        # Combine the added lines into changelog content
        changelog_content = "\n".join([line.content for line in added_lines])

        self.logger.debug(f"Checking publishing history for changelog: {processed_file.path}")
        self.check_changelog_publishing_history(processed_file, changelog_content)

    def check_changelog_publishing_history(self, processed_file, changelog_content):
        """Check if versions in the changelog have already been published."""
        try:
            # Parse the changelog
            cl = changelog.Changelog(changelog_content)
            
            # Check each version in the changelog
            for entry in cl:
                package_name = entry.package
                version_to_check = entry.version
                distribution = entry.distributions

                if distribution != UNRELEASED_DISTRIBUTION:
                    self.logger.debug(f"Checking publishing history for {package_name} {version_to_check} in {distribution}")
                    self.check_version_publishing(processed_file, package_name, str(version_to_check), distribution)

        except Exception as e:
            self.logger.error(f"Error parsing changelog {processed_file.path}: {e}")
            # Create feedback for parsing errors
            source_span = SourceSpan(
                path=processed_file.path,
                start_line=1,
                start_col=1,
                end_line=1,
                end_col=1,
                content=processed_file.source_span.content,
                content_with_context=processed_file.source_span.content_with_context
            )
            
            self.create_feedback(
                message=f"Failed to parse changelog for publishing history check: {str(e)}",
                rule_id=ErrorCode.PUBLISHING_HISTORY_PARSE_ERROR,
                severity=Severity.WARNING,
                source_span=source_span
            )

    def check_version_publishing(self, processed_file, package_name: str, version_to_check: str, distribution: str):
        """Check if a specific version has been published."""
        self.logger.debug(f"Checking publication for {package_name} {version_to_check} in {distribution}")

        try:
            # Check if we have a Launchpad helper available
            if not hasattr(self, 'lp_helper') or not self.lp_helper:
                self.logger.warning("Launchpad helper not available for publishing history check")
                return
            
            # Get published sources from Launchpad
            publications = self.lp_helper.archive.getPublishedSources(
                source_name=package_name,
                exact_match=True,
                version=version_to_check
            )

            found_publications = []
            newer_publications = []

            # Check each publication - should only be exact version matches now
            for pub in publications:
                pub_version = pub.source_package_version
                pub_distro = pub.distro_series.name
                publication_info = f"{pub_distro}/{pub.pocket}/{pub.status}"
                
                distro = parse_distributions_field(distribution)
                # Check if this publication is for the same distribution
                if pub_distro == (
                    distro[0] if distro and len(distro) > 0 else distribution
                ):  # Handle cases like 'jammy-proposed' -> 'jammy'
                    # Since we filtered by version, this should be an exact match
                    found_publications.append(publication_info)
                    self.logger.info(
                        f"✅ Found {package_name} {version_to_check} in {publication_info}"
                    )

            # Separate query for newer versions to check if there are newer publications
            newer_publications_query = self.lp_helper.archive.getPublishedSources(
                source_name=package_name, exact_match=True
            )

            for pub in newer_publications_query:
                pub_version = pub.source_package_version
                pub_distro = pub.distro_series.name
                publication_info = f"{pub_distro}/{pub.pocket}/{pub.status}"

                distro = parse_distributions_field(distribution)
                # Check if this publication is for the same distribution
                if pub_distro == (
                    distro[0] if distro and len(distro) > 0 else distribution
                ):
                    # Check if published version is newer than the one we're checking
                    if pub_version != version_to_check:  # Skip the exact match we already found
                        try:
                            from debian.debian_support import Version
                            if Version(pub_version) > Version(version_to_check):
                                newer_publications.append((pub_version, publication_info))
                                self.logger.info(f"Found newer version {pub_version} in {publication_info}")
                        except Exception as version_error:
                            self.logger.debug(f"Could not compare versions {pub_version} vs {version_to_check}: {version_error}")

            # Create feedback for exact version matches
            if found_publications:
                source_span = self.find_version_line_span(processed_file, version_to_check)
                
                self.create_line_feedback(
                    message=f"Version '{version_to_check}' of '{package_name}' is already published in: {', '.join(found_publications)}",
                    rule_id=ErrorCode.PUBLISHING_HISTORY_ALREADY_PUBLISHED,
                    severity=Severity.ERROR,
                    source_span=source_span,
                    target_line_content=version_to_check,
                    doc_url=LaunchpadHelper.get_publishing_history_url(package_name)
                )
                self.logger.warning(f"Version {package_name} {version_to_check} already published")
            
            # Create feedback for newer versions
            if newer_publications:
                source_span = self.find_version_line_span(processed_file, version_to_check)
                
                newer_versions_info = []
                for newer_version, pub_info in newer_publications:
                    newer_versions_info.append(f"{newer_version} in {pub_info}")
                
                self.create_line_feedback(
                    message=f"Newer version(s) of '{package_name}' already published for {distribution}: {'; '.join(newer_versions_info)}. Current version '{version_to_check}' may be outdated.",
                    rule_id=ErrorCode.PUBLISHING_HISTORY_NEWER_VERSION_EXISTS,
                    severity=Severity.WARNING,
                    source_span=source_span,
                    target_line_content=version_to_check,
                    doc_url=LaunchpadHelper.get_publishing_history_url(package_name)
                )
                self.logger.warning(f"Newer versions of {package_name} already published for {distribution}")
            
            # Log success if no issues found
            if not found_publications and not newer_publications:
                self.logger.info(f"✅ Version '{version_to_check}' of '{package_name}' not found in publishing history and no newer versions exist (good for new uploads)")
                
        except Exception as e:
            self.logger.error(f"Error checking publishing history for {package_name} {version_to_check}: {e}")
            
            # Create feedback for API errors
            source_span = self.find_version_line_span(processed_file, version_to_check)
            
            self.create_feedback(
                message=f"Failed to check publishing history for {package_name} {version_to_check}: {str(e)}",
                rule_id=ErrorCode.PUBLISHING_HISTORY_API_ERROR,
                severity=Severity.WARNING,
                source_span=source_span
            )

    def find_version_line_span(self, processed_file, version_to_check):
        """Find the source span for a specific version in the changelog."""
        # Look for the version string in the added lines
        for line in processed_file.source_span.content:
            if version_to_check in line.content:
                # Create a source span for this line
                source_line = SourceLine(
                    content=line.content,
                    line_number=line.line_number,
                    is_added=line.is_added
                )
                
                return SourceSpan(
                    path=processed_file.path,
                    start_line=line.line_number,
                    start_col=1,
                    end_line=line.line_number,
                    end_col=len(line.content),
                    content=[source_line],
                    content_with_context=[source_line]
                )
        
        # Fallback to first line if version not found in specific line
        return SourceSpan(
            path=processed_file.path,
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            content=processed_file.source_span.content,
            content_with_context=processed_file.source_span.content_with_context
        )