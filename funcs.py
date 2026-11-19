import os
import shutil
import tempfile

from PIL import Image, ImageOps, ImageSequence


# --------------------------------------------------
# FILE INFORMATION
# --------------------------------------------------

def get_file_size(file_path):
    return os.path.getsize(file_path)


def format_size(size):

    if size < 1024:
        return f"{size} B"

    elif size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"

    else:
        return f"{size / (1024 ** 2):.2f} MB"


# --------------------------------------------------
# INPUT MANAGEMENT
# --------------------------------------------------

def get_image_paths():

    paths = input(
        "Enter image paths (separated by commas): "
    )

    image_paths = paths.split(",")

    return [
        path.strip().strip('"')
        for path in image_paths
        if path.strip()
    ]


def validate_image_paths(image_paths):

    valid_paths = []

    for path in image_paths:

        if os.path.isfile(path):
            valid_paths.append(path)

        else:
            print(f"File not found: {path}")

    return valid_paths


# --------------------------------------------------
# OUTPUT MANAGEMENT
# --------------------------------------------------

def create_output_folder():

    output_folder = "Compressed"

    os.makedirs(output_folder, exist_ok=True)

    return os.path.abspath(output_folder)


def get_unique_path(path):

    if not os.path.exists(path):
        return path

    name, extension = os.path.splitext(path)

    counter = 1

    while True:

        new_path = f"{name}_{counter}{extension}"

        if not os.path.exists(new_path):
            return new_path

        counter += 1


# --------------------------------------------------
# IMAGE COMPRESSION HELPERS
# --------------------------------------------------

def get_quality_levels(quality):

    levels = [
        quality,
        quality - 15,
        quality - 30,
        1
    ]

    return sorted(
        set(max(1, level) for level in levels),
        reverse=True
    )


def save_candidate(image, temp_dir, image_format, **options):

    extension = image_format.lower()

    if extension == "jpeg":
        extension = "jpg"

    output_path = os.path.join(
        temp_dir,
        f"candidate_{len(os.listdir(temp_dir))}.{extension}"
    )

    try:

        image.save(
            output_path,
            format=image_format,
            **options
        )

        if os.path.isfile(output_path):
            return output_path

    except Exception:
        pass

    return None


def get_best_candidate(candidates):

    valid_candidates = [
        path for path in candidates
        if path and os.path.isfile(path)
    ]

    if not valid_candidates:
        return None

    return min(
        valid_candidates,
        key=os.path.getsize
    )


# --------------------------------------------------
# STATIC IMAGE COMPRESSION
# --------------------------------------------------

def compress_static_image(
    image,
    image_format,
    quality,
    temp_dir,
    has_alpha
):

    candidates = []

    quality_levels = get_quality_levels(quality)

    # PNG - Lossless
    if image_format == "PNG":

        candidate = save_candidate(
            image,
            temp_dir,
            "PNG",
            optimize=True,
            compress_level=9
        )

        candidates.append(candidate)

    # JPEG
    if image_format == "JPEG" or not has_alpha:

        rgb_image = image.convert("RGB")

        for level in quality_levels:

            candidate = save_candidate(
                rgb_image,
                temp_dir,
                "JPEG",
                quality=level,
                optimize=True,
                progressive=True
            )

            candidates.append(candidate)

    # WEBP
    for level in quality_levels:

        candidate = save_candidate(
            image,
            temp_dir,
            "WEBP",
            quality=level,
            method=6
        )

        candidates.append(candidate)

    # BMP
    if image_format == "BMP":

        bmp_image = image

        if bmp_image.mode not in ("RGB", "RGBA"):
            bmp_image = bmp_image.convert("RGB")

        candidate = save_candidate(
            bmp_image,
            temp_dir,
            "BMP"
        )

        candidates.append(candidate)

    # TIFF
    if image_format == "TIFF":

        for compression in ("tiff_adobe_deflate", "tiff_lzw"):

            candidate = save_candidate(
                image,
                temp_dir,
                "TIFF",
                compression=compression
            )

            candidates.append(candidate)

    # ICO
    if image_format == "ICO":

        icon_sizes = sorted(image.ico.sizes())

        icon_image = image.convert("RGBA")

        candidate = save_candidate(
            icon_image,
            temp_dir,
            "ICO",
            sizes=icon_sizes
        )

        candidates.append(candidate)

    return get_best_candidate(candidates)


# --------------------------------------------------
# ANIMATED IMAGE COMPRESSION
# --------------------------------------------------

def compress_animated_image(
    image,
    image_format,
    temp_dir,
    quality
):

    frames = []

    durations = []

    for frame in ImageSequence.Iterator(image):

        frames.append(frame.convert("RGBA").copy())

        durations.append(
            frame.info.get("duration", 100)
        )

    if not frames:
        return None

    candidates = []

    loop = image.info.get("loop", 0)

    # GIF
    if image_format == "GIF":

        candidate = save_candidate(
            frames[0],
            temp_dir,
            "GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            disposal=2,
            optimize=True
        )

        candidates.append(candidate)

    # Animated WEBP
    for level in get_quality_levels(quality):

        candidate = save_candidate(
            frames[0],
            temp_dir,
            "WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            quality=level,
            method=6
        )

        candidates.append(candidate)

    return get_best_candidate(candidates)


# --------------------------------------------------
# MULTI-PAGE TIFF COMPRESSION
# --------------------------------------------------

