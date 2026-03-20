from fastapi import APIRouter, Depends, HTTPException, Query, Response, status as STATUS
from sqlalchemy.orm import Session
from typing import List, Optional
from auth.oauth2 import get_current_user
from db.database import get_db
from db import db_booking
from db.models import Dbbooking, Dbhotel, Dbroom, Dbuser
from schemas import BookingCreate, BookingShow, BookingStatus, BookingUpdate, IsActive


router = APIRouter(prefix="/booking", tags=["Booking"])


@router.post(
    "/",
    response_model=BookingShow,
    status_code=STATUS.HTTP_201_CREATED,
    summary="Create a new booking",
)
def create_a_booking(
    request: BookingCreate,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    # Validate if the user is a superuser
    # Check if check_in_date is before check_out_date
    if request.check_in_date >= request.check_out_date:
        raise HTTPException(
            status_code=400, detail="check_in_date must be before check_out_date."
        )

    # Validate if the hotel exists
    hotel = db.query(Dbhotel).filter(Dbhotel.id == request.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    # Validate if the room exists within the specified hotel
    room = (
        db.query(Dbroom)
        .filter(Dbroom.id == request.room_id, Dbroom.hotel_id == request.hotel_id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found in this hotel.")

    # Check if the room is available for the requested dates
    if not db_booking.check_room_availability(
        db, request.room_id, request.check_in_date, request.check_out_date
    ):
        raise HTTPException(
            status_code=400, detail="The room is not available for the selected dates."
        )
    if not user.is_superuser and not request.user_id == user.id:
        raise HTTPException(
            status_code=403, detail="You are not authorized to book this room."
        )
    # Create the booking
    new_booking = db_booking.create_booking(db, request, user_id=request.user_id)

    if not new_booking:
        raise HTTPException(status_code=400, detail="Failed to create booking.")

    return new_booking


@router.get("/{booking_id}", response_model=BookingShow, summary="Get booking by ID")
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),  # Get the current logged-in user
):
    booking = db_booking.get_booking_by_id(
        db,
        booking_id,
    )

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check authorization:
    # 1. User is admin - always allowed
    # 2. User owns the booking
    # 3. User owns the hotel where booking was made
    if not (
        user.is_superuser
        or booking.user_id == user.id
        or db_booking.is_hotel_owner(db, booking.hotel_id, user.id)
    ):
            raise HTTPException(
                status_code=403, detail="Not authorized to view this booking"
            )

    return booking


@router.delete(
    "/{booking_id}",
    summary="Delete Booking",
    status_code=STATUS.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Booking deleted successfully"},
        403: {"description": "Not authorized to delete this booking"},
        404: {"description": "Booking not found"},
    },
)
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    # First check if booking exists
    booking = db_booking.soft_delete_booking(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=STATUS.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found",
        )

    # Check authorization
    if not user.is_superuser and booking.user_id != user.id:
        raise HTTPException(
            status_code=STATUS.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this booking",
        )

    # Perform soft delete
    db_booking.soft_delete_booking(db, booking_id)

    # No content response is standard for DELETE operations
    return Response(status_code=STATUS.HTTP_204_NO_CONTENT)


@router.put("/{booking_id}", response_model=BookingShow, summary="Update Booking")
def update_booking(
    booking_id: int,
    request: BookingUpdate,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    # Fetch the booking using the function from db_booking
    booking = db.query(Dbbooking).filter(Dbbooking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Authorization: Only allow the user to update their own booking or if they are an admin
    if not user.is_superuser and booking.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this booking"
        )

    if "user_id" in request.dict(exclude_unset=True) and not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to update the 'user_id' field"
        )

    # Authorization for 'is_active': Only admins can update the 'is_active' field
    if "is_active" in request.dict(exclude_unset=True) and not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to update the 'is_active' field"
        )

    # Now that we've validated the authorization, call the function to update the booking
    updated_booking = db_booking.update_booking_in_db(db, booking_id, request)

    if not updated_booking:
        raise HTTPException(
            status_codep=404, detail="Booking not found or could not be updated"
        )

    return updated_booking


@router.get(
    "/",
    response_model=List[BookingShow],
    summary="Get filtered bookings",
    description="Retrieve bookings with optional filters. Regular users can only view their own bookings.",
    responses={
        STATUS.HTTP_200_OK: {"description": "List of matching bookings"},
        STATUS.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to access these bookings"
        },
        STATUS.HTTP_404_NOT_FOUND: {
            "description": "No bookings found matching criteria"
        },
    },
)
def get_all_bookings_by_filter(
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
    user_id: Optional[int] = Query(
        None,
        gt=0,
        description="Filter by user ID (must be positive integer). Non-admins can only filter by their own ID.",
    ),
    hotel_id: Optional[int] = Query(
        None,
        gt=0,
        description="Filter by hotel ID (must be positive integer). Non-admins can only filter by hotels they own.",
    ),
    room_id: Optional[int] = Query(
        None,
        gt=0,
        description="Filter by room ID (must be positive integer). Non-admins can only filter by rooms in hotels they own.",
    ),
    booking_id: Optional[int] = Query(
        None,
        gt=0,
        description="Filter by specific booking ID (must be positive integer)",
    ),
    is_active: Optional[IsActive] = Query(
        None,
        description="Filter by active status. Non-admins cannot view deleted bookings.",
    ),
    status: Optional[BookingStatus] = Query(
        None,
        description="Filter by booking status (e.g., 'confirmed', 'pending', 'cancelled')",
    ),
):
    # Validate user permissions
    if not user.is_superuser:
        if is_active == IsActive.deleted:
            raise HTTPException(
                status_code=STATUS.HTTP_403_FORBIDDEN,
                detail="Not authorized to view deleted bookings",
            )

        if user_id and user_id != user.id:
            raise HTTPException(
                status_code=STATUS.HTTP_403_FORBIDDEN,
                detail="Not authorized to view other users' bookings",
            )

        if hotel_id:
            hotel = (
                db.query(Dbhotel)
                .filter(Dbhotel.id == hotel_id, Dbhotel.owner_id == user.id)
                .first()
            )
            if not hotel:
                raise HTTPException(
                    status_code=STATUS.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view bookings for this hotel",
                )

        if room_id:
            room = (
                db.query(Dbroom)
                .join(Dbhotel)
                .filter(Dbroom.id == room_id, Dbhotel.owner_id == user.id)
                .first()
            )
            if not room:
                raise HTTPException(
                    status_code=STATUS.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view bookings for this room",
                )

    # Apply filters
    bookings = db_booking.get_all_bookings(
        db=db,
        user_id=user_id if user.is_superuser else (user_id or user.id),
        hotel_id=hotel_id,
        room_id=room_id,
        booking_id=booking_id,
        is_active=is_active.value if is_active else None,
        status=status.value if status else None,
    )

    if not bookings:
        raise HTTPException(
            status_code=STATUS.HTTP_404_NOT_FOUND,
            detail="No bookings found matching the criteria",
        )

    return bookings
