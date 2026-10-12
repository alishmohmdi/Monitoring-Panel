import json
import re
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

from database.db import SessionLocal
from database.models import Package, Route


BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG_DIR = BASE_DIR / "logs" / "package_debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ENGLISH_DIGITS = "0123456789"

DIGIT_TRANSLATION = str.maketrans(
    PERSIAN_DIGITS,
    ENGLISH_DIGITS
)


def normalize_digits(text: str) -> str:
    if not text:
        return ""

    return text.translate(DIGIT_TRANSLATION)


def extract_dates(text: str) -> list[str]:

    text = normalize_digits(text)

    patterns = [
        r"14\d{2}/\d{1,2}/\d{1,2}",
        r"14\d{2}-\d{1,2}-\d{1,2}",
        r"\d{1,2}\s+(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)\s+14\d{2}",
        r"\d{1,2}\s+(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)",
    ]

    results = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        for match in matches:

            match = match.strip()

            if match not in results:
                results.append(match)

    return results


def extract_duration(text: str) -> str | None:

    text = normalize_digits(text)

    patterns = [
        r"\d+\s*شب\s*(?:و|،)?\s*\d+\s*روز",
        r"\d+\s*شب",
        r"\d+\s*روز",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(0)

    return None


async def inspect_package(package_id: int):

    db = SessionLocal()

    try:

        package = (
            db.query(Package)
            .filter(Package.id == package_id)
            .first()
        )

        if not package:
            print(f"❌ Package {package_id} not found")
            return

        route = (
            db.query(Route)
            .filter(Route.id == package.route_id)
            .first()
        )

        print("=" * 70)
        print("PACKAGE PARSER")
        print("=" * 70)

        print(f"Package ID: {package.id}")
        print(f"Route: {route.name if route else package.route_id}")
        print(f"URL: {package.url}")

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 1400
                }
            )

            print()
            print("🌐 Opening package...")

            try:

                response = await page.goto(
                    package.url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

            except Exception as exc:

                print("❌ Page load failed")
                print(exc)

                await browser.close()
                return

            await page.wait_for_timeout(5000)

            status = response.status if response else None

            print(f"HTTP status: {status}")
            print(f"Final URL: {page.url}")

            title = await page.title()

            print(f"Title: {title}")

            body_text = await page.locator(
                "body"
            ).inner_text()

            dates = extract_dates(body_text)
            duration = extract_duration(body_text)

            print()
            print("=" * 70)
            print("DETECTED DATA")
            print("=" * 70)

            print(f"Dates: {dates}")
            print(f"Duration: {duration}")

            table_rows = await page.locator(
                "tr"
            ).all_inner_texts()


            candidate_blocks = await page.locator(
                """
                [class*="hotel"],
                [class*="Hotel"],
                [class*="package"],
                [class*="Package"],
                [class*="tour"]
                """
            ).all_inner_texts()

            cleaned_rows = []

            for row in table_rows:

                row = " ".join(
                    row.split()
                ).strip()

                if len(row) >= 3:
                    cleaned_rows.append(row)

            cleaned_blocks = []

            for block in candidate_blocks:

                block = " ".join(
                    block.split()
                ).strip()

                if (
                    len(block) >= 5
                    and block not in cleaned_blocks
                ):
                    cleaned_blocks.append(block)

            data = {
                "package_id": package.id,
                "route_id": package.route_id,
                "url": package.url,
                "http_status": status,
                "title": title,
                "dates": dates,
                "duration": duration,
                "table_rows": cleaned_rows,
                "candidate_blocks": cleaned_blocks,
                "scanned_at": datetime.utcnow().isoformat(),
            }

            debug_file = (
                DEBUG_DIR
                / f"package_{package.id}.json"
            )

            with debug_file.open(
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2
                )

            text_file = (
                DEBUG_DIR
                / f"package_{package.id}.txt"
            )

            text_file.write_text(
                body_text,
                encoding="utf-8"
            )

            screenshot_file = (
                DEBUG_DIR
                / f"package_{package.id}.png"
            )

            await page.screenshot(
                path=str(screenshot_file),
                full_page=True
            )

            package.title = title

            if dates:
                package.departure_date = dates[0]

            if len(dates) >= 2:
                package.return_date = dates[1]

            package.duration = duration
            package.last_seen_at = datetime.utcnow()

            if status == 404:
                package.is_active = False
            else:
                package.is_active = True

            db.commit()

            print()
            print("=" * 70)
            print("TABLE ROWS")
            print("=" * 70)

            for index, row in enumerate(
                cleaned_rows[:30],
                start=1
            ):
                print(f"{index}. {row}")

            print()
            print("=" * 70)
            print("DEBUG FILES")
            print("=" * 70)

            print(debug_file)
            print(text_file)
            print(screenshot_file)
            
            result = data

            await browser.close()
            return result


    finally:

        db.close()