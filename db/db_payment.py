from sqlalchemy.orm import Session
from db.models import Dbpayment
from schemas import PaymentCreate, PaymentStatus
from decimal import Decimal
from typing import Optional, List
from datetime import date

def create_payment(db: Session, payment: PaymentCreate, user_id: int, status: str, amount: Decimal):
    db_payment = Dbpayment(
        user_id=user_id,
        booking_id=payment.booking_id,
        amount=amount,
        status=status,
        payment_date=payment.payment_date,
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_payment_by_booking(db: Session, booking_id: int):
    return db.query(Dbpayment).filter(Dbpayment.booking_id == booking_id).first()

def get_payments_by_user(db: Session, user_id: int):
    return db.query(Dbpayment).filter(Dbpayment.user_id == user_id).all()
# ------------------------------------------------------------------------------------------
# get payment by payment_id
def get_payment_by_payment_id(db: Session, payment_id: int):
    return db.query(Dbpayment).filter(Dbpayment.id == payment_id).first()
#-------------------------------------------------------------------------------------------------
# get all filterd payments by superadmin
def search_payments(
    db: Session,
    status: Optional[PaymentStatus] = None,
    user_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
) -> List[Dbpayment]:
    query = db.query(Dbpayment)

    if user_id:
        query = query.filter(Dbpayment.user_id == user_id)

    if status:
        query = query.filter(Dbpayment.status == status.value)
    
    if booking_id:
        query = query.filter(Dbpayment.booking_id == booking_id)

    if start_date:
        query = query.filter(Dbpayment.payment_date >= start_date)

    if end_date:
        query = query.filter(Dbpayment.payment_date <= end_date)

    if min_amount:
        query = query.filter(Dbpayment.amount >= min_amount)

    if max_amount:
        query = query.filter(Dbpayment.amount <= max_amount)

    return query.all()