from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from db.database import get_db
from db import db_hotel
from db.models import Dbuser
from schemas import HotelBase, HotelDisplay, UpdateHotelResponse, HotelUpdate
from typing import Optional, List
from auth.oauth2 import get_current_user
from fastapi import Response
from db.models import IsActive


router = APIRouter(prefix="/hotel", tags=["Hotel"])


@router.post("/", response_model=HotelDisplay, status_code=201)
def submit_hotel(
    request: HotelBase,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    # Call db_hotel.create_hotel and check for duplication
    new_hotel = db_hotel.create_hotel(db, request, owner_id=user.id)

    if not new_hotel:  # If None is returned (i.e., hotel already exists)
        raise HTTPException(
            status_code=400, detail="A hotel with this name and location already exists"
        )

    return new_hotel  # Proceed to return the newly created hotel if no duplication


# read one hotel
@router.get("/{id}", response_model=HotelDisplay)
def get_hotel(id: int, db: Session = Depends(get_db)):
    hotel = db_hotel.get_hotel(db, id)

    # Only exclude hotels marked as deleted
    if not hotel or hotel.is_active == IsActive.deleted:
        raise HTTPException(status_code=404, detail="Hotel not found")

    return hotel

# Combine search and filter logic into one endpoint
@router.get("/", response_model=List[HotelDisplay])
def get_hotels(
    search_term: Optional[str] = None,
    location: Optional[str] = Query(None, min_length=1),
    min_rating: Optional[float] = Query(None, ge=1.0, le=5.0),
    max_rating: Optional[float] = Query(None, ge=1.0, le=5.0),
    owner_id: Optional[int] = None,
    is_approved: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    if owner_id is not None:
        user = db.query(Dbuser).filter(Dbuser.id == owner_id).first()
        if not user:
            return Response(status_code=204)

    return db_hotel.combined_search_filter(
        db=db,
        search_term=search_term,
        location=location.strip() if location else None,
        min_rating=min_rating,
        max_rating=max_rating,
        is_approved=is_approved,
        owner_id=owner_id,
        skip=0,
        limit=100,
    )


# update hotels
@router.patch(
    "/{id}",
    response_model=UpdateHotelResponse,
    summary="Update hotel",
    description="Only owner or super admin can update",
)
def update_hotel(
    id: int,
    request: HotelUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    hotel = db_hotel.get_hotel(db, id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if hotel.owner_id != user.id and not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this hotel"
        )

    if not user.is_superuser and request.is_approved is not None:
        raise HTTPException(
            status_code=403, detail="Only an admin can update is_approved"
        )

    updated_hotel = db_hotel.update_hotel(db, id, request, background_tasks, user)

    if not updated_hotel:
        raise HTTPException(status_code=500, detail="Failed to update hotel")

    return UpdateHotelResponse(
        message="Hotel updated successfully", hotel=updated_hotel
    )


### DELETE HOTEL (Only Owner or Super Admin)
@router.delete(
    "/{id}",
    status_code=204,
    summary="Remove hotel",
    description="Only owner or super admin can delete",
)
def delete_hotel(
    id: int,
    db: Session = Depends(get_db),
    user: Dbuser = Depends(get_current_user),
):
    hotel = db_hotel.get_hotel(db, id)

    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if hotel.owner_id != user.id and not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this hotel"
        )

    # Call delete_hotel from db_hotel and get the result
    db_hotel.delete_hotel(db, id)

    return Response(status_code=204)  # No content returned