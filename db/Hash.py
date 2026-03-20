from passlib.context import CryptContext
from sqlalchemy.orm import Session  # Changed from requests import Session
from db.models import Dbuser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Hash:
    @staticmethod
    def bcrypt(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)  # Arguments fixed

    @staticmethod
    def update_password(
        db: Session,
        user: Dbuser,
        new_password: str,
        current_password: str = None,
        is_admin: bool = False,
    ) -> Dbuser:
        """
        Updates user password with security checks.
        For regular users: requires current_password verification
        For admins: can bypass current_password check
        """
        if not is_admin and current_password is None:
            raise ValueError("Current password is required for non-admin users")

        if not is_admin and not Hash.verify(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user.hashed_password = Hash.bcrypt(new_password)
        user.token_version += 1  # Invalidate existing tokens
        db.commit()
        db.refresh(user)
        return user
