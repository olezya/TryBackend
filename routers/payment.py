from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from db.database import get_db
from schemas import PaymentCreate, PaymentShow, PaymentStatus
from db import db_payment
from auth.oauth2 import get_current_user
from db.models import Dbuser, Dbbooking, Dbpayment
from decimal import Decimal
from typing import List, Optional
from datetime import date
from db.db_payment import search_payments


router = APIRouter(prefix="/payment", tags=["payment"])


@router.post("/", response_model=PaymentShow, status_code=status.HTTP_201_CREATED)
def make_payment_for_user(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    booking = db.query(Dbbooking).filter(Dbbooking.id == payment.booking_id).first()
    if current_user.id != payment.user_id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to make a payment for another user.",
        )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="This booking doesn't belong to you."
        )

    existing_payment = db_payment.get_payment_by_booking(db, payment.booking_id)
    if existing_payment:
        raise HTTPException(
            status_code=400, detail="Payment already exists for this booking."
        )

    # Check amount
    expected_amount: Decimal = booking.total_cost

    if payment.amount < expected_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient amount. You must pay exactly {expected_amount}.",
        )
    elif payment.amount > expected_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Overpayment detected. You must pay exactly {expected_amount}.",
        )

    # when the card is valid and the amount is exact the payment is completed
    payment_status = "completed"

    # Save payment
    saved_payment = db_payment.create_payment(
        db,
        payment,
        user_id=current_user.id,
        status=payment_status,
        amount=payment.amount,
    )

    # Update booking status if payment completed
    if payment_status == PaymentStatus.completed:
        booking.status = "confirmed"
        db.commit()

    return saved_payment


# -------------------------------------------------------------------------------------------
# Get the payment with payment_id
@router.get(
    "/{payment_id}",
    response_model=PaymentShow,
    summary="Get the payment with Payment_id",
)
def get_payment_with_payment_id(
    payment_id: int = Path(
        ..., gt=0, description="Payment ID must be a positive integer"
    ),
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    payment = db_payment.get_payment_by_payment_id(db, payment_id)

    # Check if the payment exists
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")

    # Check if the payment belongs to the current user or user is super admin
    if payment.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this payment"
        )

    return payment


# -------------------------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[PaymentShow],
    summary="Search all payments (owner and superadmin)",
)
def search_payments_superadmin_only(
    status: Optional[PaymentStatus] = Query(None, description="Filter by status"),
    user_id: Optional[int] = Query(None, gt=0, description="Filter User ID"),
    booking_id: Optional[int] = Query(None, gt=0, description="Filter Booking ID"),
    start_date: Optional[date] = Query(None, description="Start of payment date"),
    end_date: Optional[date] = Query(None, description="End of payment date"),
    min_amount: Optional[Decimal] = Query(None, gt=0, description="Minimum amount"),
    max_amount: Optional[Decimal] = Query(None, gt=0, description="Maximum amount"),
    db: Session = Depends(get_db),
    current_user: Dbuser = Depends(get_current_user),
):
    # Authorization: Only superadmins can query for other users
    if (
        not current_user.is_superuser
        and user_id is not None
        and user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to search for other users' payments.",
        )
    if user_id is None and not current_user.is_superuser:
        user_id = current_user.id
    # Validate amount range
    if min_amount and max_amount and min_amount > max_amount:
        raise HTTPException(
            status_code=400, detail="min_amount cannot be greater than max_amount"
        )

    # Check if user exists
    if user_id:
        user_exists = db.query(Dbuser).filter(Dbuser.id == user_id).first()
        if not user_exists:
            raise HTTPException(
                status_code=404, detail=f"User with ID {user_id} not found."
            )

    # Check if booking exists
    if booking_id:
        booking_exists = db.query(Dbbooking).filter(Dbbooking.id == booking_id).first()
        if not booking_exists:
            raise HTTPException(
                status_code=404, detail=f"Booking with ID {booking_id} not found."
            )

    results = search_payments(
        db=db,
        status=status,
        user_id=user_id,
        booking_id=booking_id,
        start_date=start_date,
        end_date=end_date,
        min_amount=min_amount,
        max_amount=max_amount,
    )

    if not results:
        raise HTTPException(status_code=404, detail="No matching payments found.")

    return results
