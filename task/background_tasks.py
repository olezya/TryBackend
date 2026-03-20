import time
from datetime import date
from sqlalchemy.orm import Session
from db.models import Dbbooking, Dbroom, IsRoomStatus
from db.database import (
    SessionLocal,
)  # Ensure SessionLocal is imported from your database config


def update_room_status_periodically():
    while True:
        db: Session = SessionLocal()

        try:
            # Log the start of the task
            print("Checking for expired bookings...")

            # Find all expired bookings
            expired_bookings = (
                db.query(Dbbooking)
                .filter(Dbbooking.check_out_date < date.today())
                .all()
            )

            if expired_bookings:
                print(f"Found {len(expired_bookings)} expired bookings.")

            for booking in expired_bookings:
                # Find the corresponding room and mark it as available
                room = db.query(Dbroom).filter(Dbroom.id == booking.room_id).first()
                if room:
                    room.status = IsRoomStatus.available  # Set room status to available
                    db.commit()
                    print(f"Room {room.id} status updated to available.")
            else:
                print("No expired bookings found.")
        finally:
            db.close()  # Always close the session after use

        time.sleep(
            60 * 60 * 24
        )  # Wait for 24 hours before running again (can adjust the interval)
