import os
import io
import shutil
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials

load_dotenv()

# Paths
ICLOUD_DRIVE_PATH = os.path.expanduser(os.environ.get("ICLOUD_DRIVE_PATH"))
SERVICE_ACCOUNT_FILE = os.path.expanduser(os.environ.get("SERVICE_ACCOUNT_FILE"))
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")


# Authenticate using Service Account
def authenticate_google_drive():
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


# Download file from Google Drive
def download_file(service, file_id, file_name):
    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(ICLOUD_DRIVE_PATH, "Blank", file_name)
    with io.FileIO(file_path, "wb") as file:
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {file_name}: {int(status.progress() * 100)}%")
    return file_path


# List files in a specific Google Drive folder
def list_files_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])


def get_google_drive_folder_id_by_name(service, folder_name):
    # Gets Google Drive folder ID based on folder name.
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get("files", [])
    if not folders:
        print("No folder found with the name:", folder_name)
        return None
    if len(folders) > 1:
        print("Multiple folders found. Using the first one.")
    return folders[0]["id"]


def transfer_sunday_puzzles(files):
    for file in files:
        if "Sunday" in file:
            [date, day, content] = file.split("_")
            new_file = "_".join([date, content])
            if not os.path.exists(os.path.join(ICLOUD_DRIVE_PATH, "Sunday", new_file)):
                src = os.path.join(ICLOUD_DRIVE_PATH, "Blank", file)
                dst = os.path.join(ICLOUD_DRIVE_PATH, "Sunday", new_file)
                shutil.copy(src, dst)
            else:
                print(f"{new_file} already exists in 'Sunday' drive.")


# Main function
def main():
    service = authenticate_google_drive()
    if GOOGLE_DRIVE_FOLDER_ID:
        files = list_files_in_folder(service, GOOGLE_DRIVE_FOLDER_ID)
    files = list_files_in_folder(service, GOOGLE_DRIVE_FOLDER_ID)

    if not files:
        print("No files found in the Google Drive folder.")
        return

    for file in files:
        if not os.path.exists(os.path.join(ICLOUD_DRIVE_PATH, "Blank", file["name"])):
            download_file(service, file["id"], file["name"])
        else:
            print(f"{file['name']} already exists in 'Blank' drive.")

    files = os.listdir(os.path.join(ICLOUD_DRIVE_PATH, "Blank"))
    transfer_sunday_puzzles(files)


if __name__ == "__main__":
    main()
