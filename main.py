import asyncio
import os
import re
from playwright.async_api import async_playwright, Error
import aiohttp
import aiofiles

IMAGES_DIR = "images"

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

async def extract_hero_image_from_urls(urls: list[str]):
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        print(f"Created directory: {IMAGES_DIR}")

    async with async_playwright() as p, aiohttp.ClientSession() as session:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        print("Extracting and downloading hero images...")
        for url in urls:
            print(f"Processing URL: {url}")
            image_src = None # Initialize image_src
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

                    await download_image(session, image_src, image_filepath)

                else:
                    # This case should now be less common unless both methods fail
                    print(f"  Could not find image source using either method.")
            except Error as e:
                print(f"  Error processing page: {e}")
            except Exception as e: # Catch other potential errors like locator timeout
                print(f"  Error occurred: {e}")

        await browser.close()


async def main():
    print("Starting Real Python Hero Image Extractor!")

    urls = [
        "https://realpython.com/list-comprehension-python/",
        "https://realpython.com/python-dictionary-comprehension/",
        "https://realpython.com/python-set-comprehension/",
        "https://realpython.com/videos/dictionary-comprehensions-overview/",
        "https://realpython.com/invalid-url-test/", # Added for testing error handling
    ]

    await extract_hero_image_from_urls(urls)


if __name__ == "__main__":
    asyncio.run(main())
