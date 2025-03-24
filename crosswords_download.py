from typing import BinaryIO, Optional

import argparse
import logging
import os
import platform
import requests
import sys
import time

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


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("nyt_crosswords")


class NYTCrosswords:
    """Class for downloading NYT Crossword puzzles and solutions from Seattle Times."""

    # Seattle Times website hosting NYT crosswords
    URL = "https://nytsyn.pzzl.com/cwd_seattle/"

    # Wait configuration
    DEFAULT_WAIT_TIME = 5
    DEFAULT_POLL_FREQ = 0.1
    MAX_RETRIES = 3

    def __init__(
        self,
        options: Options,
        wait_time: int = DEFAULT_WAIT_TIME,
        poll_freq: float = DEFAULT_POLL_FREQ,
    ):
        """
        Initialize the NYTCrosswords downloader.

        Args:
            options: Chrome WebDriver options
            wait_time: Maximum wait time in seconds for WebDriver waits
            poll_freq: Polling frequency in seconds for WebDriver waits
        """
        # Set up Chrome driver
        if os.path.exists("./chromedriver-linux64"):
            self.service = Service(
                executable_path="/usr/local/bin/chromedriver"
            )
        else:
            self.service = Service(ChromeDriverManager().install())

        self.options = options
        self.wait_time = wait_time
        self.poll_freq = poll_freq
        self.puzzle_data = None
        self.solution_data = None
        self.puzzle_url = None
        self.solution_url = None

    def download_puzzle(self) -> bool:
        """
        Download the crossword puzzle.

        Returns:
            bool: True if successful, False otherwise
        """
        return self._download_content(is_solution=False)

    def download_solution(self) -> bool:
        """
        Download the crossword solution.

        Returns:
            bool: True if successful, False otherwise
        """
        return self._download_content(is_solution=True)

    def _download_content(self, is_solution: bool = False) -> bool:
        """
        Common method to download either puzzle or solution.

        Args:
            is_solution: Whether to download the solution (True) or puzzle (False)

        Returns:
            bool: True if successful, False otherwise
        """
        action_type = "solution" if is_solution else "puzzle"
        logger.info(f"Downloading crossword {action_type}...")

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Start a Browser Session
                driver = webdriver.Chrome(
                    service=self.service, options=self.options
                )
                driver.get(self.URL)

                # Click the print button
                print_icon = WebDriverWait(
                    driver, self.wait_time, poll_frequency=self.poll_freq
                ).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        ".fa-print",
                    ))
                )

                print_button = print_icon.find_element(
                    By.XPATH, "./ancestor::button"
                )
                print_button.click()

                # If downloading solution, select the appropriate option
                if is_solution:
                    try:
                        # Wait for the solution option to be present
                        solution_label = WebDriverWait(
                            driver, self.wait_time
                        ).until(
                            EC.presence_of_element_located((
                                By.XPATH,
                                "//label[contains(text(), 'Solution without clues')]",
                            ))
                        )

                        # Find and click the checkbox/radio if not already selected
                        solution_checkbox = solution_label.find_element(
                            By.XPATH,
                            "..//input[@type='checkbox' or @type='radio']",
                        )

                        if not solution_checkbox.is_selected():
                            solution_checkbox.click()
                            # Small delay to ensure UI updates
                            time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Failed to select solution option: {e}")
                        driver.quit()
                        continue

                # Click the final print button
                print_btn = WebDriverWait(
                    driver, self.wait_time, poll_frequency=self.poll_freq
                ).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        ".btn-primary",
                    ))
                )
                print_btn.click()

                # Wait for new window/tab to open with the PDF
                WebDriverWait(driver, self.wait_time).until(
                    EC.url_changes(self.URL)
                )

                if len(driver.window_handles) > 1:
                    # Switch to the new window
                    driver.switch_to.window(driver.window_handles[-1])
                    current_url = driver.current_url

                    # Store URL for debugging
                    if is_solution:
                        self.solution_url = current_url
                    else:
                        self.puzzle_url = current_url

                    # Fetch the data
                    content_data = self.fetch_data(current_url)

                    # Store the data
                    if is_solution:
                        self.solution_data = content_data
                    else:
                        self.puzzle_data = content_data

                    driver.quit()
                    return True
                else:
                    logger.warning(f"No new window opened on attempt {attempt}")
                    driver.quit()

            except Exception as e:
                logger.error(
                    f"Error downloading {action_type} (attempt {attempt}/{self.MAX_RETRIES}): {e}"
                )
                if "driver" in locals():
                    driver.quit()

        logger.error(
            f"Failed to download {action_type} after {self.MAX_RETRIES} attempts"
        )
        return False

    @staticmethod
    def fetch_data(url: str) -> bytes:
        """
        Fetch content from the given URL and return the binary data.

        Args:
            url: URL to fetch data from

        Returns:
            The binary content

        Raises:
            requests.RequestException: If the request fails
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.content
        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            raise

    @staticmethod
    def write_data_to_file(data: bytes, file_path: str) -> bool:
        """
        Write binary data to file.

        Args:
            data: The binary data to write
            file_path: The full path to the file to write

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure the directory exists
            os.makedirs(
                os.path.dirname(os.path.abspath(file_path)), exist_ok=True
            )

            with open(file_path, "wb") as f:
                f.write(data)
            logger.info(f"Successfully wrote data to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write data to {file_path}: {e}")
            return False


