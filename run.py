import os
import requests
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import argparse


class NYTSundayCrosswords:
    # Seattle Times website
    URL = "https://nytsyn.pzzl.com/cwd_seattle/"

    # Waiting time in seconds
    wait_time = 5
    poll_freq = 0.1

    def __init__(self, options, download_dir):
        print("\n*** Initializing NYTSundayCrosswords ***\n")

        self.options = options
        self.download_dir = download_dir

        self.today = datetime.today().strftime("%y%m%d")
        self.today_fmt = datetime.today().strftime("%Y-%m-%d")
        self.today_dayweek = datetime.today().strftime("%A")
        print(f"    Today is \033[1m{self.today_fmt}, {self.today_dayweek}\033[0m.\n")

        self.puzzle_file = os.path.join(
            self.download_dir, f"{self.today_fmt}_{self.today_dayweek}_Puzzle.pdf"
        )

        self.solution_file = os.path.join(
            self.download_dir, f"{self.today_fmt}_{self.today_dayweek}_Solution.pdf"
        )

    def download_puzzle(self):
        # Start a Browser Session
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=self.options
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
            self.save_page_as_pdf(current_url, self.puzzle_file)

        else:
            print("No new window opened.")

        driver.close()

    def download_solution(self):
        # Start a Browser Session
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=self.options
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
                self.save_page_as_pdf(current_url, self.solution_file)

            else:
                print("No new window opened.")

        except Exception as e:
            print(f"An error occurred in `download_solution`(): {e}")

        driver.close()

    @staticmethod
    def save_page_as_pdf(url: str, file: str):
        """
        Saves the content of a web page as a PDF file.

        This function fetches the content from the given URL and saves it to a specified file in binary
        format. It is intended for saving web pages or resources that can be accessed via an HTTP GET request.

        Args:
            url (str): The URL of the web page to be saved as a PDF. This must be a valid URL pointing to
                    an accessible resource.
            filename (str): The name of the file (with .pdf extension) in which to save the web page content.
                            The file will be created or overwritten in the specified download directory.

        Raises:
            Exception: Raises an exception if the URL cannot be accessed or if there's an error during
                    the file writing process.

        Example:
            save_page_as_pdf('https://example.com', 'example_page')
        """
        response = requests.get(url)
        with open(file, "wb") as f:
            f.write(response.content)


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


def main(download_dir):
    # Specify the download directory

    # Create the downloads directory if it doesn't exist
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

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
            "download.default_directory": download_dir,  # Set download directory
            "download.prompt_for_download": False,  # Do not prompt for download
            "download.directory_upgrade": True,  # Allow overwriting files
            "safebrowsing.enabled": True,  # Enable safe browsing
        },
    )

    xwords = NYTSundayCrosswords(options=options, download_dir=download_dir)
    xwords.download_puzzle()
    xwords.download_solution()


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Set the download directory.")

    parser.add_argument(
        "--download_dir",
        type=str,
        default="0",
        help='Specify the download directory (default: "0", creates a "NYT Crosswords" folder in iCloud)',
    )

    # Parse arguments
    args = parser.parse_args()

    # Convert download_dir to an appropriate type
    download_dir = args.download_dir

    if download_dir == "icloud":
        download_dir = os.path.join(get_icloud_path(), "NYT Crosswords")
    elif download_dir == "0":
        download_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "downloads"
        )  # Keep it as zero for the main function
    else:
        download_dir = download_dir  # Take it as a string path

    # Call the main function
    main(download_dir)
