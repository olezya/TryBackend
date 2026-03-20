from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from auth.oauth2 import create_access_token, get_current_user
from db.database import get_db
from schemas import TokenResponse, UserBase, UpdateUserResponse, UserDisplay, UserUpdate
from db import db_user
from db.models import Dbuser
import re
from db.models import IsActive
from typing import List, Optional
from sqlalchemy import or_
from fastapi import Query
from fastapi import Response

router = APIRouter(prefix="/user", tags=["user"])

# Validation patterns
USERNAME_REGEX = r"^[a-zA-Z0-9_]{3,50}$"
PASSWORD_REGEX = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
PHONE_REGEX = r"^\+[1-9]\d{1,14}$"  # E.164 format


def validate_username(username: str):
    if not re.match(USERNAME_REGEX, username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be 3-50 characters (letters, numbers, underscores)",
        )


def validate_password(password: str):
    if not re.match(PASSWORD_REGEX, password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special character",
        )


def validate_phone(phone_number: str):
    if not re.match(PHONE_REGEX, phone_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone must be in E.164 format (+[country code][number])",
        )


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=UserDisplay
)
def register_user(request: UserBase, db: Session = Depends(get_db)):
    # Validate input fields
    try:
        validate_username(request.username)
        validate_password(request.password)
        validate_phone(request.phone_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Check for existing user conflicts
    if db_user.get_user_by_username(db, request.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        )
    if db_user.get_user_by_email(db, request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    if db_user.get_user_by_phone(db, request.phone_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Phone number already in use"
        )

    # Create the user
    new_user = db_user.create_user(db, request)
    return UserDisplay.model_validate(new_user)


@router.post("/login", response_model=TokenResponse)
def login(
    request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db_user.get_user_by_username(db, request.username)
    if not user or not db_user.verify_password(user, request.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    access_token = create_access_token(user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.patch("/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    # Get the target user
    target_user = db.query(Dbuser).filter(Dbuser.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent updates on soft-deleted accounts
    if target_user.status == IsActive.deleted:
        raise HTTPException(
            status_code=400, detail="User account is deactivated or deleted"
        )

    # Permission check
    is_admin = current_user.is_superuser
    if not is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile",
        )

    update_data = request.model_dump(exclude_unset=True)

    # Validation
    if "username" in update_data:
        validate_username(update_data["username"])
    if "password" in update_data:
        validate_password(update_data["password"])
    if "phone_number" in update_data:
        validate_phone(update_data["phone_number"])

    # Prevent non-admins from changing role/status
    if "is_superuser" in update_data and not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can modify user roles")
    if "status" in update_data and not is_admin:
        raise HTTPException(
            status_code=403, detail="Only admins can change user status"
        )

    # Handle sensitive field changes
    SENSITIVE_FIELDS = ["password", "email", "username"]
    is_updating_sensitive_field = any(
        field in update_data for field in SENSITIVE_FIELDS
    )

    # Require current password for non-admins updating sensitive fields
    if not is_admin and is_updating_sensitive_field:
        if not request.current_password:
            raise HTTPException(
                status_code=400,
                detail="Current password required for sensitive field changes",
            )

    # Perform the update
    try:
        updated_user = db_user.update_user(
            db=db,
            user_id=user_id,
            request=request,
            current_password=request.current_password if not is_admin else None,
            is_admin=is_admin,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Token regen if sensitive data changed
    response = {
        "message": "User updated successfully",
        "user": UserDisplay.from_orm(updated_user),
    }

    if is_updating_sensitive_field:
        response.update(
            {
                "access_token": create_access_token(updated_user),
                "token_type": "bearer",
            }
        )

    return response


# Admin sees users' list
@router.get("/", response_model=List[UserDisplay], summary="Admin search users")
def get_all_users(
    search_term: Optional[str] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    query = db.query(Dbuser).filter(Dbuser.status != IsActive.deleted)

    # 🔍 Fuzzy match on any field
    if search_term:
        search = f"%{search_term.strip()}%"
        query = query.filter(
            or_(
                Dbuser.username.ilike(search),
                Dbuser.email.ilike(search),
                Dbuser.phone_number.ilike(search),
            )
        )

    # 🔎 Specific filters
    if username:
        query = query.filter(Dbuser.username.ilike(f"%{username.strip()}%"))
    if email:
        query = query.filter(Dbuser.email.ilike(f"%{email.strip()}%"))
    if phone_number:
        query = query.filter(Dbuser.phone_number.ilike(f"%{phone_number.strip()}%"))

    return query.all()


# Admin sees user's info
@router.get("/{user_id}", response_model=UserDisplay, summary="Get user info")
def get_user_info(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    user = db.query(Dbuser).filter(Dbuser.id == user_id).first()

    if not user or user.status == IsActive.deleted:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this user"
        )

    return user


# Admin deletes user
@router.delete("/{user_id}", status_code=204, summary="Admin deletes a user")
def delete_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    user = db.query(Dbuser).filter(Dbuser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = IsActive.deleted
    db.commit()

    return Response(status_code=204)
