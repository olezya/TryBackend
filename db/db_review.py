from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.models import Dbreview 
from schemas import ReviewBase, IsReviewStatus,ReviewUpdate,ReviewCreate
from sqlalchemy import func
from db.models import Dbreview, Dbhotel, Dbuser, Dbbooking
from typing import Optional, List
from datetime import date

#------------------------------------------------------------------------------------------
# # submit a review
def create_review(db: Session, request: ReviewCreate):
    db_review = Dbreview(
        user_id=request.user_id,
        hotel_id=request.hotel_id,
        booking_id=request.booking_id,
        rating=request.rating,
        comment=request.comment,
        status=IsReviewStatus.pending  
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

def update_avg_review_score(db: Session, hotel_id: int):
    total_rating, count = db.query(
        func.sum(Dbreview.rating),
        func.count(Dbreview.rating)
    ).filter(
        Dbreview.hotel_id == hotel_id,
        Dbreview.status == IsReviewStatus.confirmed
    ).first()

    if count:
        avg_rating = round(total_rating / count, 2)
    else:
        avg_rating = None  # No confirmed reviews yet

    hotel = db.query(Dbhotel).filter(Dbhotel.id == hotel_id).first()
    if hotel:
        hotel.avg_review_score = avg_rating
        db.commit()
        
#------------------------------------------------------------------------------------------
#get review by review_id
def get_review_by_review_id(db: Session, review_id: int):
    return db.query(Dbreview).filter(Dbreview.id== review_id).filter(Dbreview.status != "deleted").first()
#------------------------------------------------------------------------------------------
# get review by filtering
def get_filtered_reviews(
    db: Session,
    user_id: Optional[int] = None,
    hotel_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
    status: Optional[str] = None ,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
) -> List[Dbreview]:
    query = db.query(Dbreview).filter(Dbreview.status != "deleted")
#
    if user_id is not None:
        query = query.filter(Dbreview.user_id == user_id)

    if hotel_id is not None:
        query = query.filter(Dbreview.hotel_id == hotel_id)

    if booking_id is not None:
        query = query.filter(Dbreview.booking_id == booking_id)

    if min_rating is not None:
        query = query.filter(Dbreview.rating >= min_rating)

    if max_rating is not None:
        query = query.filter(Dbreview.rating <= max_rating)
    
    if status is not None:
        query = query.filter(Dbreview.status == status)

    if start_date is not None:
        query = query.filter(Dbreview.created_at >= start_date)

    if end_date is not None:
        query = query.filter(Dbreview.created_at <= end_date)

    if search is not None:
        query = query.filter(Dbreview.comment.ilike(f"%{search}%"))

    return query.all()

# Helper functions for existence checks
def user_exists(db: Session, user_id: int) -> bool:
    return db.query(Dbuser).filter(Dbuser.id == user_id).first() is not None

def hotel_exists(db: Session, hotel_id: int) -> bool:
    return db.query(Dbhotel).filter(Dbhotel.id == hotel_id).first() is not None

def booking_exists(db: Session, booking_id: int) -> bool:
    return db.query(Dbbooking).filter(Dbbooking.id == booking_id).first() is not None

def review_exists_for_user_and_hotel(db: Session, user_id: int, hotel_id: int) -> bool:
    return db.query(Dbreview).filter(
        Dbreview.user_id == user_id,
        Dbreview.hotel_id == hotel_id
    ).first() is not None

def review_exists_for_user_and_booking(db: Session, user_id: int, booking_id: int) -> bool:
    return db.query(Dbreview).filter(
        Dbreview.user_id == user_id,
        Dbreview.booking_id == booking_id
    ).first() is not None
def booking_belongs_to_user(db: Session, user_id: int, booking_id: int) -> bool:
    from db.models import Dbbooking
    return db.query(Dbbooking).filter(
        Dbbooking.id == booking_id,
        Dbbooking.user_id == user_id
    ).first() is not None
#------------------------------------------------------------------------------------------
#update a review
def update_review_by_id(
    db: Session,
    review_id: int,
    new_rating: Optional[float],
    new_comment: Optional[str],
    new_status: Optional[str] = None
) -> Optional[Dbreview]:
    review = db.query(Dbreview).filter(Dbreview.id == review_id).first()
    if not review:
        return None
    if new_rating is not None:
        review.rating = new_rating
    if new_comment is not None:
        review.comment = new_comment
    if new_status is not None:
        review.status = new_status

    db.commit()
    db.refresh(review)
    return review
 
#------------------------------------------------------------------------------------------
#delet a review
def soft_delete_review_by_id(db: Session, review_id: int):
    review = db.query(Dbreview).filter(Dbreview.id == review_id).first()
    if review:
        review.status = IsReviewStatus.deleted
        db.commit()
    return review


