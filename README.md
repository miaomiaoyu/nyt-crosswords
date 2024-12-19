# NYT Crosswords

This script automates the downloading of the New York Times Crosswords puzzles and their solutions from the Seattle Times website. It uses Selenium WebDriver to interact with the web page and store the downloaded puzzles in PDF format.

## Features

- Downloads the daily crossword puzzle and solution in PDF format.
- Supports headless browsing to run the script without opening a browser window.
- Automatically creates the specified download directory if it does not exist.

## Prerequisites

Before running the script, ensure you have the following installed:

- Python 3.x
- pip (Python package installer)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/nyt-crosswords-downloader.git
   cd nyt-crosswords-downloader
   ```

2. Install required packages:

   ```bash
   pip install selenium webdriver-manager requests
   ```

## Usage

To run the script, execute the following command in your terminal, replacing `path/to/download/directory` with your desired directory:

```bash
python nyt_crosswords_downloader.py --save_dir path/to/download/directory
```

### Example

```bash
python nyt_crosswords_downloader.py --save_dir ./downloads
```

## How It Works

1. The script navigates to the [Seattle Times crossword page](https://nytsyn.pzzl.com/cwd_seattle/).
2. It finds the print button for the puzzle and solution, clicks on it, and downloads the corresponding PDF files.
3. It saves the downloaded files in the specified directory, using today's date and day of the week in the file names.

## Code Structure

- `NYTCrosswords`: Class responsible for handling the downloading of puzzles and solutions.
  - `download_puzzle`: Handles the downloading of the puzzle PDF.
  - `download_solution`: Handles the downloading of the solution PDF.
  - `save_page_as_pdf`: Saves the downloaded content as a PDF file.

- `get_icloud_path`: Utility function to determine the path for iCloud Drive.

- `main`: The main function that sets up the script and initiates the downloading process.

## Contribution

Feel free to fork the repository and submit pull requests. Any contributions, improvements, or bug fixes are welcome!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- This script uses the Selenium and webdriver-manager libraries for web automation.
  
For any questions or issues, please open an issue in the GitHub repository. Happy puzzling!
