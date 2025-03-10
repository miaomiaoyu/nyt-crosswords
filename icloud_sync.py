#!/usr/bin/env python3

import os
import io
import re
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()

# Constants
ICLOUD_PATH = os.path.expanduser(os.getenv("ICLOUD_PATH"))
GOOGLE_SERVICE_ACCOUNT_FILE = os.path.expanduser(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"))
GOOGLE_FOLDER_ID = os.getenv("GOOGLE_FOLDER_ID")
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Ensure required environment variables exist
if not all([ICLOUD_PATH, GOOGLE_FOLDER_ID, GOOGLE_SERVICE_ACCOUNT_FILE]):
    raise ValueError("Missing one or more required environment variables. Check .env file.")


def authenticate_google_drive() -> Any:
    """Authenticates and returns a Google Drive service instance."""
    try:
        credentials = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        logging.error(f"Google Drive authentication failed: {e}")
        raise


def list_files_in_drive_folder(service: Any, folder_id: str) -> List[Dict[str, str]]:
    """Lists files in a specified Google Drive folder."""
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        return results.get("files", [])
    except HttpError as e:
        logging.error(f"Error listing files in Google Drive folder: {e}")
        return []


def rename_file_in_drive(service: Any, file_id: str, new_name: str) -> Optional[Dict[str, str]]:
    """Renames a file in Google Drive."""
    try:
        updated_file = service.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields="id, name"
        ).execute()
        logging.info(f"Renamed [ID: {updated_file['id']}] >> '{updated_file['name']}'")
        return updated_file
    except HttpError as e:
        logging.error(f"Failed to rename file: {e}")
        return None


def list_all_files_recursive(path: str) -> List[str]:
    """Returns a list of all file names in the given directory recursively."""
    file_list = []
    for root, _, files in os.walk(path):
        file_list.extend(files)
    return file_list


def format_date_long_to_short(long_date: str) -> str:
    """Converts a date from YYYY-MM-DD to MM-DD-YY format."""
    try:
        long_date_dt = datetime.strptime(long_date, "%Y-%m-%d")
        return long_date_dt.strftime("%m-%d-%y")
    except ValueError as e:
        logging.error(f"Invalid date format: {long_date}. Error: {e}")
        return long_date


def format_filename_old_to_new(old_filename: str) -> str:
    """Converts old filename format to new format."""
    try:
        long_date, day, content = old_filename.split("_")
        short_date = format_date_long_to_short(long_date)
        short_day = day[:3].upper()
        return f"{short_date}-{short_day} {content}"
    except ValueError:
        logging.warning(f"Filename '{old_filename}' does not match expected format.")
        return old_filename


def detect_filename_format(filename: str) -> str:
    """Detects if a filename follows the 'Old' or 'New' format."""
    old_format_patterns = (
        r"^\d{4}-\d{2}-\d{2}_[A-Za-z]+_Puzzle\.pdf$",
        r"^\d{4}-\d{2}-\d{2}_[A-Za-z]+_Solution\.pdf$",
    )
    new_format_patterns = (
        r"^\d{2}-\d{2}-\d{2}-[A-Z]{3}\sPuzzle\.pdf$",
        r"^\d{2}-\d{2}-\d{2}-[A-Z]{3}\sSolution\.pdf$",
    )

    for pattern in old_format_patterns:
        if re.match(pattern, filename):
            return "Old"

    for pattern in new_format_patterns:
        if re.match(pattern, filename):
            return "New"

    return "Unknown"


def download_file(service: Any, file_id: str, dst: str) -> None:
    """Downloads a file from Google Drive to a local directory."""
    try:
        request = service.files().get_media(fileId=file_id)
        with io.FileIO(dst, "wb") as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logging.info(f"Downloading {os.path.basename(dst)}: {int(status.progress() * 100)}%")
    except HttpError as e:
        logging.error(f"Failed to download file {os.path.basename(dst)}: {e}")


def process_drive_files(service: Any, icloud_files: List[str]) -> None:
    
    """Detects and renames old-format files in Google Drive, then downloads new Sunday crosswords."""
    files_in_drive = list_files_in_drive_folder(service, GOOGLE_FOLDER_ID)

    for drive_file in files_in_drive:
        drive_file_id = drive_file["id"]
        drive_filename = drive_file["name"]

        filename_format = detect_filename_format(drive_filename)
        if filename_format == "Old":
            new_filename = format_filename_old_to_new(drive_filename)
            rename_file_in_drive(service, drive_file_id, new_filename)

    for drive_file in list_files_in_drive_folder(service, GOOGLE_FOLDER_ID):
        drive_filename = drive_file["name"]

        if "-SUN" in drive_filename:
            cloud_filename = drive_filename.replace("-SUN", "")

            if cloud_filename not in icloud_files:
                download_path = os.path.join(ICLOUD_PATH, "nyt-crosswords", cloud_filename)
                download_file(service, drive_file["id"], download_path)


if __name__ == "__main__":
    print("\nnyt-crosswords | Syncing Files in Drive to iCloud\n")
    try:
        service = authenticate_google_drive()
        icloud_files = list_all_files_recursive(os.path.join(ICLOUD_PATH, "nyt-crosswords"))
        process_drive_files(service, icloud_files)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

