"""Idempotent, development-only sample data.

The credentials are deliberately obvious demo credentials and must never be used in production.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Category, Location, Report, Role, User
from app.security import hash_password


DEMO_ACCOUNTS = (
    ("alex.student@findit.local", "Alex Student", Role.STUDENT.value, "DemoStudent1!"),
    ("jordan.student@findit.local", "Jordan Student", Role.STUDENT.value, "DemoStudent2!"),
    ("sam.staff@findit.local", "Sam Campus Staff", Role.STAFF.value, "DemoStaff2026!"),
    ("admin@findit.local", "Demo Administrator", Role.ADMIN.value, "DemoAdmin2026!"),
)

CATEGORIES = (
    ("Electronics", "Phones, laptops, chargers, and personal electronics"),
    ("Keys", "Keys, keychains, and access fobs"),
    ("Bags", "Backpacks, handbags, and cases"),
    ("Identification", "Student cards and identity documents"),
    ("Clothing", "Clothing and wearable accessories"),
    ("Books & Notes", "Books, notebooks, and study materials"),
    ("Other", "Items that do not fit another category"),
)

LOCATIONS = (
    ("Main Library", "Library", "Main library entrance and study floors"),
    ("Student Center", "Student Center", "Food court and student activity areas"),
    ("Engineering Block", "Engineering", "Engineering classrooms and laboratories"),
    ("Campus Security Desk", "Administration", "Central staffed recovery point"),
)


def main() -> None:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        raise SystemExit("Refusing to load demo data outside development/test")
    with SessionLocal() as db:
        users: dict[str, User] = {}
        for email, name, role, password in DEMO_ACCOUNTS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    full_name=name,
                    role=role,
                    email_verified=True,
                    password_hash=hash_password(password),
                )
                db.add(user)
                db.flush()
            users[email] = user

        categories: dict[str, Category] = {}
        for name, description in CATEGORIES:
            category = db.scalar(select(Category).where(Category.name == name))
            if category is None:
                category = Category(
                    name=name,
                    slug=name.lower().replace(" & ", "-").replace(" ", "-"),
                    description=description,
                )
                db.add(category)
                db.flush()
            categories[name] = category

        locations: dict[str, Location] = {}
        for name, building, description in LOCATIONS:
            location = db.scalar(select(Location).where(Location.name == name))
            if location is None:
                location = Location(
                    name=name,
                    slug=name.lower().replace(" ", "-"),
                    building=building,
                    description=description,
                )
                db.add(location)
                db.flush()
            locations[name] = location

        alex = users["alex.student@findit.local"]
        jordan = users["jordan.student@findit.local"]
        lost_exists = db.scalar(
            select(Report.id).where(
                Report.reporter_id == alex.id, Report.item_name == "Blue wireless headphones"
            )
        )
        if not lost_exists:
            db.add(
                Report(
                    reporter_id=alex.id,
                    report_type="lost",
                    item_name="Blue wireless headphones",
                    category_id=categories["Electronics"].id,
                    location_id=locations["Main Library"].id,
                    approximate_location="Second floor quiet study area",
                    occurred_at=datetime.now(UTC) - timedelta(days=2),
                    description="Navy blue over-ear wireless headphones in a black zip case.",
                    public_details="Small silver scratch on the left ear cup.",
                    private_details="The device name and serial number can be provided to staff.",
                )
            )
        found_exists = db.scalar(
            select(Report.id).where(
                Report.reporter_id == jordan.id, Report.item_name == "Wireless headphones in case"
            )
        )
        if not found_exists:
            db.add(
                Report(
                    reporter_id=jordan.id,
                    report_type="found",
                    item_name="Wireless headphones in case",
                    category_id=categories["Electronics"].id,
                    location_id=locations["Main Library"].id,
                    approximate_location="Library second floor study desks",
                    occurred_at=datetime.now(UTC) - timedelta(days=1, hours=20),
                    description="Blue over-ear wireless headphones found inside a black case.",
                    public_details="Turned off when found; no owner information displayed.",
                    private_details="Staff can inspect an identifying mark not shown publicly.",
                )
            )
        db.commit()

    print("Development demo data is ready.")
    print("Demo-only accounts:")
    for email, _name, role, password in DEMO_ACCOUNTS:
        print(f"  {role:7} {email:32} {password}")


if __name__ == "__main__":
    main()