def get_icloud_path() -> str:
    """
    Determine the base path for iCloud Drive based on the operating system.

    Returns:
        The path to iCloud Drive

    Raises:
        NotImplementedError: If the operating system is not supported
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        icloud_path = os.path.expanduser(
            "~/Library/Mobile Documents/com~apple~CloudDocs/"
        )
    elif system == "Windows":
        icloud_path = os.path.expanduser("~/iCloudDrive/")
    else:
        raise NotImplementedError(f"Unsupported operating system: {system}")

    if not os.path.exists(icloud_path):
        logger.warning(f"iCloud path not found at {icloud_path}")

    return icloud_path


def upload_to_drive(
    service,
    filename: str,
    folder_id: str,
    data: bytes,
    mime_type: str = "application/pdf",
) -> Optional[str]:
    """
    Upload data to Google Drive.

    Args:
        service: Google Drive service instance
        filename: Name of the file to create
        folder_id: ID of the folder where the file should be created
        data: Binary data to upload
        mime_type: MIME type of the file

    Returns:
        The ID of the created file, or None if the file already exists or upload fails
    """
    try:
        # Check if file already exists in the specified folder
        query = (
            f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        )
        results = (
            service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )

        existing_files = results.get("files", [])

        if existing_files:
            logger.info(
                f"File '{filename}' already exists in Google Drive, skipping upload"
            )
            return existing_files[0].get("id")

        # Upload new file
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaInMemoryUpload(data, mimetype=mime_type, resumable=True)

        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        file_id = file.get("id")
        logger.info(
            f"Successfully uploaded '{filename}' to Google Drive with ID: {file_id}"
        )
        return file_id

    except Exception as e:
        logger.error(f"Failed to upload '{filename}' to Google Drive: {e}")
        return None


def main():
    """Main function to parse arguments and run the program."""

    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Download NYT Crossword puzzles and solutions from Seattle Times."
    )

    parser.add_argument(
        "--save_dir",
        type=str,
        default="./download",
        help="Directory to save downloaded puzzles and solutions",
    )

    parser.add_argument(
        "--google_service_account_file",
        type=str,
        help="Path to Google service account credentials JSON file",
    )

    parser.add_argument(
        "--google_folder_id",
        type=str,
        help="Google Drive folder ID to upload files to",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run Chrome in headless mode (default: True)",
    )

    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    # Parse arguments
    args = parser.parse_args()

    # Set logging level
    logger.setLevel(getattr(logging, args.log_level))

    # Check if Google Drive upload is requested but missing required args
    if args.google_service_account_file and not args.google_folder_id:
        logger.error(
            "Google folder ID is required when using Google Drive upload"
        )
        sys.exit(1)
    elif args.google_folder_id and not args.google_service_account_file:
        logger.error(
            "Google service account file is required when using Google Drive upload"
        )
        sys.exit(1)

    # Set Options for WebDriver
    options = Options()
    options.add_argument("--incognito")

    if args.headless:
        options.add_argument("--headless")

    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": "/downloads",
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    # Initialize and run crossword downloader
    xwords = NYTCrosswords(options=options)

    # Download puzzle and solution
    puzzle_success = xwords.download_puzzle()
    solution_success = xwords.download_solution()

    if not puzzle_success and not solution_success:
        logger.error("Failed to download both puzzle and solution")
        sys.exit(1)

    # Generate filenames based on today's date
    today = datetime.today()
    today_fmt = today.strftime("%m-%d-%y")
    day_of_week = today.strftime("%a").upper()

    puzzle_file_name = f"{today_fmt}-{day_of_week} Puzzle.pdf"
    solution_file_name = f"{today_fmt}-{day_of_week} Solution.pdf"

    # Save files locally if requested
    if args.save_dir:
        if puzzle_success and xwords.puzzle_data:
            puzzle_file_path = os.path.join(args.save_dir, puzzle_file_name)
            NYTCrosswords.write_data_to_file(
                xwords.puzzle_data, puzzle_file_path
            )

        if solution_success and xwords.solution_data:
            solution_file_path = os.path.join(args.save_dir, solution_file_name)
            NYTCrosswords.write_data_to_file(
                xwords.solution_data, solution_file_path
            )

        # List saved files
        if os.path.exists(args.save_dir):
            logger.info(f"Files saved to {args.save_dir}:")
            files = os.listdir(args.save_dir)
            for file in files:
                logger.info(f"  - {file}")

    # Upload to Google Drive if credentials provided
    if args.google_service_account_file and args.google_folder_id:
        try:
            logger.info("Uploading files to Google Drive...")

            # Set up Google Drive API
            SCOPES = ["https://www.googleapis.com/auth/drive"]
            credentials = service_account.Credentials.from_service_account_file(
                args.google_service_account_file, scopes=SCOPES
            )
            service = build("drive", "v3", credentials=credentials)

            # Upload files
            if puzzle_success and xwords.puzzle_data:
                upload_to_drive(
                    service,
                    puzzle_file_name,
                    args.google_folder_id,
                    xwords.puzzle_data,
                )

            if solution_success and xwords.solution_data:
                upload_to_drive(
                    service,
                    solution_file_name,
                    args.google_folder_id,
                    xwords.solution_data,
                )

        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {e}")

    logger.info("Operation completed")


if __name__ == "__main__":
    main()
