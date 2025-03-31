#!/usr/bin/env python3

import os
import io
import re
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials


class CrosswordSyncer:
    """Handles syncing NYT crossword puzzles between Google Drive and iCloud."""

    # Constants for filename patterns
    ISO_FORMAT_PATTERNS = (
        r"^\d{4}-\d{2}-\d{2}_[A-Za-z]+_Puzzle\.pdf$",
        r"^\d{4}-\d{2}-\d{2}_[A-Za-z]+_Solution\.pdf$",
    )

    SHORT_FORMAT_PATTERNS = (
        r"^\d{2}-\d{2}-\d{2}-[A-Z]{3}\sPuzzle\.pdf$",
        r"^\d{2}-\d{2}-\d{2}-[A-Z]{3}\sSolution\.pdf$",
    )

    def __init__(self, day_of_week: int = 6, dry_run: bool = False):
        """Initialize the CrosswordSyncer.

        Args:
            dry_run: If True, no actual file operations are performed
        """
        # Load environment variables
        load_dotenv()

        # Set up logging
        self._configure_logging()

        # Load config
        self.icloud_path = os.path.expanduser(os.getenv("ICLOUD_PATH", ""))
        self.service_account_file = os.path.expanduser(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        )
        self.folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
        self.scopes = ["https://www.googleapis.com/auth/drive"]
        self.day_of_week = day_of_week
        self.dry_run = dry_run

        # Validate config
        self._validate_config()

        # Set up paths
        self.crosswords_dir = Path(self.icloud_path) / "nyt-crosswords"
        self.crosswords_dir.mkdir(parents=True, exist_ok=True)

        # Statistics for operations performed
        self.stats = {"renamed": 0, "downloaded": 0, "skipped": 0, "errors": 0}

    def _configure_logging(self):
        """Configure logging format and level."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def _validate_config(self):
        """Ensure all required configuration variables are present."""
        missing = []
        if not self.icloud_path:
            missing.append("ICLOUD_PATH")
        if not self.service_account_file:
            missing.append("GOOGLE_SERVICE_ACCOUNT_FILE")
        if not self.folder_id:
            missing.append("GOOGLE_FOLDER_ID")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Check your .env file."
            )

        # Check if service account file exists
        if not os.path.isfile(self.service_account_file):
            raise FileNotFoundError(
                f"Service account file not found: {self.service_account_file}"
            )

    def authenticate_google_drive(self) -> Any:
        """Authenticate with Google Drive API and return a service instance.

        Returns:
            A Google Drive service object

        Raises:
            Exception: If authentication fails
        """
        try:
            credentials = Credentials.from_service_account_file(
                self.service_account_file, scopes=self.scopes
            )
            return build("drive", "v3", credentials=credentials)
        except Exception as e:
            self.logger.error(f"Google Drive authentication failed: {e}")
            self.stats["errors"] += 1
            raise

    def list_files_in_drive_folder(self, service: Any) -> List[Dict[str, str]]:
        """List all files in the configured Google Drive folder.

        Args:
            service: An authenticated Google Drive service object

        Returns:
            A list of dictionaries containing file information
        """
        try:
            query = f"'{self.folder_id}' in parents and trashed = false"
            results = (
                service.files()
                .list(q=query, fields="files(id, name, modifiedTime)")
                .execute()
            )
            return results.get("files", [])
        except HttpError as e:
            self.logger.error(
                f"Error listing files in Google Drive folder: {e}"
            )
            self.stats["errors"] += 1
            return []

    def rename_file_in_drive(
        self, service: Any, file_id: str, new_name: str
    ) -> Optional[Dict[str, str]]:
        """Rename a file in Google Drive.

        Args:
            service: An authenticated Google Drive service object
            file_id: The ID of the file to rename
            new_name: The new name for the file

        Returns:
            The updated file metadata or None if the operation failed
        """
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would rename file to: {new_name}")
                return {"id": file_id, "name": new_name}

            updated_file = (
                service.files()
                .update(
                    fileId=file_id, body={"name": new_name}, fields="id, name"
                )
                .execute()
            )
            self.logger.info(
                f"Renamed [ID: {updated_file['id']}] >> '{updated_file['name']}'"
            )
            self.stats["renamed"] += 1
            return updated_file
        except HttpError as e:
            self.logger.error(f"Failed to rename file: {e}")
            self.stats["errors"] += 1
            return None

    def list_local_files(self) -> List[str]:
        """Get a list of all files in the local crosswords directory.

        Returns:
            A list of filenames
        """
        return [f.name for f in self.crosswords_dir.glob("**/*") if f.is_file()]

    def format_date_long_to_short(self, long_date: str) -> str:
        """Convert a date from YYYY-MM-DD to MM-DD-YY format.

        Args:
            long_date: A date string in YYYY-MM-DD format

        Returns:
            The date in MM-DD-YY format
        """
        try:
            long_date_dt = datetime.strptime(long_date, "%Y-%m-%d")
            return long_date_dt.strftime("%m-%d-%y")
        except ValueError as e:
            self.logger.error(f"Invalid date format: {long_date}. Error: {e}")
            self.stats["errors"] += 1
            return long_date

    def format_filename_old_to_new(self, old_filename: str) -> Tuple[str, bool]:
        """Convert old filename format to new format.

        Args:
            old_filename: A filename in the old format (YYYY-MM-DD_Day_Type.pdf)

        Returns:
            Tuple containing (new_filename, changed) where changed is True if the
            filename was modified
        """
        try:
            # Extract components from old filename
            match = re.match(
                r"^(\d{4}-\d{2}-\d{2})_([A-Za-z]+)_(.+\.pdf)$", old_filename
            )
            if not match:
                return old_filename, False

            long_date, day, content = match.groups()
            short_date = self.format_date_long_to_short(long_date)
            short_day = day[:3].upper()
            new_filename = f"{short_date}-{short_day} {content}"

            return new_filename, old_filename != new_filename
        except Exception as e:
            self.logger.warning(
                f"Filename '{old_filename}' could not be converted: {e}"
            )
            self.stats["errors"] += 1
            return old_filename, False

    def is_iso_format(self, filename: str) -> bool:
        """Check if a filename follows the ISO 8601 date format.

        Args:
            filename: The filename to check

        Returns:
            True if the filename is in ISO format, False otherwise
        """
        for pattern in self.ISO_FORMAT_PATTERNS:
            if re.match(pattern, filename):
                return True

        for pattern in self.SHORT_FORMAT_PATTERNS:
            if re.match(pattern, filename):
                return False

        return False

    def day_of_week_string_to_index(self, day_of_week):
        return {
            0: "MON",
            1: "TUE",
            2: "WED",
            3: "THU",
            4: "FRI",
            5: "SAT",
            6: "SUN",
        }.get(day_of_week)

    def download_file(self, service: Any, file_id: str, filename: str) -> bool:
        """Download a file from Google Drive to the local directory.

        Args:
            service: An authenticated Google Drive service object
            file_id: The ID of the file to download
            filename: The name to save the file as

        Returns:
            True if the download was successful, False otherwise
        """
        dst = self.crosswords_dir / filename

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would download file to: {dst}")
            return True

        try:
            request = service.files().get_media(fileId=file_id)
            with io.FileIO(dst, "wb") as file:
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    self.logger.info(
                        f"Downloading {filename}: {int(status.progress() * 100)}%"
                    )
            self.stats["downloaded"] += 1
            return True
        except HttpError as e:
            self.logger.error(f"Failed to download file {filename}: {e}")
            self.stats["errors"] += 1
            return False

    def process_drive_files(self, service: Any) -> None:
        """Process files in Google Drive: rename old format files and download Sunday crosswords.

        Args:
            service: An authenticated Google Drive service object
        """
        self.logger.info("Fetching files from Google Drive...")
        files_in_drive = self.list_files_in_drive_folder(service)
        self.logger.info(
            f"Found {len(files_in_drive)} files in Google Drive folder"
        )

        # Get list of local files
        local_files = self.list_local_files()
        self.logger.info(f"Found {len(local_files)} files in local directory")

        # First pass: rename files in old format
        self.logger.info("Checking for files to rename...")
        for drive_file in files_in_drive:
            drive_file_id = drive_file["id"]
            drive_filename = drive_file["name"]

            if self.is_iso_format(drive_filename):
                new_filename, changed = self.format_filename_old_to_new(
                    drive_filename
                )
                if changed:
                    self.rename_file_in_drive(
                        service, drive_file_id, new_filename
                    )

        # Refresh the file list after renames
        if not self.dry_run and self.stats["renamed"] > 0:
            files_in_drive = self.list_files_in_drive_folder(service)

        # Second pass: download Sunday crosswords
        self.logger.info("Checking for new Sunday crosswords to download...")
        for drive_file in files_in_drive:
            drive_file_id = drive_file["id"]
            drive_filename = drive_file["name"]

            if not drive_filename.startswith(
                "%m"
            ):  # >> Ignore files that start with %
                day_of_week = self.day_of_week_string_to_index(self.day_of_week)

                # Check if this is a Sunday crossword
                if f"-{day_of_week}" in drive_filename:
                    local_filename = drive_filename.replace(
                        f"-{day_of_week}", ""
                    )

                    if local_filename not in local_files:
                        self.logger.info(
                            f"Downloading new Sunday crossword: {local_filename}"
                        )
                        self.download_file(
                            service, drive_file_id, local_filename
                        )
                    else:
                        self.logger.debug(
                            f"Skipping existing file: {local_filename}"
                        )
                        self.stats["skipped"] += 1

    def sync(self) -> Dict[str, int]:
        """Perform the synchronization process.

        Returns:
            Statistics about the operations performed
        """
        self.logger.info("Starting NYT crosswords sync process")
        if self.dry_run:
            self.logger.info("DRY RUN MODE: No files will be modified")

        try:
            # Authenticate
            service = self.authenticate_google_drive()

            # Process files
            self.process_drive_files(service)

            # Report results
            self.logger.info("Sync completed successfully")
            self.logger.info(f"Files renamed: {self.stats['renamed']}")
            self.logger.info(f"Files downloaded: {self.stats['downloaded']}")
            self.logger.info(f"Files skipped: {self.stats['skipped']}")
            self.logger.info(f"Errors encountered: {self.stats['errors']}")

            return self.stats
        except Exception as e:
            self.logger.error(
                f"Unexpected error during sync: {e}", exc_info=True
            )
            self.stats["errors"] += 1
            return self.stats


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Sync NYT crosswords from Google Drive to iCloud"
    )
    parser.add_argument(
        "--day_of_week",
        "-d",
        default=6,
        action="store_true",
        help="Sync crosswords from this day of the Week. Defaults to Sunday (6).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate operations without making changes",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("\nNYT Crosswords | Syncing Files from Google Drive to iCloud\n")
    syncer = CrosswordSyncer(day_of_week=args.day_of_week, dry_run=args.dry_run)
    syncer.sync()


if __name__ == "__main__":
    main()
