"""
zip_builder.py
--------------
Creates a zip archive of all files inside a job's download directory.
"""

import os
import zipfile
from source.logger import get_logger

logger = get_logger(__name__)


def create_zip(download_dir: str, matter_id: str, category: str) -> str:
    """
    Zip the contents of download_dir into a single archive.

    The archive is placed *next to* (not inside) the download directory so
    that we can safely delete the directory afterwards.

    Args:
        download_dir: Path to the directory that holds the downloaded files.
        matter_id:    Used to name the output zip file.
        category:     Used to name the output zip file.

    Returns:
        Absolute path to the created zip file.

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

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in all_files:
            full_path = os.path.join(download_dir, filename)
            zf.write(full_path, arcname=filename)
            logger.debug("Zipped: %s", filename)

    logger.info(
        "Created zip '%s' with %d file(s) for Matter ID: %s",
        zip_path, len(all_files), matter_id
    )
    return zip_path
