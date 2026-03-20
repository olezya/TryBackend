import cloudinary
from fastapi import HTTPException
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


def configure_cloudinary():
    try:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Cloudinary configuration failed: {str(e)}"
        )


def get_cloudinary():
    """Returns the configured cloudinary module"""
    if not all(
        [
            cloudinary.config().cloud_name,
            cloudinary.config().api_key,
            cloudinary.config().api_secret,
        ]
    ):
        configure_cloudinary()
    return cloudinary
