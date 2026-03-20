from sqlalchemy.orm import Session
from db.models import Dbhotel, IsActive, Dbuser
from schemas import HotelBase, HotelUpdate
from sqlalchemy import or_
from typing import Optional
from fastapi import BackgroundTasks
from email_utils import send_email


def create_hotel(db: Session, request: HotelBase, owner_id: int):
    # Check if a hotel with the same name and location already exists
    existing_hotel = (
        db.query(Dbhotel)
        .filter(Dbhotel.name == request.name, Dbhotel.location == request.location)
        .first()
    )

    if existing_hotel:
        return None  # Return None if the hotel already exists

    # If no duplicate found, create a new hotel
    new_hotel = Dbhotel(
        name=request.name,
        location=request.location,
        description=request.description,
        img_link=request.img_link,
        phone_number=request.phone_number,
        email=request.email,
        owner_id=owner_id,
    )
    db.add(new_hotel)
    db.commit()
    db.refresh(new_hotel)
    return new_hotel


# delete hotel
def delete_hotel(db: Session, id: int):
    hotel = db.query(Dbhotel).filter(Dbhotel.id == id).first()

    if hotel:
        hotel.is_active = IsActive.deleted  # Mark hotel as deleted
        db.commit()
        return f"Hotel with ID {id} deleted successfully."  # Return success message
    else:
        return None  # Return None if hotel not found


def combined_search_filter(
    db: Session,
    search_term: Optional[str] = None,
    location: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
    is_approved: Optional[bool] = None,
    owner_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
):
    query = db.query(Dbhotel).filter(Dbhotel.is_active != "deleted")


    if search_term:
        query = query.filter(Dbhotel.name.ilike(f"%{search_term}%"))

    if location:
        query = query.filter(Dbhotel.location.ilike(f"%{location}%"))

    if min_rating is not None:
        query = query.filter(Dbhotel.avg_review_score >= min_rating)

    if max_rating is not None:
        query = query.filter(Dbhotel.avg_review_score <= max_rating)
    
    if is_approved is not None:
        query = query.filter(Dbhotel.is_approved == is_approved)

    if owner_id is not None:
        query = query.filter(Dbhotel.owner_id == owner_id)
    

    return query.offset(skip).limit(limit).all()



def get_all_hotels(db: Session):
    return db.query(Dbhotel).all()


def get_hotel(db: Session, id: int):
    return db.query(Dbhotel).filter(Dbhotel.id == id).first()


def update_hotel(db: Session, id: int, request: HotelUpdate, background_tasks: BackgroundTasks, current_user: Dbuser):
    hotel = db.query(Dbhotel).filter(Dbhotel.id == id).first()

    if not hotel:
        return None
    
    #Take the status before changing
    previous_is_approved = hotel.is_approved

    update_data = request.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(hotel, key, value)

    db.commit()
    db.refresh(hotel)


# Check for changing approval status
    if current_user.is_superuser and "is_approved" in update_data and previous_is_approved != hotel.is_approved:
        owner = db.query(Dbuser).filter(Dbuser.id == hotel.owner_id).first()

        if hotel.is_approved:
            # Approval email
            subject = "Your Hotel Has Been Approved"
            body = f"Congratulations {owner.username},\n\nYour hotel '{hotel.name}' has been approved.\n\nBest regards,\nHotel Management Team."
        else:
            # Rejection email
            subject = "Your Hotel Has Been Rejected"
            body = f"Dear {owner.username},\n\nYour hotel '{hotel.name}' has been rejected. Please contact support for further information.\n\nBest regards,\nHotel Management Team."

        to_email = owner.email
        background_tasks.add_task(send_email, to_email, subject, body)

    return hotel
