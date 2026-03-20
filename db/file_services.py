from typing import List, Optional
from datetime import datetime
import cloudinary.uploader
from fastapi import HTTPException, status

from sqlalchemy.orm import Session

from db.models import Dbuser, UploadedFile


def upload_file(db: Session, user_id: int, file, folder: str = "user_uploads"):
    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(file.file, folder=folder)

        # Save to database
        db_file = UploadedFile(
            user_id=user_id,
            file_name=file.filename,
            file_url=upload_result["secure_url"],
            public_id=upload_result["public_id"],
        )

        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        return db_file

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}",
        )


def delete_file(db: Session, file_id: int, user_id: int):
    try:
        # Get file from database
        db_file = (
            db.query(UploadedFile)
            .filter(UploadedFile.id == file_id, UploadedFile.user_id == user_id)
            .first()
        )

        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Delete from Cloudinary
        cloudinary.uploader.destroy(db_file.public_id)

        # Delete from database
        db.delete(db_file)
        db.commit()

        return db_file

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File deletion failed: {str(e)}",
        )


def get_file_by_id(db: Session, file_id: int):
    query = db.query(UploadedFile).filter(UploadedFile.id == file_id)

    return query.first()


def get_files_with_filters(
    db: Session,
    current_user: Dbuser,
    user_id: Optional[int] = None,
    filename_contains: Optional[str] = None,
    uploaded_before: Optional[datetime] = None,
    uploaded_after: Optional[datetime] = None,
) -> List[UploadedFile]:
    query = db.query(UploadedFile)

    # For non-superusers, they can only see their own files
    if not current_user.is_superuser:
        query = query.filter(UploadedFile.user_id == current_user.id)
    # Superusers can filter by specific user_id if provided
    elif user_id is not None:
        query = query.filter(UploadedFile.user_id == user_id)

    # Filename contains filter (case insensitive)
    if filename_contains:
        query = query.filter(UploadedFile.file_name.ilike(f"%{filename_contains}%"))

    # Date range filters
    if uploaded_after:
        query = query.filter(UploadedFile.upload_date >= uploaded_after)
    if uploaded_before:
        query = query.filter(UploadedFile.upload_date <= uploaded_before)

    return query.all()
