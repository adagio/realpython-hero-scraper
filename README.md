# Real Python Hero Image Extractor

A Python script to automatically extract and download hero images from a list of Real Python article URLs.

## Description

This script uses Playwright to navigate to specified Real Python URLs, identify the primary "hero" image associated with the article or video, and then downloads the image using `aiohttp`. It saves the images locally in an `images/` directory, using sanitized filenames derived from the original URL.

## Features

*   Fetches hero images from both standard Real Python articles (`figure img`) and video pages (`og:image` meta tag).
*   Asynchronous operation using `asyncio`, `playwright`, and `aiohttp` for efficient processing of multiple URLs.
*   Creates an `images/` directory if it doesn't exist.
*   Sanitizes URLs to create safe and descriptive filenames for downloaded images.
*   Handles basic network and file I/O errors during download.
*   Attempts to preserve the original file extension, defaulting to `.jpg` if unknown or unusual.

## Requirements

*   Python 3.7+
*   Libraries:
    *   `playwright`
    *   `aiohttp`
    *   `aiofiles`

## Installation

1.  **Clone the repository (if applicable) or download the script.**
2.  **Install Python dependencies:**
    ```bash
    pip install playwright aiohttp aiofiles
    ```
3.  **Install Playwright browsers:** (This needs to be done once)
    ```bash
    playwright install
    ```
    *Note: This will download the necessary browser binaries (Chromium is used by default in the script).*

## Usage

1.  **(Optional)** Modify the `urls` list within `main.py` to include the Real Python URLs you want to process.
2.  Run the script from your terminal:
    ```bash
    python main.py
    ```
3.  The script will process each URL, print progress updates to the console, and save the downloaded images to the `images/` directory in the same folder as the script.

## How It Works

1.  The script initializes `playwright` to launch a headless browser instance (Chromium).
2.  It iterates through the provided list of URLs.
3.  For each URL, it navigates to the page using `playwright`.
4.  It first checks if the URL points to a video page (`/videos/`). If so, it attempts to extract the image URL from the `og:image` meta tag.
5.  If it's not a video page or the `og:image` tag is not found, it attempts to find the first image within a `<figure>` tag (`figure img`).
6.  If an image source (`src`) is found using either method, it constructs the absolute URL if necessary.
7.  The original article URL is sanitized to create a base filename.
8.  The file extension is extracted from the image source URL (defaulting to `.jpg`).
9.  An `aiohttp` session is used to asynchronously download the image content.
10. The image content is saved to a file in the `images/` directory using `aiofiles`.
11. Progress and any errors are printed to the console.