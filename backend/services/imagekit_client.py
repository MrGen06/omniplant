import os
import time
from imagekitio import ImageKit

imagekit = ImageKit(
    private_key=os.getenv("IMAGEKIT_PRIVATE_KEY"),
)

def upload_file_bytes(file_bytes: bytes, filename: str):
    """
    Upload a file's raw bytes to ImageKit.

    Parameters:
        file_bytes: bytes
        filename: str

    Returns:
        Upload response from ImageKit.
    """
    result = imagekit.files.upload(
        file=file_bytes,
        file_name=filename,
        folder="/omniplant/pdfs",
        use_unique_file_name=False,
    )
    return result

def upload_file(file):
    """
    Upload a file to ImageKit.

    Parameters:
        file: UploadFile (FastAPI) or any file-like object with:
            - file.file (binary stream)
            - file.filename
            - file.content_type

    Returns:
        Upload response from ImageKit.
    """

    file_name = file.filename or f"upload_{int(time.time())}.pdf"

    # Read bytes from uploaded file
    file_bytes = file.file.read()

    return upload_file_bytes(file_bytes, file_name)