from typing import BinaryIO

import argparse
import os
import platform
import requests

from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class NYTCrosswords:
    # Seattle Times website
    URL = "https://nytsyn.pzzl.com/cwd_seattle/"

    # Waiting time in seconds
    wait_time = 5
    poll_freq = 0.1

    def __init__(self, options):
        if os.path.exists("./chromedriver-linux64"):
            self.service = Service(executable_path="/usr/local/bin/chromedriver")
        else:
            self.service = Service(ChromeDriverManager().install())
        self.options = options
        self.puzzle_data = None
        self.solution_data = None

    def download_puzzle(self):
        # Start a Browser Session
        driver = webdriver.Chrome(service=self.service, options=self.options)

        # Go to URL using driver
        driver.get(self.URL)

        element = WebDriverWait(
            driver, self.wait_time, poll_frequency=self.poll_freq
        ).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".fa-print")))
        # Find the parent button of the print button
        button = element.find_element(By.XPATH, "./ancestor::button")
        button.click()

        # The only element here is the Print button.
        element = WebDriverWait(
            driver, self.wait_time, poll_frequency=self.poll_freq
        ).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-primary")))
        element.click()

        # Later in your try block after clicking to download PDF
        WebDriverWait(driver, self.wait_time).until(EC.url_changes(self.URL))
        # Check the number of open windows and switch only if a new one has been opened
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

            current_url = driver.current_url
            self.puzzle_data = self.fetch_data(current_url)

        else:
            print("No new window opened.")

        driver.close()

    def download_solution(self):
        # Start a Browser Session
        driver = webdriver.Chrome(service=self.service, options=self.options)

        # Go to URL using driver
        driver.get(self.URL)

        element = WebDriverWait(
            driver, self.wait_time, poll_frequency=self.poll_freq
        ).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".fa-print")))
        # Find the parent button of the print button
        button = element.find_element(By.XPATH, "./ancestor::button")
        button.click()

        try:
            # Wait for the label "C" to be present
            label = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//label[contains(text(), 'Solution without clues')]")
                )
            )
            # Locate the associated input (checkbox/radio) using the label's 'for' attribute or by navigating up to the input type
            checkbox = label.find_element(
                By.XPATH, "..//input[@type='checkbox' or @type='radio']"
            )

            # Click the checkbox or radio button if it's not already selected
            if not checkbox.is_selected():
                checkbox.click()

            element = WebDriverWait(
                driver, self.wait_time, poll_frequency=self.poll_freq
            ).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".fa-print")))

            # The only element here is the Print button.
            element = WebDriverWait(
                driver, self.wait_time, poll_frequency=self.poll_freq
            ).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-primary")))
            element.click()

            # Later in your try block after clicking to download PDF
            WebDriverWait(driver, self.wait_time).until(EC.url_changes(self.URL))
            # Check the number of open windows and switch only if a new one has been opened
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])

                current_url = driver.current_url
                self.solution_data = self.fetch_data(current_url)

            else:
                print("No new window opened.")

        except Exception as e:
            print(f"An error occurred in `download_solution`(): {e}")

        driver.close()

    @staticmethod
    def fetch_data(url: str):
        """
        Fetch the content from the given URL and returns the binary data
        """
        response = requests.get(url)
        return response.content

    @staticmethod
    def write_data_to_file(data: BinaryIO, file: str):
        """
        Write data to file.

        This function fetches the content from the given URL and saves it to a specified file in binary
        format. It is intended for saving web pages or resources that can be accessed via an HTTP GET request.

        Args:
            data (binary):  The binary data to write.
            filename (str): The name of the file (with .pdf extension) in which to save the web page content.
                            The file will be created or overwritten in the specified download directory.

        Raises:
            Exception: Raises an exception if the URL cannot be accessed or if there's an error during
                    the file writing process.

        Example:
            write_data_to_file('https://example.com', 'example_page')
        """
        with open(file, "wb") as f:
            f.write(data)


def get_icloud_path():
    # Determine the base path for iCloud Drive
    if platform.system() == "Darwin":  # macOS
        icloud_path = os.path.expanduser(
            "~/Library/Mobile Documents/com~apple~CloudDocs/"
        )
    elif platform.system() == "Windows":
        icloud_path = os.path.expanduser("~/iCloudDrive/")
    else:
        raise NotImplementedError("Unsupported operating system.")

    return icloud_path


def upload_data(service, filename, folderId, data):
    query = f"name='{filename}' and '{folderId}' in parents and trashed=false"
    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name)")
        .execute()
    )
    existing_files = results.get("files", [])

    if existing_files:
        print("File exists, exiting...")
        return

    file_metadata = {"name": filename, "parents": [folderId]}
    media = MediaInMemoryUpload(data, mimetype="application/pdf", resumable=True)
    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    print(f"File ID: {file.get('id')}")


def main(args):
    # Set Options for WebDriver
    options = Options()
    options.add_argument("--incognito")
    options.add_argument("--headless")  # Headless mode to avoid opening a window
    options.add_argument("--disable-gpu")  # Disable GPU acceleration
    options.add_argument("--no-sandbox")  # Required for some environments
    options.add_argument("--start-maximized")  # Needed to see whole page
    options.add_argument(
        "--disable-dev-shm-usage"
    )  # Overcome limited resource problems
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": "/tmp",
            "download.prompt_for_download": False,  # Do not prompt for download
            "download.directory_upgrade": True,  # Allow overwriting files
            "safebrowsing.enabled": True,  # Enable safe browsing
        },
    )

    xwords = NYTCrosswords(options=options)
    xwords.download_puzzle()
    xwords.download_solution()

    today_fmt = datetime.today().strftime("%%m-%d-%y")
    dw = datetime.today().strftime("%a").upper()
    puzzle_file_name = f"{today_fmt}-{dw} Puzzle.pdf"
    solution_file_name = f"{today_fmt}-{dw} Solution.pdf"

    if args.save_dir:
        # Create the downloads directory if it doesn't exist
        if not os.path.exists(args.save_dir):
            os.makedirs(args.save_dir)

        puzzle_file_path = os.path.join(args.save_dir, puzzle_file_name)
        NYTCrosswords.write_data_to_file(xwords.puzzle_data, puzzle_file_path)

        solution_file_path = os.path.join(args.save_dir, solution_file_name)
        NYTCrosswords.write_data_to_file(xwords.solution_data, solution_file_path)

        print("Files saved. Listing...")
        files = os.listdir(args.save_dir)
        for file in files:
            print(file)

    if args.google_service_account_file:
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        puzzle_file_path = os.path.join("/tmp", puzzle_file_name)
        solution_file_path = os.path.join("/tmp", solution_file_name)

        credentials = service_account.Credentials.from_service_account_file(
            args.google_service_account_file, scopes=SCOPES
        )
        service = build("drive", "v3", credentials=credentials)

        upload_data(
            service, puzzle_file_name, args.google_folder_id, xwords.puzzle_data
        )
        upload_data(
            service, solution_file_name, args.google_folder_id, xwords.solution_data
        )


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Set the download directory.")
    parser.add_argument("--google_service_account_file", type=str)
    parser.add_argument("--google_folder_id", type=str)
    parser.add_argument("--save_dir", type=str)

    # Parse arguments
    args = parser.parse_args()

    # Call the main function
    main(args)
