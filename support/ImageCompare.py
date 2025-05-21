from skimage.metrics import structural_similarity as ssim
import cv2
import numpy as np

class ImageCompare:
    def compute_visibility(carved_path, original_path):
        carved = cv2.imread(carved_path)
        original = cv2.imread(original_path)

        if carved is None or original is None:
            print("Error loading images.")
            return None

        # Resize both images to the same shape
        original = cv2.resize(original, (carved.shape[1], carved.shape[0]))

        # Convert to grayscale
        carved_gray = cv2.cvtColor(carved, cv2.COLOR_BGR2GRAY)
        original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

        # Compute SSIM
        score, _ = ssim(carved_gray, original_gray, full=True)
        visibility_percentage = score * 100
        print(f"Estimated visibility: {visibility_percentage:.2f}")
        return visibility_percentage

# Example usage
# compute_visibility("/home/akila/Pictures/wat.gif", "/home/akila/Pictures/00000005.gif")
