from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import School, Team, User
from app.seed_data import BASKETBALL, FOOTBALL
from app.services.accounts import create_user


def seed_schools(db) -> None:
    if db.scalar(select(func.count()).select_from(School)):
        return
    catalog: dict[str, dict] = {}
    for sport, rows in (("mens_basketball", BASKETBALL), ("mens_football", FOOTBALL)):
        for name, abbreviation, mascot, primary, secondary in rows:
            row = catalog.setdefault(
                name,
                {
                    "abbreviation": abbreviation,
                    "mascot": mascot,
                    "primary": primary,
                    "secondary": secondary,
                    "sports": set(),
                },
            )
            row["sports"].add(sport)
    for name, row in catalog.items():
        school = School(
            name=name,
            abbreviation=row["abbreviation"],
            mascot=row["mascot"],
            primary_color=row["primary"],
            secondary_color=row["secondary"],
        )
        db.add(school)
        db.flush()
        for sport in sorted(row["sports"]):
            db.add(Team(school_id=school.id, sport=sport, active=True))
    db.commit()
    print(f"Seeded {len(catalog)} schools.")


def seed_admin(db) -> None:
    settings = get_settings()
    email = settings.superadmin_email.strip()
    password = settings.superadmin_password
    if not email or not password:
        raise SystemExit("Set SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD before seeding.")
    existing = db.scalar(select(User).where(User.email == email.casefold()))
    if existing:
        existing.role = "super_admin"
        if not existing.password_hash:
            from app.security import hash_password

            existing.password_hash = hash_password(password)
        db.commit()
        print(f"Super admin ready: {existing.email}")
        return
    user = create_user(db, email, password=password)
    user.role = "super_admin"
    db.commit()
    print(f"Created super admin {user.email}")
    print("Sign in, then confirm the suggested display name before using the app.")


def main() -> None:
    db = SessionLocal()
    try:
        seed_schools(db)
        seed_admin(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
