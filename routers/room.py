from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db.database import get_db
from db import db_room, db_hotel
from db.models import Dbuser, Dbhotel
from schemas import RoomBase, RoomDisplay, RoomUpdate, RoomCreate
from decimal import Decimal
from typing import Optional, List
from auth.oauth2 import get_current_user
from datetime import date
from db.models import IsActive, IsRoomStatus
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status


router = APIRouter(prefix="/room", tags=["Room"])


# Submit a new room
@router.post("/", response_model=RoomDisplay, status_code=201)
def submit_room(
    hotel_id: int,
    request: RoomBase,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    hotel = db_hotel.get_hotel(db, hotel_id)
    if not hotel or hotel.is_active == "deleted":
        raise HTTPException(status_code=404, detail="Hotel not found")
    
    if not hotel.is_approved:
        raise HTTPException(status_code=403, detail="Hotel is not approved yet")

    if hotel.owner_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        create_data = request.dict()
        create_data.update({
            'hotel_id': hotel_id,
            'is_active': create_data.get('is_active', 'active')
        })
        create_request = RoomCreate(**create_data)

        return db_room.create_room(db, create_request)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid room data: {str(e)}"
        )


# Update a room
@router.put("/{room_id}", response_model=RoomDisplay)
def update_room(
    room_id: int,
    request: RoomUpdate,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    room = db_room.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    hotel = db.query(Dbhotel).filter(Dbhotel.id == room.hotel_id).first()
    if not hotel or (hotel.owner_id != user.id and not user.is_superuser):
        raise HTTPException(status_code=403, detail="Not authorized")

    updated_room = db_room.update_room(db, room_id, request)
    if not updated_room:
        raise HTTPException(status_code=400, detail="Update failed")

    return updated_room


# Advanced room search with filters and availability
@router.get("/", response_model=List[RoomDisplay], summary="Room search")
def search_rooms(
    hotel_id: Optional[int] = None,
    search_term: Optional[str] = None,
    wifi: Optional[bool] = None,
    air_conditioner: Optional[bool] = None,
    tv: Optional[bool] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    check_in_date: Optional[date] = None,
    check_out_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    return db_room.advanced_room_search(
        db=db,
        search_term=search_term,
        wifi=wifi,
        air_conditioner=air_conditioner,
        tv=tv,
        min_price=min_price,
        max_price=max_price,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        hotel_id=hotel_id
    )



#  Get a room by an id
@router.get("/{room_id}", response_model=RoomDisplay, summary="Get a room by room ID")
def get_room_by_id(
    room_id: int,
    db: Session = Depends(get_db),
):
    room = db_room.get_room(db, room_id)
    if not room or room.is_active == IsActive.deleted:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

#......
# Soft-delete a room
@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a room")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    room = db_room.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    hotel = db_hotel.get_hotel(db, room.hotel_id)
    if not hotel or (hotel.owner_id != user.id and not user.is_superuser):
        raise HTTPException(status_code=403, detail="Not authorized to delete this room")

    room.is_active = IsActive.deleted
    room.status = IsRoomStatus.unavailable
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
