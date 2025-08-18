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

    
    def block_compare(carved_path, groundtruth_path, block_size=512, verbose=False):
        with open(carved_path, 'rb') as f_carved, open(groundtruth_path, 'rb') as f_truth:
            carved = f_carved.read()
            truth = f_truth.read()

        total_bytes = len(truth)
        matched_bytes = sum(1 for a, b in zip(carved, truth) if a == b)

        # block-level recovery
        total_blocks = total_bytes // block_size
        matched_blocks = 0
        for i in range(0, min(len(carved), len(truth)), block_size):
            block_carved = carved[i:i+block_size]
            block_truth = truth[i:i+block_size]
            if block_carved == block_truth:
                matched_blocks += 1
            elif verbose:
                print(f"Block mismatch at offset {i}")

        byte_recovery_pct = (matched_bytes / total_bytes) * 100 if total_bytes else 0
        block_recovery_pct = (matched_blocks / total_blocks) * 100 if total_blocks else 0

        print(f"Matched Bytes: {matched_bytes}/{total_bytes} ({byte_recovery_pct:.2f}%)")
        print(f"Matched Blocks: {matched_blocks}/{total_blocks} ({block_recovery_pct:.2f}%)")

        return {
            "matched_bytes": matched_bytes,
            "total_bytes": total_bytes,
            "byte_recovery_pct": byte_recovery_pct,
            "matched_blocks": matched_blocks,
            "total_blocks": total_blocks,
            "block_recovery_pct": block_recovery_pct
        }




# Example usage
# compute_visibility("/home/akila/Pictures/wat.gif", "/home/akila/Pictures/00000005.gif")
