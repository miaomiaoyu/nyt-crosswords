import os
import io
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
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


# Using os.walk
def list_files(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_list.append(file)
    return file_list


# Example usage
download_path = os.path.join(ICLOUD_PATH, "nyt-crosswords")

# Check if there are any differences in the two files of the two folders
icloud_files = list_files(download_path)

service = authenticate_google_drive()
files_in_drive = list_files_in_drive_folder(service, GOOGLE_FOLDER_ID)
files_in_drive_sunday = [
    {"id": f.get("id"), "name": f.get("name")}
    for f in files_in_drive
    if "SUN" in f.get("name").upper()
]
drive_files = [f.get("name").replace("-SUN", "") for f in files_in_drive_sunday]

new_files = set(drive_files) - set(icloud_files)
print(f"{len(new_files)} new files found.")

if len(new_files) > 0:
    for new_file in new_files:
        file_id = next(
            (
                item["id"]
                for item in files_in_drive_sunday
                if item["name"] == new_file.replace(" ", "-SUN ")
            ),
            None,
        )
        request = service.files().get_media(fileId=file_id)
        file_path = os.path.join(download_path, new_file)
        with io.FileIO(file_path, "wb") as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download {new_file}: {int(status.progress() * 100)}%")
