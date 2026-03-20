from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from db.database import Base
from sqlalchemy import Column, DateTime, Enum, Integer, String, Boolean, ForeignKey



from sqlalchemy import (
    DECIMAL,
   

    Date,
    func,
)
from sqlalchemy import Enum as SqlEnum


class IsActive(PyEnum):
    inactive = "inactive"
    active = "active"
    deleted = "deleted"


class Dbuser(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)  # Long enough for bcrypt
    is_superuser = Column(Boolean, default=False)
    phone_number = Column(String(15), unique=True, nullable=False)  # +1234567890123
    token_version = Column(Integer, default=0)
    status = Column(Enum(IsActive), default=IsActive.active)

    hotels = relationship("Dbhotel", back_populates="owner")
    bookings = relationship("Dbbooking", back_populates="user")
    reviews = relationship("Dbreview", back_populates="user")
    payments = relationship(
        "Dbpayment", back_populates="user"
    )  # Added for 1:M user-payment


class Dbhotel(Base):
    __tablename__ = "hotel"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("user.id"))
    name = Column(String)
    location = Column(String)
    description = Column(String)
    is_active = Column(Enum(IsActive), default=IsActive.active)
    img_link = Column(String)
    is_approved = Column(Boolean, default=False)
    avg_review_score = Column(DECIMAL(3, 2))
    phone_number = Column(String)
    email = Column(String)

    bookings = relationship("Dbbooking", back_populates="hotel")
    rooms = relationship("Dbroom", back_populates="hotel")
    reviews = relationship("Dbreview", back_populates="hotel")
    owner = relationship("Dbuser", back_populates="hotels")


class IsRoomStatus(PyEnum):
    available = "available"
    reserved = "booked"
    unavailable = "unavailable"


class Dbroom(Base):
    __tablename__ = "room"

    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotel.id", ondelete="CASCADE"))
    room_number = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price_per_night = Column(DECIMAL(8, 2), nullable=False)
    is_active = Column(
        Enum(IsActive), nullable=False, server_default=IsActive.active.value
    )
    wifi = Column(Boolean, default=False)
    air_conditioner = Column(Boolean, default=False)
    tv = Column(Boolean, default=False)
    status = Column(Enum(IsRoomStatus), default=IsRoomStatus.available)
    bed_count = Column(Integer, nullable=False)
    hotel = relationship("Dbhotel", back_populates="rooms")


class IsBookingStatus(PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class Dbbooking(Base):
    __tablename__ = "booking"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    room_id = Column(Integer, ForeignKey("room.id"))
    hotel_id = Column(Integer, ForeignKey("hotel.id"))
    check_in_date = Column(Date)
    check_out_date = Column(Date)
    is_active = Column(Enum(IsActive), default=IsActive.active)
    status = Column(
        Enum("pending", "confirmed", "cancelled", name="booking_status"),
        default="pending",
    )
    cancel_reason = Column(String)
    total_cost = Column(DECIMAL(10, 2))

    hotel = relationship("Dbhotel", back_populates="bookings")
    user = relationship("Dbuser", back_populates="bookings")
    payment = relationship(
        "Dbpayment", back_populates="booking", uselist=False
    )  # Changed to singular
    review = relationship(
        "Dbreview", back_populates="booking", uselist=False
    )  # Changed to singular


class IsPaymentStatus(PyEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class Dbpayment(Base):
    __tablename__ = "payment"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))  # Added user_id
    booking_id = Column(
        Integer, ForeignKey("booking.id", ondelete="CASCADE"), unique=True
    )  # Enforcing 1:1
    amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(Enum(IsPaymentStatus), nullable=False)
    payment_date = Column(Date, nullable=False)

    booking = relationship("Dbbooking", back_populates="payment")  # Changed to singular
    user = relationship("Dbuser", back_populates="payments")  # Updated


# ---------------------------------------------------------------------
class IsReviewStatus(PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"
    deleted = "deleted"


class Dbreview(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))
    hotel_id = Column(Integer, ForeignKey("hotel.id", ondelete="CASCADE"))
    booking_id = Column(
        Integer, ForeignKey("booking.id", ondelete="CASCADE"), unique=True
    )  # Enforcing 1:1
    rating = Column(DECIMAL(2, 1), nullable=False)
    comment = Column(String, nullable=True)
    created_at = Column(Date, default=func.now(), nullable=False)
    status = Column(
        SqlEnum(IsReviewStatus, name="review_status"),  # ✅ using Python Enum here
        default=IsReviewStatus.pending,
        nullable=False,
    )
    user = relationship("Dbuser", back_populates="reviews")
    hotel = relationship("Dbhotel", back_populates="reviews")
    booking = relationship("Dbbooking", back_populates="review")  # Changed to singular


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    file_name = Column(String)
    file_url = Column(String)
    public_id = Column(String)  # Cloudinary public ID for deletion
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
