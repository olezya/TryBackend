from fastapi import APIRouter, Query, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from cloudinary_config import get_cloudinary
from db import file_services
from db.database import get_db
from typing import List, Optional
import cloudinary
import cloudinary.uploader
from datetime import datetime
from auth.oauth2 import get_current_user
from db.models import Dbuser, UploadedFile
from schemas import FileUploadOut

router = APIRouter(prefix="/files", tags=["files"])

cloudinary = get_cloudinary()


@router.post("/", response_model=FileUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file, folder=f"user_uploads/{user.id}"
        )

        # Save to database
        db_file = UploadedFile(
            user_id=user.id,
            file_name=file.filename,
            file_url=upload_result["secure_url"],
            public_id=upload_result["public_id"],
            upload_date=datetime.utcnow(),
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


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    db_file = (
        db.query(UploadedFile)
        .filter(UploadedFile.id == file_id, UploadedFile.user_id == user.id)
        .first()
    )

    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    try:
        # Delete from Cloudinary
        cloudinary.uploader.destroy(db_file.public_id)

        # Delete from database
        db.delete(db_file)
        db.commit()

        return {"message": "File deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File deletion failed: {str(e)}",
        )


@router.get("/{file_id}", response_model=FileUploadOut)
async def get_file_by_id(
    file_id: int,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    db_file = file_services.get_file_by_id(db, file_id=file_id)
    if not (user.is_superuser or db_file.user_id == user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this file")

    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found ",
        )
    return db_file


@router.get("/", response_model=List[FileUploadOut])
async def get_files(
    user_id: Optional[int] = Query(None, description="Filter by user ID (admin only)"),
    filename_contains: Optional[str] = Query(
        None, description="Search for files containing this string in name"
    ),
    uploaded_before: Optional[datetime] = Query(
        None, description="Filter files uploaded before this date (Format: YYYY-MM-DD)"
    ),
    uploaded_after: Optional[datetime] = Query(
        None, description="Filter files uploaded after this date (Format: YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    if not (current_user.is_superuser or user_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this files")
    return file_services.get_files_with_filters(
        db=db,
        current_user=current_user,
        user_id=user_id,
        filename_contains=filename_contains,
        uploaded_before=uploaded_before,
        uploaded_after=uploaded_after,
    )
