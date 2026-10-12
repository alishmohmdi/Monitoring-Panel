import asyncio

from database.db import SessionLocal
from database.models import Package

from scraper.package_parser import inspect_package


async def main():

    db = SessionLocal()

    try:

        package = (
            db.query(Package)
            .filter(Package.is_active == True)
            .order_by(Package.id.asc())
            .first()
        )

        if not package:

            print("❌ No active packages found")
            return

        print(
            f"Testing Package ID: {package.id}"
        )

        await inspect_package(
            package.id
        )

    finally:

        db.close()


if __name__ == "__main__":
    asyncio.run(main())