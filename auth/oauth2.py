from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from dotenv import load_dotenv
import os
from db.database import get_db
from db.models import Dbuser
 
 
load_dotenv()
 
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
 
 
def create_access_token(user: Dbuser, expires_delta: timedelta | None = None) -> str:
    to_encode = {
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "token_version": user.token_version,  # Include version
        "fresh": True,
    }
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
 
 
def verify_access_token(token: str):
    ### """Decodes JWT and returns payload if valid"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
 
 
def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Dbuser:
    ### """Extracts user from JWT token and fetches from database"""
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token"
        )
 
    user_id = payload.get("sub")  # Extract user ID from token
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
 
    # Fetch the user from the database
    user = db.query(Dbuser).filter(Dbuser.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if payload.get("token_version") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked due to credential change",
        )
 
    return user  # Return full user object