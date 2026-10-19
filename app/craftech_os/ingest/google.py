"""Read-only access to Google Drive, Drive Activity and Sheets, with retries on quota and server
errors."""

import os
import time
from datetime import datetime

import httplib2
from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.activity.readonly",
]
SPREADSHEET = "application/vnd.google-apps.spreadsheet"
ACTIVITY_PAGE_SIZE = 100
MAX_RETRIES = 6
HTTP_TIMEOUT_S = 300
# A tab's grid is JSON that gzip shrinks more than httplib2's default 100x ratio allows.
# Google is the only peer, so the ratio check is off and the total size stays capped.
DECODE_LIMIT_BYTES = 1 << 30
TAB_PROPERTIES = "properties(sheetId,title,hidden,gridProperties(rowCount,columnCount))"
CELL_FIELDS = (
    "effectiveValue,formattedValue,userEnteredValue,effectiveFormat(backgroundColor,numberFormat)"
)
GRID_FIELDS = (
    f"sheets({TAB_PROPERTIES},merges,data(startRow,startColumn,rowData(values({CELL_FIELDS}))))"
)


class GoogleError(Exception):
    pass


def status(error: HttpError) -> int:
    return int(error.resp.status)


class Google:
    """The few Drive, Drive Activity and Sheets calls Craftech OS makes. Every call is read-only.

    Each method takes on_retry(call=..., status=..., attempt=..., wait_s=...), called
    before waiting to retry a 429 or 5xx answer.
    """

    def __init__(self, drive, sheets, sleep=time.sleep, activity=None):
        self.drive, self.sheets, self.sleep, self.activity = drive, sheets, sleep, activity

    @classmethod
    def from_environment(cls) -> "Google":
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not path:
            raise GoogleError("GOOGLE_APPLICATION_CREDENTIALS is not set")
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

        def http():
            return AuthorizedHttp(
                creds,
                httplib2.Http(
                    timeout=HTTP_TIMEOUT_S,
                    decode_limit_ratio=0,
                    decode_limit_hard=DECODE_LIMIT_BYTES,
                ),
            )

        return cls(
            build("drive", "v3", http=http(), cache_discovery=False),
            build("sheets", "v4", http=http(), cache_discovery=False),
            activity=build("driveactivity", "v2", http=http(), cache_discovery=False),
        )

    def _execute(self, call: str, request, on_retry):
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                return request.execute()
            except HttpError as e:
                if attempt > MAX_RETRIES or not (status(e) == 429 or status(e) >= 500):
                    raise
                wait_s = 2 ** (attempt - 1)
                on_retry(call=call, status=status(e), attempt=attempt, wait_s=wait_s)
                self.sleep(wait_s)

    def find_spreadsheets(self, title: str, on_retry) -> list[str]:
        """Ids of the spreadsheets whose name is exactly title, in any shared drive."""
        quoted = title.replace("\\", "\\\\").replace("'", "\\'")
        request = self.drive.files().list(
            q=f"name = '{quoted}' and mimeType = '{SPREADSHEET}'",
            corpora="allDrives",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id,name)",
            pageSize=100,
        )
        files = self._execute("drive.files.list", request, on_retry).get("files", [])
        return [f["id"] for f in files if f.get("name") == title]

    def version(self, file_id: str, on_retry) -> dict:
        """{'version': '66931', 'modifiedTime': '2026-10-18T12:00:00.000Z'}"""
        request = self.drive.files().get(
            fileId=file_id, fields="version,modifiedTime", supportsAllDrives=True
        )
        return self._execute("drive.files.get", request, on_retry)

    def tabs(self, file_id: str, on_retry) -> list[dict]:
        """Properties of every tab, hidden ones included, without cell data."""
        request = self.sheets.spreadsheets().get(
            spreadsheetId=file_id, includeGridData=False, fields=f"sheets.{TAB_PROPERTIES}"
        )
        sheets = self._execute("sheets.get", request, on_retry).get("sheets", [])
        return [s["properties"] for s in sheets]

    def grid(self, file_id: str, tab_title: str, on_retry) -> dict:
        """The whole tab: properties, merges and cell data, as the API returns it."""
        request = self.sheets.spreadsheets().get(
            spreadsheetId=file_id,
            ranges=["'" + tab_title.replace("'", "''") + "'"],
            includeGridData=True,
            fields=GRID_FIELDS,
        )
        sheets = self._execute("sheets.get", request, on_retry).get("sheets", [])
        if len(sheets) != 1:
            raise GoogleError(f"expected one tab in the answer, got {len(sheets)}")
        return sheets[0]

    def activities(self, file_id: str, on_retry, since: datetime | None = None) -> list[dict]:
        """Every Drive Activity of one file, newest first, through all the pages.

        With since, only the activity at that moment or later.
        """
        body = {"itemName": f"items/{file_id}", "pageSize": ACTIVITY_PAGE_SIZE}
        if since is not None:
            body["filter"] = f'time >= "{since.isoformat()}"'
        found = []
        while True:
            request = self.activity.activity().query(body=body)
            page = self._execute("driveactivity.query", request, on_retry)
            found += page.get("activities", [])
            if not page.get("nextPageToken"):
                return found
            body = {**body, "pageToken": page["nextPageToken"]}
