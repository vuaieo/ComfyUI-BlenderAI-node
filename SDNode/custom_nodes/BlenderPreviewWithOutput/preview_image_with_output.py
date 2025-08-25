import os
import json
import random
import numpy as np
from pathlib import Path
from PIL import Image

try:
    from PIL import PngInfo
except ImportError:
    # For newer PIL versions, PngInfo might be in a different location
    try:
        from PIL.PngImagePlugin import PngInfo
    except ImportError:
        # Fallback for other PIL versions
        PngInfo = None

import folder_paths
import comfy.cli_args as args


class PreviewImageWithOutput:
    """
    Preview with Output - A preview node that displays images and also outputs them for use by other nodes.
    """
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + ''.join(random.choice("abcdefghijklmnopqrstupvxyz") for _ in range(5))
        self.compress_level = 1

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", ),
                "filename_prefix": ("STRING", {"default": "ComfyUI_Preview"}),
                "output_dir": ("STRING", {"default": ""}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ("IMAGE",)  # Output the images for other nodes to use
    OUTPUT_NODE = False  # Not an output-only node since it has outputs
    FUNCTION = "preview_and_output_images"
    CATEGORY = "Blender"

    def preview_and_output_images(self, images, filename_prefix="ComfyUI_Preview", output_dir="", prompt=None, extra_pnginfo=None):
        """
        Save images to temp directory for preview and return them as output.
        """
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])

        results = list()
        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            metadata = None
            if not args.disable_metadata and PngInfo is not None:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            if metadata is not None:
                img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
            else:
                img.save(os.path.join(full_output_folder, file), compress_level=self.compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        # Return both the UI results for preview and the images for output
        return {
            "ui": {"images": results},
            "result": (images,)  # Return the images as tuple for output socket
        }


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "BlenderPreviewWithOutput": PreviewImageWithOutput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BlenderPreviewWithOutput": "Preview with Output",
}