def compress_multipage_tiff(image, temp_dir):

    frames = [
        frame.copy()
        for frame in ImageSequence.Iterator(image)
    ]

    if not frames:
        return None

    candidates = []

    for compression in (
        "tiff_adobe_deflate",
        "tiff_lzw"
    ):

        candidate = save_candidate(
            frames[0],
            temp_dir,
            "TIFF",
            save_all=True,
            append_images=frames[1:],
            compression=compression
        )

        candidates.append(candidate)

    return get_best_candidate(candidates)


# --------------------------------------------------
# MAIN COMPRESSION FUNCTION
# --------------------------------------------------

def compress_image(input_path, output_path, quality=75):

    supported_formats = [
        "JPEG",
        "PNG",
        "WEBP",
        "BMP",
        "GIF",
        "TIFF",
        "ICO"
    ]

    try:

        original_size = get_file_size(input_path)

        with Image.open(input_path) as source:

            image_format = source.format

            if image_format not in supported_formats:

                print(
                    f"Unsupported format: {input_path}"
                )

                return None

            image = ImageOps.exif_transpose(source.copy())

            is_animated = getattr(
                source,
                "is_animated",
                False
            )

            frame_count = getattr(
                source,
                "n_frames",
                1
            )

            has_alpha = (
                "A" in image.getbands()
                or "transparency" in source.info
            )

            with tempfile.TemporaryDirectory() as temp_dir:

                # Animated images
                if is_animated and frame_count > 1:

                    if image_format == "TIFF":

                        best_candidate = compress_multipage_tiff(
                            source,
                            temp_dir
                        )

                    else:

                        best_candidate = compress_animated_image(
                            source,
                            image_format,
                            temp_dir,
                            quality
                        )

                # Static images
                else:

                    if image_format == "ICO":

                        sizes = sorted(source.ico.sizes())

                        if sizes:
                            image = source.ico.getimage(
                                sizes[-1]
                            ).convert("RGBA")

                            has_alpha = True

                    best_candidate = compress_static_image(
                        image,
                        image_format,
                        quality,
                        temp_dir,
                        has_alpha
                    )

                if not best_candidate:

                    print("No compression candidate was created.")

                    return None

                compressed_size = get_file_size(
                    best_candidate
                )

                # Only accept smaller files
                if compressed_size >= original_size:

                    print(
                        "No smaller output was found."
                    )

                    return None

                # Get selected output format
                extension = os.path.splitext(
                    best_candidate
                )[1]

                base_path = os.path.splitext(
                    output_path
                )[0]

                final_path = get_unique_path(
                    base_path + extension
                )

                shutil.copy2(
                    best_candidate,
                    final_path
                )

                return final_path

    except Exception as error:

        print(
            f"Error compressing {input_path}: {error}"
        )

        return None


# --------------------------------------------------
# MAIN PROGRAM
# --------------------------------------------------

def main():

    print("=" * 45)
    print("          IMAGE COMPRESSOR")
    print("=" * 45)

    # Get image paths
    image_paths = get_image_paths()

    # Validate paths
    image_paths = validate_image_paths(image_paths)

    if not image_paths:

        print("No valid image files found!")

        return

    # Create output folder
    output_folder = create_output_folder()

    # Get quality
    while True:

        try:

            quality = int(
                input(
                    "Enter compression quality (1-100): "
                )
            )

            if 1 <= quality <= 100:
                break

            print(
                "Quality must be between 1 and 100!"
            )

        except ValueError:

            print(
                "Please enter a valid number!"
            )

    # Statistics
    total_original_size = 0
    total_compressed_size = 0
    successful_images = 0

    # Process images
    for image_path in image_paths:

        print("\n" + "-" * 45)

        print(
            f"Processing: {os.path.basename(image_path)}"
        )

        original_size = get_file_size(image_path)

        file_name = os.path.basename(image_path)

        output_path = os.path.join(
            output_folder,
            file_name
        )

        compressed_path = compress_image(
            image_path,
            output_path,
            quality
        )

        if compressed_path:

            compressed_size = get_file_size(
                compressed_path
            )

            saved_size = (
                original_size - compressed_size
            )

            reduction = (
                saved_size / original_size
            ) * 100

            successful_images += 1

            total_original_size += original_size

            total_compressed_size += compressed_size

            print("Compression successful!")

            print(
                f"Output: {os.path.basename(compressed_path)}"
            )

            print(
                f"Original Size: {format_size(original_size)}"
            )

            print(
                f"Compressed Size: {format_size(compressed_size)}"
            )

            print(
                f"Size Reduction: {reduction:.2f}%"
            )

        else:

            print(
                "Could not reduce the file size."
            )

    # Final report
    print("\n" + "=" * 45)

    print("COMPRESSION REPORT")

    print("=" * 45)

    print(
        f"Total Images: {len(image_paths)}"
    )

    print(
        f"Successfully Compressed: {successful_images}"
    )

    print(
        f"Not Compressed: {len(image_paths) - successful_images}"
    )

    if successful_images:

        total_saved = (
            total_original_size - total_compressed_size
        )

        total_reduction = (
            total_saved / total_original_size
        ) * 100

        print(
            f"Original Total: {format_size(total_original_size)}"
        )

        print(
            f"Compressed Total: {format_size(total_compressed_size)}"
        )

        print(
            f"Total Saved: {format_size(total_saved)}"
        )

        print(
            f"Total Reduction: {total_reduction:.2f}%"
        )

    print("\nOutput Folder:")

    print(output_folder)

    print("=" * 45)