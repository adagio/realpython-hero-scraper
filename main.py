import asyncio
import os
import re
import sqlite3
import datetime # Added import
from playwright.async_api import async_playwright, Error
import aiohttp
import aiofiles

IMAGES_DIR = "images"
DB_NAME = "hero_images.sqlite3"

def sanitize_filename(url):
    """Sanitizes a URL to create a safe filename."""
    # Remove scheme and domain
    path = re.sub(r'^https?://[^/]+/', '', url)
    # Remove trailing slash
    path = path.rstrip('/')
    # Replace invalid filename characters
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', path)
    # Limit length (optional)
    return sanitized[:100] # Limit filename length

async def download_image(session, url, filepath):
    """Downloads an image from a URL and saves it to filepath."""
    try:
        async with session.get(url) as response:
            response.raise_for_status() # Raise an exception for bad status codes
            async with aiofiles.open(filepath, mode='wb') as f:
                await f.write(await response.read())
            print(f"  Successfully saved image to: {filepath}")
            return True
    except aiohttp.ClientError as e:
        print(f"  Error downloading image {url}: {e}")
        return False
    except IOError as e:
        print(f"  Error saving image {filepath}: {e}")
        return False

async def extract_hero_image_from_urls(urls: list[str], conn: sqlite3.Connection):
    """Extracts hero images, checks DB, downloads if new or failed, and updates DB."""
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        print(f"Created directory: {IMAGES_DIR}")

    async with async_playwright() as p, aiohttp.ClientSession() as session:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        print("Extracting and downloading hero images...")
        cur = conn.cursor()
        for url in urls:
            print(f"Processing URL: {url}")

            # Check if URL already exists and was successfully downloaded
            cur.execute("SELECT successful_download FROM downloaded_images WHERE url = ?", (url,))
            result = cur.fetchone()

            if result and result[0] == 1:
                print(f"  Image for URL already successfully downloaded: {url}. Skipping.")
                continue # Skip to the next URL
            elif result and result[0] == 0:
                 print(f"  Previous download attempt failed for {url}. Retrying.")
            # Else (result is None), it's a new URL

            image_src = None
            download_successful = False # Initialize default status
            successful_download_time = None
            # Record the start time of the attempt for this URL
            try_download_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

            try:
                await page.goto(url, wait_until="domcontentloaded")

                # Check if it's a video page
                if "/videos/" in url:
                    print("  Video URL detected, checking og:image meta tag.")
                    og_image_locator = page.locator('meta[property="og:image"]').first
                    image_src = await og_image_locator.get_attribute("content")
                    if not image_src:
                        print("  Could not find og:image meta tag or content attribute.")
                
                # If not a video page or og:image failed, try the figure approach
                if not image_src:
                    print("  Checking 'figure img' selector.")
                    image_locator = page.locator("figure img").first
                    image_src = await image_locator.get_attribute("src")
                    if not image_src:
                         print(f"  Could not find src attribute for 'figure img'")


                if image_src:
                    print(f"  Found Image Source: {image_src}")
                    # Construct absolute URL if necessary
                    if image_src.startswith('/'):
                        # Check if already absolute path starting with //
                        if image_src.startswith('//'):
                             image_src = url.split(':')[0] + ":" + image_src
                        else:
                            base_url = "/".join(url.split('/')[:3])
                            image_src = base_url + image_src

                    filename_base = sanitize_filename(url)
                    # Try to get extension from URL, default to .jpg
                    file_ext = os.path.splitext(image_src)[1] or ".jpg"
                    # Ensure extension starts with a dot
                    if not file_ext.startswith('.'):
                        file_ext = '.' + file_ext
                        
                    # Basic check for valid image extensions
                    valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                    if file_ext.lower() not in valid_extensions:
                        print(f"  Warning: Unusual file extension '{file_ext}', defaulting to .jpg")
                        file_ext = ".jpg"

                    image_filename = f"{filename_base}{file_ext}"
                    image_filepath = os.path.join(IMAGES_DIR, image_filename)

                    # Attempt download
                    download_successful = await download_image(session, image_src, image_filepath)
                    if download_successful:
                         successful_download_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    # If download fails, download_successful remains False, successful_download_time remains None

                else:
                    # This case means image source wasn't found
                    print(f"  Could not find image source using either method.")
                    # download_successful remains False

            except Error as e:
                print(f"  Error processing page: {e}")
                # download_successful remains False
            except Exception as e: # Catch other potential errors
                print(f"  Error occurred: {e}")
                # download_successful remains False

            # Database logging happens AFTER try-except block to capture all outcomes
            try:
                if result is None: # New URL, perform INSERT
                    cur.execute("""
                        INSERT INTO downloaded_images (url, successful_download, try_download_datetime, successful_download_datetime)
                        VALUES (?, ?, ?, ?)
                    """, (url, 1 if download_successful else 0, try_download_time, successful_download_time))
                    print(f"  Inserted download status into database for: {url} (Success: {download_successful})")
                else: # Existing URL (must have failed before), perform UPDATE
                    cur.execute("""
                        UPDATE downloaded_images
                        SET successful_download = ?, try_download_datetime = ?, successful_download_datetime = ?
                        WHERE url = ?
                    """, (1 if download_successful else 0, try_download_time, successful_download_time, url))
                    print(f"  Updated download status in database for: {url} (Success: {download_successful})")

                conn.commit()
            except sqlite3.Error as db_err:
                 print(f"  Error saving download status to database: {db_err}")
                 conn.rollback()

        await browser.close()


async def main():
    print("Starting Real Python Hero Image Extractor!")

    # Initialize database connection and create/update table if it doesn't exist
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        # Create table with new columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS downloaded_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                successful_download INTEGER NOT NULL,
                try_download_datetime TEXT NOT NULL,
                successful_download_datetime TEXT
            )
        """)
        # Add columns if they don't exist (for backward compatibility)
        try:
            cur.execute("ALTER TABLE downloaded_images ADD COLUMN successful_download INTEGER NOT NULL DEFAULT 0")
            print("Added column 'successful_download' to table.")
        except sqlite3.OperationalError:
            pass # Column likely already exists
        try:
            cur.execute("ALTER TABLE downloaded_images ADD COLUMN try_download_datetime TEXT NOT NULL DEFAULT ' '" ) # Default needed for existing rows
            # Set a default for existing rows - might need adjustment based on desired default
            cur.execute("UPDATE downloaded_images SET try_download_datetime = ? WHERE try_download_datetime = ' '", (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
            print("Added column 'try_download_datetime' to table.")
        except sqlite3.OperationalError:
            pass # Column likely already exists
        try:
            cur.execute("ALTER TABLE downloaded_images ADD COLUMN successful_download_datetime TEXT")
            print("Added column 'successful_download_datetime' to table.")
        except sqlite3.OperationalError:
            pass # Column likely already exists

        conn.commit()
        print(f"Database '{DB_NAME}' initialized/updated.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.close()
        return # Exit if database initialization fails


    urls = [
        "https://realpython.com/list-comprehension-python/",
        "https://realpython.com/python-dictionary-comprehension/",
        "https://realpython.com/python-metaclasses/",
        "https://realpython.com/python-set-comprehension/",
        "https://realpython.com/videos/dictionary-comprehensions-overview/",
        "https://realpython.com/invalid-url-test/", # Added for testing error handling
    ]

    if conn: # Proceed only if connection is successful
        try:
            await extract_hero_image_from_urls(urls, conn)
        finally:
            # Ensure the database connection is closed
             print("Closing database connection.")
             conn.close()


if __name__ == "__main__":
    asyncio.run(main())
