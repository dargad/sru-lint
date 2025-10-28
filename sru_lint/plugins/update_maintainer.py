from sru_lint.common.debian.changelog import parse_header
from sru_lint.common.errors import ErrorCode
from sru_lint.common.feedback import Severity
from sru_lint.common.logging import get_logger
from sru_lint.plugins.plugin_base import Plugin

from debian.deb822 import Deb822
from debian.debian_support import Version


class UpdateMaintainer(Plugin):
    """Checks whether the maintainer information in debian/control is up to date."""

    MAINTAINER_FIELD = "Maintainer"
    MAINTAINER_EXPECTED = "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>"
    ORIGINAL_MAINTAINER_FIELD = "XSBC-Original-Maintainer"
    UBUNTU_IN_DEBIAN_REVISION = "ubuntu"
    UBUNTU_EMAIL_DOMAIN = "ubuntu.com"

    def __init__(self):
        super().__init__()
        self.logger = get_logger("plugins.update-maintainer")
        self.control_checked = False
        self.expect_control = False
        self.changelog = None
        self.version = None

    def register_file_patterns(self):
        """Register that we want to check debian/changelog and debian/control files."""
        self.add_file_pattern("debian/changelog")
        self.add_file_pattern("debian/control")

    def process_file(self, processed_file):
        """Process a debian/control or debian/changelog file to check maintainer info."""
        self.logger.info(f"Processing file for maintainer update: {processed_file.path}")
        
        if processed_file.path.endswith("debian/changelog"):
            self.process_changelog(processed_file)
        elif processed_file.path.endswith("debian/control"):
            self.process_control(processed_file)

    def process_control(self, processed_file):
        """Process a debian/control file to check maintainer info."""
        self.logger.info(f"Checking debian/control for maintainer update: {processed_file.path}")
        content = "\n".join([line.content for line in processed_file.source_span.lines_with_context])
        control_data = Deb822(content)
        maintainer = original_maintainer = None

        if self.MAINTAINER_FIELD in control_data:
            self.logger.debug(f"Found {self.MAINTAINER_FIELD} in control file")
            maintainer = control_data[self.MAINTAINER_FIELD]

        if self.is_ubuntu_maintainer(maintainer):
            self.logger.info(f"Maintainer is set to Ubuntu address in {processed_file.path}: {maintainer}")
            self.control_checked = True

    def is_ubuntu_maintainer(self, maintainer: str) -> bool:
        """Check if the maintainer string indicates Ubuntu Developers."""
        if maintainer == self.MAINTAINER_EXPECTED:
            return True
        if maintainer and self.UBUNTU_EMAIL_DOMAIN in maintainer:
            return True
        return False

    def process_changelog(self, processed_file):
        """Process a debian/changelog file to determine if maintainer update is needed."""
        self.logger.info(f"Checking changelog for maintainer update need: {processed_file.path}")
        self.changelog = processed_file
        headers = self.find_changelog_headers(processed_file)
        self.logger.debug(f"Changelog headers found: {headers}")
        if self.is_update_maintainer_needed(headers):
            self.logger.info(f"Maintainer update needed for {processed_file.path}")
            self.expect_control = True
            version_string = headers[0].version
            version = Version(version_string)
            deb_rev = version.debian_revision
            self.version = deb_rev

    def is_update_maintainer_needed(self, headers):
        """Determine if the maintainer update is needed based on changelog headers."""
        if headers and len(headers) > 1:
            return self.is_ubuntu_version(headers[0]) and not self.is_ubuntu_version(headers[1])
        return False
    
    def is_ubuntu_version(self, header):
        """Check if the version in the changelog header is an Ubuntu version."""
        try:
            version = Version(header.version)
            return self.UBUNTU_IN_DEBIAN_REVISION in version.debian_revision
        except Exception as e:
            self.logger.error(f"Error parsing version '{header.version}': {e}")
            return False

    def find_changelog_headers(self, processed_file):
        """Extract changelog headers from the debian/changelog file."""
        headers = []

        for line in processed_file.source_span.lines_with_context:
            self.logger.debug(f"Processing line in {processed_file.path}: {line.content}")
            try:
                header = parse_header(line.content)
                if header:
                    headers.append(header)
            except Exception as e:
                self.logger.error(f"Error parsing line in {processed_file.path}: {e}")

        self.logger.debug(f"Found headers: {headers}")
        return headers

    def post_process(self):
        """Perform any final checks or cleanup after all files have been processed."""
        self.logger.info(f"Post-processing after maintainer update checks control_checked={self.control_checked}, expect_control={self.expect_control}")
        if not self.control_checked and self.expect_control:
            self.logger.warning("debian/control file was expected but not found for maintainer update check.")
            self.create_line_feedback(
                message="Version number suggests Ubuntu changes, but Maintainer: does not have Ubuntu address",
                rule_id=ErrorCode.CONTROL_MAINTAINER_NOT_UPDATED,
                severity=Severity.WARNING,
                doc_url="https://documentation.ubuntu.com/project/how-ubuntu-is-made/concepts/debian-directory/#the-control-file",
                source_span=self.changelog.source_span,
                target_line_content=self.version
                )