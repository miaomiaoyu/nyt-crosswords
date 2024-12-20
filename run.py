from typing import BinaryIO

import argparse
import os
import platform
import requests

from datetime import datetime
from googleapiclient.discovery import build
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

    def __init__(self, options, driver_executable_path):
        if driver_executable_path:
            self.service = Service(executable_path=driver_executable_path)
        else:
            self.service=Service(ChromeDriverManager().install())
        self.options = options
        self.puzzled_data = None
        self.solution_data = None

    def download_puzzle(self):
        # Start a Browser Session
        driver = webdriver.Chrome(
            service=self.service, options=self.options
        )

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
            self.puzzled_data = self.fetch_data(current_url)

        else:
            print("No new window opened.")

        driver.close()

    def download_solution(self):
        # Start a Browser Session
        driver = webdriver.Chrome(
            service=self.service, options=self.options
        )

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

def upload_file(service, file_name):
    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, resumable=True)
    
    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f'Successfully uploaded {file_name}')
        print(f'File ID: {file.get("id")}')
        return file.get('id')
    except Exception as e:
        print(f'Error uploading file: {e}')
        return None

def main(args):
    # Specify the download directory
    save_dir = args.save_dir
    # Create the downloads directory if it doesn't exist
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # Set Options for WebDriver
    options = Options()
    options.add_argument("--incognito")
    options.add_argument("--headless")  # Headless mode to avoid opening a window
    options.add_argument("--disable-gpu")  # Disable GPU acceleration
    options.add_argument("--no-sandbox")  # Required for some environments
    options.add_argument("--start-maximized")
    options.add_argument(
        "--disable-dev-shm-usage"
    )  # Overcome limited resource problems
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": save_dir,  # Set download directory
            "download.prompt_for_download": False,  # Do not prompt for download
            "download.directory_upgrade": True,  # Allow overwriting files
            "safebrowsing.enabled": True,  # Enable safe browsing
        },
    )

    xwords = NYTCrosswords(options=options, driver_executable_path=args.driver_executable_path)
    xwords.download_puzzle()
    xwords.download_solution()
    print(xwords.solution_data)

    today = datetime.today().strftime("%y%m%d")
    today_fmt = datetime.today().strftime("%Y-%m-%d")
    today_dayweek = datetime.today().strftime("%A")
    print(f"    Today is \033[1m{today_fmt}, {today_dayweek}\033[0m.\n")

    puzzle_file = os.path.join(
        "./", f"{today_fmt}_{today_dayweek}_Puzzle.pdf"
    )

    solution_file = os.path.join(
        "./", f"{today_fmt}_{today_dayweek}_Solution.pdf"
    )



if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Set the download directory.")
    parser.add_argument('--token', help='Google Drive API token')
    parser.add_argument('--driver_executable_path', help='Google Drive API token')
    parser.add_argument(
        "--save_dir",
        type=str,
        default="./downloads",
    )

    # Parse arguments
    args = parser.parse_args()

    # Call the main function
    main(args)
