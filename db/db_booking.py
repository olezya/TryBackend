from operator import and_, or_
from typing import Optional
from sqlalchemy.orm import Session
from db.models import Dbbooking, Dbhotel, Dbroom, IsActive, IsRoomStatus
from schemas import BookingCreate, BookingUpdate
from datetime import date


def calculate_total_cost(
    db: Session, room_id: int, check_in_date: date, check_out_date: date
):
    # Fetch the room's price per night
    room = db.query(Dbroom).filter(Dbroom.id == room_id).first()

    if not room:
        return None  # Room not found

    # Calculate the total cost for the booking
    total_nights = (check_out_date - check_in_date).days
    if total_nights <= 0:
        return None  # Invalid booking dates

    return room.price_per_night * total_nights  # Return the total cost


def check_room_availability(
    db: Session, room_id: int, check_in_date: date, check_out_date: date
) -> bool:
    # Validate dates
    if check_out_date <= check_in_date:
        return False  # Invalid date range

    # Check if room exists and is active
    room = (
        db.query(Dbroom)
        .filter(
            Dbroom.id == room_id,
            Dbroom.is_active == IsActive.active,
        )
        .first()
    )

    if not room:
        return False

    # Check for overlapping bookings
    overlapping_booking = (
        db.query(Dbbooking)
        .filter(
            Dbbooking.room_id == room_id,
            Dbbooking.is_active == IsActive.active,
            # Alternative overlapping condition that might be clearer
            or_(
                and_(
                    Dbbooking.check_in_date < check_out_date,
                    Dbbooking.check_out_date > check_in_date,
                ),
                # This covers cases where a booking completely contains the requested period
                and_(
                    Dbbooking.check_in_date >= check_in_date,
                    Dbbooking.check_out_date <= check_out_date,
                ),
            ),
        )
        .first()
    )

    return not overlapping_booking


def create_booking(db: Session, request: BookingCreate, user_id: int):
    # Create the booking (without checking availability here)
    new_booking = Dbbooking(
        user_id=user_id,
        hotel_id=request.hotel_id,
        room_id=request.room_id,
        check_in_date=request.check_in_date,
        check_out_date=request.check_out_date,
    )

    # Calculate the total cost
    total_cost = calculate_total_cost(
        db, request.room_id, request.check_in_date, request.check_out_date
    )
    if total_cost is None:
        return None  # If there's an issue with the cost calculation

    new_booking.total_cost = total_cost

    # Update the room status to reserved
    room = db.query(Dbroom).filter(Dbroom.id == request.room_id).first()
    if room:
        room.status = IsRoomStatus.reserved
        db.commit()

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return new_booking


def is_hotel_owner(db: Session, hotel_id: int, user_id: int) -> bool:
    """Check if user owns the specified hotel"""
    return db.query(
        db.query(Dbhotel)
        .filter(
            Dbhotel.id == hotel_id,
            Dbhotel.owner_id == user_id,
            Dbhotel.is_active == IsActive.active,
        )
        .exists()
    ).scalar()


def get_booking_by_id(db: Session, booking_id: int):
    query = (
        db.query(Dbbooking)
        .filter(Dbbooking.id == booking_id)
        .filter(Dbbooking.is_active != IsActive.deleted)
    )

    return query.first()


def soft_delete_booking(db: Session, booking_id: int):
    booking = db.query(Dbbooking).filter(Dbbooking.id == booking_id).first()

    if not booking or booking.is_active == IsActive.deleted:
        return None  # Return None if no booking is found

    booking.is_active = (
        IsActive.deleted
    )  # Mark the booking as inactive instead of deleting

    # Update the room status to available
    room = db.query(Dbroom).filter(Dbroom.id == booking.room_id).first()
    if room:
        room.status = IsRoomStatus.available
        db.commit()

    db.commit()
    db.refresh(booking)
    return booking  # Return the updated booking


def get_all_bookings(
    db: Session,
    user_id: Optional[int] = None,
    hotel_id: Optional[int] = None,
    room_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    is_active: Optional[str] = None,
    status: Optional[str] = None,
):
    query = db.query(Dbbooking).filter(Dbbooking.is_active != IsActive.deleted)

    if user_id is not None:
        query = query.filter(Dbbooking.user_id == user_id)
    if hotel_id is not None:
        query = query.filter(Dbbooking.hotel_id == hotel_id)
    if room_id is not None:
        query = query.filter(Dbbooking.room_id == room_id)
    if booking_id is not None:
        query = query.filter(Dbbooking.id == booking_id)
    if is_active is not None:
        query = query.filter(Dbbooking.is_active == is_active)
    if status is not None:
        query = query.filter(Dbbooking.status == status)

    return query.all()


def update_booking_in_db(
    db: Session, booking_id: int, request: BookingUpdate
) -> Dbbooking:
    # Query the booking by ID
    booking = (
        db.query(Dbbooking)
        .filter(Dbbooking.id == booking_id)
        .filter(Dbbooking.is_active != IsActive.deleted)
    )

    # Check if the booking exists
    if not booking.first():
        return None  # Return None if the booking is not found

    # Prepare data for updating the booking
    request_data = request.dict(exclude_unset=True)

    # Update the booking fields (only the fields that are included in the request)
    booking.update(request_data)

    # Commit the changes to the database
    db.commit()

    # Return the updated booking (optional - if you want to fetch it back from DB)
    updated_booking = booking.first()
    return updated_booking
