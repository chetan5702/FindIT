import io
import uuid

import qrcode
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import require_admin
from app.errors import APIError
from app.models import Category, Location, User
from app.schemas import CategoryOut, LocationOut


router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return list(
        db.scalars(
            select(Category).where(Category.is_active.is_(True)).order_by(Category.name.asc())
        )
    )


@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db)) -> list[Location]:
    return list(
        db.scalars(select(Location).where(Location.is_active.is_(True)).order_by(Location.name.asc()))
    )


@router.get("/locations/{location_id}", response_model=LocationOut)
def get_location(location_id: uuid.UUID, db: Session = Depends(get_db)) -> Location:
    location = db.get(Location, location_id)
    if location is None or not location.is_active:
        raise APIError(404, "location_not_found", "Location not found")
    return location


@router.get("/locations/{location_id}/qr", responses={200: {"content": {"image/png": {}}}})
def location_qr(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> Response:
    location = db.get(Location, location_id)
    if location is None:
        raise APIError(404, "location_not_found", "Location not found")
    url = (
        f"{settings.public_base_url.rstrip('/')}/app/report/found"
        f"?location={location.id}&source=qr&token={location.qr_token}"
    )
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300", "X-QR-Purpose": "reporting-convenience"},
    )

