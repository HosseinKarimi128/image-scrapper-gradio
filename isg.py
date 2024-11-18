import os
import requests
import gradio as gr
import csv
from urllib.parse import urlencode
from pathlib import Path
import pandas as pd
import logging
from datetime import datetime

# Setup Logging
LOG_FILE = 'app.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')
DOWNLOAD_FOLDER = "downloaded_images"

# Ensure the download folder exists
Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
logger.info(f"Download folder '{DOWNLOAD_FOLDER}' is ready.")

def sanitize_filename(name):
    """Sanitize filenames by replacing invalid characters with underscores."""
    sanitized = "".join([c if c.isalnum() or c in (' ', '_') else "_" for c in name])
    logger.debug(f"Sanitized filename: Original='{name}', Sanitized='{sanitized}'")
    return sanitized

def search_and_download_images(query, num_images, save_folder):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    params = {
        "engine": "google",
        "q": query,
        "tbm": "isch",
        "api_key": SERPAPI_API_KEY,
        "ijn": "0"
    }

    image_urls = []
    downloaded_images = []
    logger.info(f"Starting image search for query='{query}' with num_images={num_images}")

    try:
        while len(image_urls) < num_images:
            logger.debug(f"Making request to SerpAPI with params={params}")
            response = requests.get("https://serpapi.com/search", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Extract image URLs
            new_images = data.get("images_results", [])
            if not new_images:
                logger.warning("No more images found in the search results.")
                break  # No more images found

            for img in new_images:
                url = img.get('original') or img.get('image')
                if url:
                    image_urls.append(url)
                    logger.debug(f"Found image URL: {url}")
                if len(image_urls) >= num_images:
                    break

            params["ijn"] = str(int(params["ijn"]) + 1)  # Next page
            logger.debug(f"Incremented page index to {params['ijn']}")

        # Limit to the requested number
        image_urls = image_urls[:num_images]
        logger.info(f"Total image URLs collected: {len(image_urls)}")

        for idx, url in enumerate(image_urls):
            try:
                logger.debug(f"Downloading image {idx + 1}/{len(image_urls)} from URL: {url}")
                img_data = requests.get(url, headers=headers, timeout=10)
                img_data.raise_for_status()
                file_extension = url.split('.')[-1].split('?')[0]
                if len(file_extension) > 4 or not file_extension.isalnum():
                    file_extension = 'jpg'
                file_path = os.path.join(save_folder, f"image_{idx + 1}.{file_extension}")
                with open(file_path, 'wb') as f:
                    f.write(img_data.content)
                downloaded_images.append(file_path)
                logger.info(f"Downloaded image saved to: {file_path}")
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")

        if not downloaded_images:
            message = f"No images were downloaded for keyword: {query}. Please try a different query or reduce the number."
            logger.warning(message)
            return [], message

        success_message = f"Downloaded {len(downloaded_images)} images for keyword: {query}."
        logger.info(success_message)
        return downloaded_images, success_message

    except Exception as e:
        error_message = f"An error occurred while downloading images for keyword: {query}. Error: {e}"
        logger.error(error_message)
        return [], error_message

def clear_downloaded_images():
    """Function to clear the download folder."""
    logger.info("Attempting to clear the download folder.")
    try:
        for file in Path(DOWNLOAD_FOLDER).glob("*"):
            if file.is_dir():
                for subfile in file.glob("*"):
                    subfile.unlink()
                file.rmdir()
                logger.debug(f"Removed directory: {file}")
            else:
                file.unlink()
                logger.debug(f"Removed file: {file}")
        success_message = "Download folder cleared."
        logger.info(success_message)
        return success_message
    except Exception as e:
        error_message = f"Failed to clear download folder: {e}"
        logger.error(error_message)
        return error_message

def download_images_single(query, num_images):
    """Function to handle single image download."""
    logger.info(f"Initiating single download with query='{query}' and num_images={num_images}")
    sanitized_query = sanitize_filename(query)
    save_folder = os.path.join(DOWNLOAD_FOLDER, sanitized_query)
    Path(save_folder).mkdir(parents=True, exist_ok=True)
    logger.debug(f"Images will be saved to: {save_folder}")

    images, status = search_and_download_images(query, int(num_images), save_folder)
    if isinstance(images, list) and images:
        # Convert file paths to absolute URLs for Gradio Gallery
        absolute_paths = [f"file://{os.path.abspath(path)}" for path in images]
        logger.debug(f"Generated absolute paths for images: {absolute_paths}")
        return absolute_paths, status
    else:
        return [], status

def download_images_batch(csv_file):
    """Function to handle batch image downloads from CSV."""
    logger.info("Starting batch download process.")
    if csv_file is None:
        message = "No CSV file uploaded."
        logger.warning(message)
        return message

    try:
        # Read the CSV file using pandas
        df = pd.read_csv(csv_file.name)
        logger.debug(f"CSV file '{csv_file.name}' read successfully.")

        # Normalize column names to lowercase
        df.columns = [col.lower() for col in df.columns]

        # Validate CSV columns
        required_columns = {'keyword', 'numbers', 'category'}
        if not required_columns.issubset(df.columns):
            message = "CSV file must contain the following columns: 'keyword', 'numbers', 'category'."
            logger.error(message)
            return message

        # Process each row
        statuses = []
        for index, row in df.iterrows():
            keyword = str(row['keyword']).strip()
            numbers = row['numbers']
            category = str(row['category']).strip()

            logger.debug(f"Processing row {index + 1}: keyword='{keyword}', numbers={numbers}, category='{category}'")

            if not keyword or not category or not isinstance(numbers, (int, float)) or numbers < 1:
                status = f"Row {index + 1}: Invalid data. Skipped."
                statuses.append(status)
                logger.warning(status)
                continue

            sanitized_keyword = sanitize_filename(keyword)
            sanitized_category = sanitize_filename(category)

            # Create category and keyword folders
            category_folder = os.path.join(DOWNLOAD_FOLDER, sanitized_category)
            keyword_folder = os.path.join(category_folder, sanitized_keyword)
            Path(keyword_folder).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created folder structure: {keyword_folder}")

            images, status = search_and_download_images(keyword, int(numbers), keyword_folder)
            statuses.append(status)

        # Combine all statuses
        final_status = "\n".join(statuses)
        logger.info("Batch download completed.")
        return final_status

    except Exception as e:
        error_message = f"An error occurred while processing the CSV file. Error: {e}"
        logger.error(error_message)
        return error_message

def generate_empty_csv():
    """Generate an empty CSV with the required columns."""
    output_path = "empty_template.csv"
    logger.info(f"Generating empty CSV template at '{output_path}'.")
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['keyword', 'numbers', 'category'])
        logger.info("Empty CSV template generated successfully.")
        return output_path
    except Exception as e:
        error_message = f"Failed to generate empty CSV template: {e}"
        logger.error(error_message)
        return error_message

# Define Gradio Interface
with gr.Blocks() as demo:
    gr.Markdown("# 🖼️ Image Downloader")

    with gr.Tab("Batch Download"):
        gr.Markdown("### Batch Download Images from CSV")
        with gr.Row():
            upload_csv = gr.File(label="Upload CSV File", file_types=['.csv'])
            download_template = gr.File(label="Download Empty CSV Template")
            download_template_button = gr.Button("Download Template")

        download_template_button.click(
            fn=generate_empty_csv,
            inputs=None,
            outputs=download_template
        )

        process_batch = gr.Button("Start Batch Download")
        batch_status = gr.Textbox(label="Batch Download Status", lines=10, interactive=False)

        process_batch.click(
            fn=download_images_batch,
            inputs=upload_csv,
            outputs=batch_status
        )

    with gr.Tab("Single Download"):
        gr.Markdown("### Download Images Individually")
        
        with gr.Row():
            query = gr.Textbox(label="Search Query", placeholder="e.g., Golden Retriever, Elon Musk, Quantum Physics")
            num = gr.Slider(label="Number of Images", minimum=1, maximum=20, step=1, value=5)
        
        download_button = gr.Button("Download Images")
        clear_button = gr.Button("Clear Downloaded Images")
        
        gallery = gr.Gallery(label="Downloaded Images")  # Removed .style(grid=[5])
        output_text = gr.Textbox(label="Status", interactive=False)
        
        download_button.click(
            fn=download_images_single, 
            inputs=[query, num], 
            outputs=[gallery, output_text]
        )
        
        clear_button.click(
            fn=clear_downloaded_images,
            inputs=None,
            outputs=output_text
        )

    gr.Markdown("""
    ---
    **Note:**
    - Ensure that your SerpAPI key is valid and has sufficient quota.
    - The downloaded images will be saved in the `downloaded_images` folder within the current working directory.
    - For batch downloads, the folder structure will be organized by category and keyword.
    - Refer to the `app.log` file for detailed logs of the application's operations.
    """)

# Launch the Gradio app
if __name__ == "__main__":
    logger.info("Launching Gradio app.")
    demo.launch()
