
import os
import requests
import gradio as gr
from urllib.parse import urlencode
from pathlib import Path

# Constants
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')
DOWNLOAD_FOLDER = "downloaded_images"

# Ensure the download folder exists
Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

def search_and_download_images(query, num_images):
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

    try:
        while len(image_urls) < num_images:
            response = requests.get("https://serpapi.com/search", params=params, headers=headers)
            response.raise_for_status()  # Raise an error for bad status codes
            data = response.json()

            # Extract image URLs
            new_images = data.get("images_results", [])
            if not new_images:
                break  # No more images found

            for img in new_images:
                if 'original' in img:
                    image_urls.append(img['original'])
                elif 'image' in img:
                    image_urls.append(img['image'])

                if len(image_urls) >= num_images:
                    break

            params["ijn"] = str(int(params["ijn"]) + 1)  # Next page

        # Limit to the requested number
        image_urls = image_urls[:num_images]

        for idx, url in enumerate(image_urls):
            try:
                img_data = requests.get(url, headers=headers, timeout=10)
                img_data.raise_for_status()
                file_extension = url.split('.')[-1].split('?')[0]
                if len(file_extension) > 4 or not file_extension.isalnum():  # Handle URLs without proper extensions
                    file_extension = 'jpg'
                # Sanitize query to create valid filenames
                sanitized_query = "".join([c if c.isalnum() or c in (' ', '_') else "_" for c in query])
                file_path = os.path.join(DOWNLOAD_FOLDER, f"{sanitized_query}_{idx}.{file_extension}")
                with open(file_path, 'wb') as f:
                    f.write(img_data.content)
                downloaded_images.append(file_path)
            except Exception as e:
                print(f"Failed to download {url}: {e}")

        if not downloaded_images:
            return [], "No images were downloaded. Please try a different query or reduce the number."

        return downloaded_images, "Downloaded successfully."

    except Exception as e:
        return [], f"An error occurred: {e}"

def clear_downloaded_images():
    # Optional: Function to clear the download folder
    try:
        for file in Path(DOWNLOAD_FOLDER).glob("*"):
            file.unlink()
        return "Download folder cleared."
    except Exception as e:
        return f"Failed to clear download folder: {e}"

# Define Gradio Interface
with gr.Blocks() as demo:
    gr.Markdown("# Image Downloader")
    gr.Markdown("Enter the name of an object, person, or concept and specify the number of images to download.")
    
    with gr.Row():
        query = gr.Textbox(label="Search Query", placeholder="e.g., Golden Retriever, Elon Musk, Quantum Physics")
        num = gr.Slider(label="Number of Images", minimum=1, maximum=20, step=1, value=5)
    
    download_button = gr.Button("Download Images")
    clear_button = gr.Button("Clear Downloaded Images")
    
    gallery = gr.Gallery(label="Downloaded Images")  # Removed .style(grid=[5])
    output_text = gr.Textbox(label="Status", interactive=False)
    
    download_button.click(
        fn=search_and_download_images, 
        inputs=[query, num], 
        outputs=[gallery, output_text]
    )
    
    clear_button.click(
        fn=clear_downloaded_images,
        inputs=None,
        outputs=output_text
    )

# Launch the Gradio app
demo.launch()
