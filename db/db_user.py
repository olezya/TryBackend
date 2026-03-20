from sqlalchemy.orm import Session
from db.models import Dbuser
from schemas import UserUpdate, UserBase
from .Hash import Hash


def create_user(db: Session, request: UserBase) -> Dbuser:
    new_user = Dbuser(
        username=request.username,
        email=request.email,
        phone_number=request.phone_number,
        hashed_password=Hash.bcrypt(request.password),  # Hashing stays here
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def get_user_by_username(db: Session, username: str) -> Dbuser:
    return db.query(Dbuser).filter(Dbuser.username == username).first()


def get_user_by_email(db: Session, email: str) -> Dbuser:
    return db.query(Dbuser).filter(Dbuser.email == email).first()


def get_user_by_phone(db: Session, phone: str) -> Dbuser:
    return db.query(Dbuser).filter(Dbuser.phone_number == phone).first()


def verify_password(user: Dbuser, password: str) -> bool:
    return Hash.verify(password, user.hashed_password)


def update_user(
    db: Session,
    user_id: int,
    request: UserUpdate,
    current_password: str = None,
    is_admin: bool = False,
) -> Dbuser:
    user = db.query(Dbuser).filter(Dbuser.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    update_data = request.model_dump(exclude_unset=True)

    # Define sensitive fields
    SENSITIVE_FIELDS = [
        "password",
        "email",
        "username",
    ]
    needs_token_reset = any(field in update_data for field in SENSITIVE_FIELDS)
    is_admin_role_change = "is_superuser" in update_data

    # Admin role change validation
    if is_admin_role_change and not is_admin:
        raise ValueError("Only admins can change user roles")

    # Password update logic
    if "password" in update_data:
        if not is_admin:
            if not current_password:
                raise ValueError("Current password required for password change")
            if not Hash.verify(current_password, user.hashed_password):
                raise ValueError("Current password is incorrect")

        user.hashed_password = Hash.bcrypt(update_data["password"])
        del update_data["password"]

    # Apply other updates
    for field, value in update_data.items():
        if hasattr(user, field) and field != "current_password":
            setattr(user, field, value)

    # Invalidate tokens if sensitive fields changed (except admin role changes)
    if needs_token_reset and not is_admin_role_change:
        user.token_version += 1

    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> Dbuser:
    """Get user by ID"""
    return db.query(Dbuser).filter(Dbuser.id == user_id).first()
