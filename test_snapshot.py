import asyncio

from database.db import SessionLocal
from database.models import Package

from scraper.snapshot_engine import scan_package


async def main():

    db = SessionLocal()

    try:

        package = (
            db.query(Package)
            .filter(
                Package.is_active == True
            )
            .order_by(
                Package.id.asc()
            )
            .first()
        )

        if not package:

            print(
                "❌ No active package found"
            )

            return

        print(
            f"Testing Package ID: {package.id}"
        )

        package_id = package.id

    finally:

        db.close()

    await scan_package(
        package_id
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )