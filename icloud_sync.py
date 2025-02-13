import os
import io
import re
from dotenv import load_dotenv
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials

load_dotenv()

ICLOUD_PATH = os.environ.get("ICLOUD_PATH")
GOOGLE_FOLDER_ID = os.environ.get("GOOGLE_FOLDER_ID")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")


# Authenticate using Service Account
def authenticate_google_drive():
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)


def list_files_in_drive_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])


def rename_file_in_drive(file_id, new_name):
    try:
        # Update the file's name
        updated_file = service.files().update(
            fileId=file_id,
            body={'name': new_name},
            fields='id, name'
        ).execute()

        print(f"Renamed file ID: {updated_file['id']} to '{updated_file['name']}'")
        return updated_file
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


# Using os.walk
def list_all_files_recursive(path):
    file_list = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_list.append(file)
    return file_list


def format_date_long_to_short(long_date):
    # 2025-02-09 --> 02-09-25
    long_date_dt = datetime.strptime(long_date, '%Y-%M-%d')
    short_date = long_date_dt.strftime('%M-%d-%y')
    return short_date


def format_filename_old_to_new(old_filename):
    [long_date, day, content] = old_filename.split('_')
    short_date = format_date_long_to_short(long_date)
    short_day = day[:3].upper()
    new_filename = f'{short_date}-{short_day} {content}'
    return new_filename


def detect_filename_format(filename):
    """ Returns 'Old', 'New', or 'Unknown' """
    # Regex for new format: YYYY-MM-DD_Dayname_Solution.pdf
    old_format_patterns = (
        r"^\d{4}-\d{2}-\d{2}_[A-Za-z]+_Puzzle\.pdf$",
        r"^\d{4}-\d{2}-\d{2}_[A-Za-z]+_Solution\.pdf$")
    # Regex for old format: MM-DD-YY-DAY Solution.pdf
    new_format_patterns = (
        r"^\d{2}-\d{2}-\d{2}-[A-Z]{3}\sPuzzle\.pdf$",
        r"^\d{2}-\d{2}-\d{2}-[A-Z]{3}\sSolution\.pdf$")
    for pattern in old_format_patterns:
        if re.match(pattern, filename):
            return 'Old'
    for pattern in new_format_patterns:
        if re.match(pattern, filename):
            return 'New'
    else:
        return 'Unknown'


if __name__ == "__main__":
    
    # Google API
    service = authenticate_google_drive()

    # Example usage
    download_path = os.path.join(ICLOUD_PATH, "nyt-crosswords")
    downloaded_files = list_all_files_recursive(download_path)

    # Check if there are any differences in the two files of the two folders
    icloud_files = list_all_files_recursive(download_path)


    # 1. Detect new files in the drive folder and rename them.
    files_in_drive = list_files_in_drive_folder(service, GOOGLE_FOLDER_ID)

    for drive_file in files_in_drive:
        drive_file_id = drive_file['id']
        drive_filename = drive_file['name']

        filename_format = detect_filename_format(drive_filename)
        if filename_format == 'Old':
            new_filename = format_filename_old_to_new(drive_filename)
            updated_file = rename_file_in_drive(drive_file_id, new_filename)


    # 2. Find new SUNDAY crosswords.
    files_in_drive = list_files_in_drive_folder(service, GOOGLE_FOLDER_ID)

    unsynced_file_ids = []

    for drive_file in files_in_drive:
        drive_filename = drive_file['name']
        # 01-01-25-SUN --> 01-01-25
        cloud_filename = drive_filename.replace('-SUN', '')

        if ('SUN' in drive_filename) and (cloud_filename not in downloaded_files):
            unsynced_file_id = drive_file['id']
            request = service.files().get_media(fileId=unsynced_file_id)

            with io.FileIO(os.path.join(download_path, cloud_filename), "wb") as file:
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"Downloading {cloud_filename}: {int(status.progress() * 100)}%")
