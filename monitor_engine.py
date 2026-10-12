import asyncio
from datetime import datetime

from database.db import SessionLocal
from database.models import Route, Package

from scraper.package_discovery import discover_packages
from scraper.snapshot_engine import scan_package


async def scan_route(route_id: int):

    db = SessionLocal()

    try:

        route = (
            db.query(Route)
            .filter(
                Route.id == route_id,
                Route.is_active == True
            )
            .first()
        )

        if not route:
            print(f"❌ Active Route {route_id} not found")
            return

        print()
        print("=" * 80)
        print(f"🚀 ROUTE SCAN STARTED: {route.name}")
        print("=" * 80)

        #
        # مرحله ۱:
        # پیدا کردن تمام تاریخ‌های فعلی این Route
        #

        print()
        print("🔎 Discovering package pages...")

        await discover_packages(
            route.id
        )

        #
        # مرحله ۲:
        # گرفتن تمام Packageهای فعال Route
        #

        packages = (
            db.query(Package)
            .filter(
                Package.route_id == route.id,
                Package.is_active == True
            )
            .order_by(
                Package.id.asc()
            )
            .all()
        )

        package_ids = [
            package.id
            for package in packages
        ]

        print()
        print(
            f"📦 Active packages: {len(package_ids)}"
        )

    finally:

        db.close()

    #
    # مرحله ۳:
    # Scan تک تک Packageها
    #

    for package_id in package_ids:

        try:

            print()
            print(
                f"🔄 Scanning Package ID {package_id}"
            )

            await scan_package(
                package_id
            )

        except Exception as exc:

            print()
            print(
                f"❌ Package {package_id} failed"
            )

            print(
                f"Error: {exc}"
            )

            #
            # مهم:
            # خراب شدن یک Package نباید
            # کل مانیتور را متوقف کند
            #

            continue

        #
        # فاصله کوچک بین صفحات
        #

        await asyncio.sleep(1)

    print()
    print("=" * 80)
    print(f"✅ ROUTE FINISHED: {route.name}")
    print("=" * 80)


async def scan_all_routes():

    started_at = datetime.now()

    print()
    print("#" * 80)
    print("ARYAK TOUR MONITOR")
    print("#" * 80)

    print(
        f"Started at: {started_at}"
    )

    db = SessionLocal()

    try:

        routes = (
            db.query(Route)
            .filter(
                Route.is_active == True
            )
            .order_by(
                Route.id.asc()
            )
            .all()
        )

        route_ids = [
            route.id
            for route in routes
        ]

        print()
        print(
            f"Active routes: {len(route_ids)}"
        )

    finally:

        db.close()

    if not route_ids:

        print(
            "⚠️ No active routes found"
        )

        return

    #
    # تمام Routeها
    #

    for route_id in route_ids:

        try:

            await scan_route(
                route_id
            )

        except Exception as exc:

            print()
            print(
                f"❌ Route {route_id} failed"
            )

            print(
                f"Error: {exc}"
            )

            continue

    finished_at = datetime.now()

    duration = (
        finished_at - started_at
    )

    print()
    print("#" * 80)
    print("SCAN COMPLETED")
    print("#" * 80)

    print(
        f"Started: {started_at}"
    )

    print(
        f"Finished: {finished_at}"
    )

    print(
        f"Duration: {duration}"
    )


if __name__ == "__main__":

    asyncio.run(
        scan_all_routes()
    )