"""
zip_builder.py
--------------
Creates a zip archive of all files inside a job's download directory.
"""

import os
import zipfile
from source.logger import get_logger

logger = get_logger(__name__)

# Gmail's limit is 25MB total. We limit uncompressed contents to 20MB to be safe,
# accounting for zip headers and base64 email encoding overhead.
MAX_ZIP_CONTENT_BYTES = 20 * 1024 * 1024

def create_zip(download_dir: str, matter_id: str, category: str) -> tuple[str, list[str]]:
    """
    Zip the contents of download_dir into a single archive.

    The archive is placed *next to* (not inside) the download directory so
    that we can safely delete the directory afterwards.

    Args:
        download_dir: Path to the directory that holds the downloaded files.
        matter_id:    Used to name the output zip file.
        category:     Used to name the output zip file.

    Returns:
        Tuple of (Absolute path to the created zip file, list of filenames that were skipped due to size).

    Raises:
        FileNotFoundError: If download_dir does not exist.
        RuntimeError: If no files were found to zip.
    """
    if not os.path.isdir(download_dir):
        raise FileNotFoundError(f"Download directory not found: {download_dir}")

    all_files = [
        f for f in os.listdir(download_dir)
        if os.path.isfile(os.path.join(download_dir, f))
    ]

    if not all_files:
        raise RuntimeError(f"No files found in '{download_dir}' to zip.")

    # Build a safe filename: "M12205_Exhibits.zip"
    safe_category = category.replace(" ", "_")
    zip_name = f"{matter_id}_{safe_category}.zip"

    # Place the zip one level up from the download dir (e.g. inside assets/)
    parent_dir = os.path.dirname(download_dir)
    zip_path = os.path.join(parent_dir, zip_name)

    # Sort files by size (smallest first) to fit as many as possible
    file_sizes = []
    for filename in all_files:
        full_path = os.path.join(download_dir, filename)
        file_sizes.append((filename, full_path, os.path.getsize(full_path)))
    
    file_sizes.sort(key=lambda x: x[2])

    skipped_files = []
    total_bytes = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, full_path, size in file_sizes:
            if total_bytes + size > MAX_ZIP_CONTENT_BYTES:
                logger.warning("Skipping '%s' (%d bytes) to stay under zip size limit.", filename, size)
                skipped_files.append(filename)
                continue

            zf.write(full_path, arcname=filename)
            total_bytes += size
            logger.debug("Zipped: %s (%d bytes)", filename, size)

    included_count = len(all_files) - len(skipped_files)
    logger.info(
        "Created zip '%s' with %d/%d file(s) (Total: %d bytes) for Matter ID: %s",
        zip_path, included_count, len(all_files), total_bytes, matter_id
    )
    return zip_path, skipped_files
