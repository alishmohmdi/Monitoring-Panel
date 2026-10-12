import json
import re
from datetime import datetime, timedelta
from services.change_service import create_change_with_task
from database.db import SessionLocal
from database.models import (
    Snapshot,
    Change,
    Task,
    Assignment,
    Package,
)

from scraper.package_parser import inspect_package


PRICE_PATTERN = re.compile(
    r"(\d[\d,\.]{4,})"
)


def clean_number(value: str) -> float | None:

    if not value:
        return None

    value = (
        value
        .replace(",", "")
        .replace(".", "")
        .replace(" ", "")
    )

    try:
        return float(value)

    except ValueError:
        return None


def extract_price(text: str) -> float | None:

    if not text:
        return None

    matches = PRICE_PATTERN.findall(text)

    numbers = []

    for item in matches:

        number = clean_number(item)

        if number and number >= 10000:
            numbers.append(number)

    if not numbers:
        return None

    return numbers[-1]


def detect_currency(text: str) -> str:

    text_lower = text.lower()

    if "$" in text or "دلار" in text:
        return "USD"

    if "€" in text or "یورو" in text_lower:
        return "EUR"

    return "IRR"


def normalize_row(text: str) -> str:

    return " ".join(
        text.split()
    ).strip()


async def scan_package(package_id: int):

    print()
    print("=" * 70)
    print(f"SCANNING PACKAGE {package_id}")
    print("=" * 70)

    data = await inspect_package(
        package_id
    )

    if not data:

        print("❌ Parser returned no data")
        return

    db = SessionLocal()

    try:

        package = (
            db.query(Package)
            .filter(Package.id == package_id)
            .first()
        )

        if not package:

            print("❌ Package not found")
            return

        rows = data.get(
            "table_rows",
            []
        )

        current_rows = {}

        for row in rows:

            row = normalize_row(row)

            if len(row) < 5:
                continue

            price = extract_price(row)

            if price is None:
                continue

            current_rows[row] = {
                "text": row,
                "price": price,
                "currency": detect_currency(row),
            }

        print(
            f"Usable rows: {len(current_rows)}"
        )

        previous_snapshots = (
            db.query(Snapshot)
            .filter(
                Snapshot.package_id == package_id
            )
            .all()
        )

        #
        # اولین اسکن
        #

        if not previous_snapshots:

            print(
                "📸 First scan — creating baseline"
            )

            for row_data in current_rows.values():

                snapshot = Snapshot(
                    route_id=package.route_id,
                    package_id=package.id,

                    hotel_name=row_data["text"],

                    package_name=package.title,

                    price=row_data["price"],

                    currency=row_data["currency"],

                    raw_data=json.dumps(
                        row_data,
                        ensure_ascii=False
                    ),

                    scanned_at=datetime.utcnow(),
                )

                db.add(snapshot)

            db.commit()

            print(
                f"✅ Baseline created: {len(current_rows)} rows"
            )

            return

        #
        # Snapshot قبلی
        #

        previous_data = {}

        for snapshot in previous_snapshots:

            key = normalize_row(
                snapshot.hotel_name or ""
            )

            previous_data[key] = snapshot

        current_keys = set(
            current_rows.keys()
        )

        previous_keys = set(
            previous_data.keys()
        )

        #
        # هتل / ردیف جدید
        #

        added = (
            current_keys
            - previous_keys
        )

        #
        # حذف شده
        #

        removed = (
            previous_keys
            - current_keys
        )

        #
        # مشترک
        #

        common = (
            current_keys
            & previous_keys
        )

        changes_created = 0

        #
        # Added
        #

        for key in added:

            row = current_rows[key]

            change = Change(
                route_id=package.route_id,
                package_id=package.id,

                hotel_name=row["text"],

                package_name=package.title,

                change_type="hotel_added",

                old_value=None,
                new_value=row["text"],

                old_price=None,
                new_price=row["price"],

                detected_at=datetime.utcnow(),
            )

            db.add(change)

            db.flush()

            create_task_for_change(
                db=db,
                change=change,
                route_id=package.route_id,
            )

            changes_created += 1

        #
        # Removed
        #

        for key in removed:

            old = previous_data[key]

            change = Change(
                route_id=package.route_id,
                package_id=package.id,

                hotel_name=old.hotel_name,

                package_name=package.title,

                change_type="hotel_removed",

                old_value=old.hotel_name,
                new_value=None,

                old_price=old.price,
                new_price=None,

                detected_at=datetime.utcnow(),
            )

            db.add(change)

            db.flush()

            create_task_for_change(
                db=db,
                change=change,
                route_id=package.route_id,
            )

            changes_created += 1

        #
        # Price change
        #

        for key in common:

            old = previous_data[key]
            new = current_rows[key]

            if (
                old.price is not None
                and new["price"] is not None
                and float(old.price)
                != float(new["price"])
            ):

                change = Change(
                    route_id=package.route_id,
                    package_id=package.id,

                    hotel_name=new["text"],

                    package_name=package.title,

                    change_type="price_change",

                    old_value=old.hotel_name,
                    new_value=new["text"],

                    old_price=old.price,
                    new_price=new["price"],

                    detected_at=datetime.utcnow(),
                )

                db.add(change)

                db.flush()

                create_task_for_change(
                    db=db,
                    change=change,
                    route_id=package.route_id,
                )

                changes_created += 1

        #
        # Snapshot قبلی پاک می‌شود
        #

        (
            db.query(Snapshot)
            .filter(
                Snapshot.package_id == package_id
            )
            .delete(
                synchronize_session=False
            )
        )

        #
        # Snapshot جدید
        #

        for row_data in current_rows.values():

            snapshot = Snapshot(
                route_id=package.route_id,
                package_id=package.id,

                hotel_name=row_data["text"],

                package_name=package.title,

                price=row_data["price"],

                currency=row_data["currency"],

                raw_data=json.dumps(
                    row_data,
                    ensure_ascii=False
                ),

                scanned_at=datetime.utcnow(),
            )

            db.add(snapshot)

        db.commit()

        print()
        print("=" * 70)
        print("SCAN RESULT")
        print("=" * 70)

        print(
            f"Added: {len(added)}"
        )

        print(
            f"Removed: {len(removed)}"
        )

        print(
            f"Changes created: {changes_created}"
        )

    finally:

        db.close()


def create_task_for_change(
    db,
    change,
    route_id: int,
):

    assignment = (
        db.query(Assignment)
        .filter(
            Assignment.route_id == route_id
        )
        .first()
    )

    if not assignment:

        print(
            "⚠️ No counter assignment for route"
        )

        return

    created_at = datetime.utcnow()

    task = Task(
        change_id=change.id,

        counter_id=assignment.counter_id,

        status="Pending",

        created_at=created_at,

        deadline=(
            created_at
            + timedelta(hours=2)
        ),
    )

    db.add(task)