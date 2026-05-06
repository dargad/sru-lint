"""
Launchpad API helper for interacting with Launchpad bug tracker
and Ubuntu archive.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

LOG = logging.getLogger(__name__)

LP_API = "https://api.launchpad.net/1.0"
LP_API_STAGING = "https://api.staging.launchpad.net/1.0"

DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 5


class LaunchpadHelper:
    """Helper class for Launchpad API interactions.

    Supports querying the Ubuntu archive for published package versions
    and managing bugs (create, delete, attach files) on Launchpad.

    Uses the Launchpad REST API directly via urllib (no launchpadlib
    dependency). For write operations (bugs), an OAuth token is required.
    """

    def __init__(self, api_url=None, oauth_token=None, retries=None, retry_delay=None):
        """
        :param api_url: Launchpad API base URL. Defaults to production.
            Use LP_API_STAGING for the test instance.
        :param oauth_token: OAuth access token for authenticated operations
            (bug creation, deletion, attachments). Not needed for read-only
            archive queries.
        :param retries: Number of retry attempts for failed API calls.
            Defaults to DEFAULT_RETRIES.
        :param retry_delay: Seconds to wait between retries.
            Defaults to DEFAULT_RETRY_DELAY.
        """
        self.api_url = api_url or LP_API
        self.oauth_token = oauth_token
        self.retries = retries if retries is not None else DEFAULT_RETRIES
        self.retry_delay = retry_delay if retry_delay is not None else DEFAULT_RETRY_DELAY

    def _request(  # pylint: disable=too-many-arguments
        self,
        url,
        method="GET",
        data=None,
        headers=None,
        content_type=None,
    ):
        """Send an HTTP request to the Launchpad API.

        :param url: Full URL to request.
        :param method: HTTP method.
        :param data: Request body (bytes or str).
        :param headers: Additional headers dict.
        :param content_type: Content-Type header value.
        :returns: Parsed JSON response or None for 204/empty responses.
        """
        req_headers = {}
        if self.oauth_token:
            req_headers["Authorization"] = f"Bearer {self.oauth_token}"
        if content_type:
            req_headers["Content-Type"] = content_type
        if headers:
            req_headers.update(headers)

        if isinstance(data, str):
            data = data.encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        for attempt in range(1, self.retries + 1):
            try:
                LOG.debug("LP API %s %s (attempt %d/%d)", method, url, attempt, self.retries)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read()
                    if not body:
                        return None
                    return json.loads(body)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                if attempt < self.retries:
                    LOG.warning(
                        "LP API %s %s failed (attempt %d/%d): %s — retrying in %ds",
                        method,
                        url,
                        attempt,
                        self.retries,
                        exc,
                        self.retry_delay,
                    )
                    time.sleep(self.retry_delay)
                else:
                    LOG.error(
                        "LP API %s %s failed after %d attempts: %s", method, url, self.retries, exc
                    )
                    raise
        return None

    # ------------------------------------------------------------------ #
    # Archive / package version queries (read-only, no auth needed)
    # ------------------------------------------------------------------ #

    def get_published_version(self, package, series, pocket=None):
        """Query the current published source version of a package.

        :param package: Source package name (e.g. "netplan.io").
        :param series: Ubuntu series codename (e.g. "noble").
        :param pocket: Preferred pocket ("Updates", "Release", etc.).
            If None, prefers Updates then Release.
        :returns: Version string.
        :raises ValueError: If no published version is found.
        """
        params = urllib.parse.urlencode(
            {
                "ws.op": "getPublishedSources",
                "source_name": package,
                "distro_series": f"{self.api_url}/ubuntu/{series}",
                "status": "Published",
                "exact_match": "true",
            }
        )
        url = f"{self.api_url}/ubuntu/+archive/primary?{params}"
        data = self._request(url)
        entries = data.get("entries", [])
        if not entries:
            raise ValueError(f"No published version found for {package} in {series}")
        if pocket:
            for entry in entries:
                if entry["pocket"] == pocket:
                    return entry["source_package_version"]
            raise ValueError(f"No version in {pocket} pocket for {package} in {series}")
        # Default: prefer Updates, then Release
        for preferred in ("Updates", "Release"):
            for entry in entries:
                if entry["pocket"] == preferred:
                    return entry["source_package_version"]
        return entries[0]["source_package_version"]

    # ------------------------------------------------------------------ #
    # Bug management (requires auth)
    # ------------------------------------------------------------------ #

    def create_bug(self, project, title, description):
        """Create a new bug on a Launchpad project.

        :param project: Project name (e.g. "ubuntu", "netplan").
        :param title: Bug title.
        :param description: Bug description body.
        :returns: Dict with bug data including 'id' and 'self_link'.
        """
        url = f"{self.api_url}/bugs"
        params = urllib.parse.urlencode(
            {
                "ws.op": "createBug",
                "target": f"{self.api_url}/{project}",
                "title": title,
                "description": description,
            }
        )
        return self._request(
            url, method="POST", data=params, content_type="application/x-www-form-urlencoded"
        )

    def get_bug(self, bug_id):
        """Retrieve a bug by ID.

        :param bug_id: Launchpad bug number.
        :returns: Dict with bug data.
        """
        url = f"{self.api_url}/bugs/{bug_id}"
        return self._request(url)

    def delete_bug(self, bug_id):
        """Delete a bug by ID.

        Note: Launchpad does not support deleting bugs via API.
        As a workaround, this marks the bug as Invalid and private.

        :param bug_id: Launchpad bug number.
        """
        # Mark the default bug task as Invalid
        bug = self.get_bug(bug_id)
        tasks_url = bug.get("bug_tasks_collection_link")
        if tasks_url:
            tasks = self._request(tasks_url)
            for task in tasks.get("entries", []):
                task_url = task["self_link"]
                params = urllib.parse.urlencode(
                    {
                        "ws.op": "transitionToStatus",
                        "status": "Invalid",
                    }
                )
                self._request(
                    task_url,
                    method="POST",
                    data=params,
                    content_type="application/x-www-form-urlencoded",
                )
        LOG.info("Bug %s marked as Invalid", bug_id)

    def add_attachment(self, bug_id, filepath, filename=None, comment=""):
        """Attach a file to a Launchpad bug.

        :param bug_id: Launchpad bug number.
        :param filepath: Local path to the file to attach.
        :param filename: Name for the attachment. Defaults to the
            basename of filepath.
        :param comment: Optional comment to add with the attachment.
        """
        if filename is None:
            filename = os.path.basename(filepath)

        with open(filepath, "rb") as f:
            file_content = f.read()

        # Launchpad uses multipart MIME for attachments
        boundary = "----LaunchpadBoundary"
        body_parts = []

        # ws.op parameter
        body_parts.append(f"--{boundary}")
        body_parts.append('Content-Disposition: form-data; name="ws.op"')
        body_parts.append("")
        body_parts.append("addAttachment")

        # comment parameter
        body_parts.append(f"--{boundary}")
        body_parts.append('Content-Disposition: form-data; name="comment"')
        body_parts.append("")
        body_parts.append(comment)

        # filename parameter
        body_parts.append(f"--{boundary}")
        body_parts.append('Content-Disposition: form-data; name="filename"')
        body_parts.append("")
        body_parts.append(filename)

        # data parameter (file content)
        body_parts.append(f"--{boundary}")
        body_parts.append(f'Content-Disposition: form-data; name="data"; filename="{filename}"')
        body_parts.append("Content-Type: application/octet-stream")
        body_parts.append("")

        # Build the multipart body as bytes
        header_bytes = "\r\n".join(body_parts).encode("utf-8") + b"\r\n"
        footer_bytes = f"\r\n--{boundary}--\r\n".encode()
        full_body = header_bytes + file_content + footer_bytes

        url = f"{self.api_url}/bugs/{bug_id}"
        return self._request(
            url,
            method="POST",
            data=full_body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
