from PIL import Image, ImageFile
import numpy as np

# Allow Pillow to load truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True
class ImageCheck:
    def compute_visibility_percentage(image_path, diff_threshold=10):
        """
        Load the image, convert it to grayscale, and compute the percentage
        of pixels that differ from the background (assumed as the mode) by more than diff_threshold.
        
        :param image_path: Path to the image file.
        :param diff_threshold: Minimum absolute difference to consider a pixel non-background.
        :return: Percentage (0-100) of pixels that are not background, and the background intensity.
        """
        try:
            with Image.open(image_path) as img:
                grayscale_img = img.convert("L")
            arr = np.array(grayscale_img)
            total_pixels = arr.size

            # Estimate background as the mode of the pixel values
            counts = np.bincount(arr.flatten())
            background = np.argmax(counts)
            
            # Count pixels that differ significantly from the background value
            visible_pixels = np.sum(np.abs(arr - background) > diff_threshold)
            visibility_percentage = (visible_pixels / total_pixels) * 100
            return visibility_percentage, background
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            return None, None

    def __init__(image_path):
        # image_path = "/home/akila/Pictures/00000000.gif"
        
        # First, check if the image is structurally valid.
        try:
            with Image.open(image_path) as img:
                img.verify()  # This does an internal consistency check.
            print("Image is valid and viewable (structurally).")
        except Exception as e:
            print("Image is corrupted or invalid:", e)
            return

        # Since verify() closes the file, re-open the image to load pixel data.
        visibility, bg_value = compute_visibility_percentage(image_path, diff_threshold=10)
        if visibility is not None:
            print(f"Estimated background intensity: {bg_value}")
            print(f"Visibility (non-background area): {visibility:.2f}%")
        else:
            print("Could not compute visibility percentage.")

    # if __name__ == "__main__":
    #     main()


