from threading import Thread
from fastapi import FastAPI
from auth import authentication
from cloudinary_config import configure_cloudinary
from routers import files, hotel, user, booking, review, room, payment
from db import models
from db.database import engine
from task.background_tasks import update_room_status_periodically


app = FastAPI()
app.include_router(authentication.router)
app.include_router(user.router)
app.include_router(hotel.router)
app.include_router(room.router)
app.include_router(booking.router)
app.include_router(review.router)
app.include_router(payment.router)
app.include_router(files.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Hotel Booking API!!!!"}


@app.on_event("startup")
def start_periodic_task():
    configure_cloudinary()
    thread = Thread(target=update_room_status_periodically)
    thread.daemon = (
        True  # Daemon threads automatically close when the main program exits
    )
    thread.start()


models.Base.metadata.create_all(engine)
