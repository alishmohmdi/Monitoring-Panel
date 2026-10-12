import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Route, Package
from services.change_service import create_change_with_task


BASE_URL = "https://www.alefbatour.com"


def normalize_url(url: str) -> str | None:

    if not url:
        return None

    absolute = urljoin(BASE_URL, url)

    parsed = urlparse(absolute)

    if parsed.netloc not in {
        "alefbatour.com",
        "www.alefbatour.com",
    }:
        return None

    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    return clean.rstrip("/")


def looks_like_package(url: str) -> bool:

    if not url:
        return False

    patterns = [
        r"/tour/d/",
        r"/tour/package/",
    ]

    return any(
        re.search(
            pattern,
            url,
            re.IGNORECASE
        )
        for pattern in patterns
    )


async def discover_packages(route_id: int):

    db: Session = SessionLocal()

    try:

        route = (
            db.query(Route)
            .filter(Route.id == route_id)
            .first()
        )

        if not route:

            print(
                f"❌ Route {route_id} not found"
            )

            return

        print()
        print("=" * 70)
        print("PACKAGE DISCOVERY")
        print("=" * 70)

        print(
            f"Route ID: {route.id}"
        )

        print(
            f"Route Name: {route.name}"
        )

        print(
            f"Master URL: {route.url}"
        )

        

        previous_packages = (
            db.query(Package)
            .filter(
                Package.route_id == route.id
            )
            .all()
        )

        previous_urls = {
            package.url
            for package in previous_packages
        }


        has_baseline = (
            len(previous_packages) > 0
        )

        if has_baseline:

            print()
            print(
                f"Existing baseline: {len(previous_packages)} packages"
            )

        else:

            print()
            print(
                "📸 First package discovery — baseline mode"
            )

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 1200,
                }
            )

            print()
            print(
                "🌐 Opening master route..."
            )

            try:

                response = await page.goto(
                    route.url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

            except Exception as exc:

                print()
                print(
                    "❌ Could not open master route"
                )

                print(
                    f"Error: {exc}"
                )

                await browser.close()

                return

            await page.wait_for_timeout(
                5000
            )

            if response:

                print(
                    f"HTTP status: {response.status}"
                )

            else:

                print(
                    "HTTP status: unknown"
                )

            print(
                f"Final URL: {page.url}"
            )


            links = await page.locator(
                "a"
            ).evaluate_all(
                """
                elements =>
                    elements.map(element => ({
                        href: element.href,
                        text: (element.innerText || "").trim()
                    }))
                """
            )

            print()
            print(
                f"Total links found: {len(links)}"
            )

            discovered_urls = set()

            new_packages = 0
            existing_packages = 0
            removed_packages = 0


            for item in links:

                raw_url = item.get(
                    "href"
                )

                url = normalize_url(
                    raw_url
                )

                if not url:
                    continue

                

                if not looks_like_package(
                    url
                ):
                    continue

                

                if url in discovered_urls:
                    continue

                discovered_urls.add(
                    url
                )

                title = (
                    item.get("text")
                    or route.name
                    or "Unknown Package"
                )

                title = " ".join(
                    title.split()
                ).strip()

                

                package = (
                    db.query(Package)
                    .filter(
                        Package.url == url
                    )
                    .first()
                )

                if package:


                    package.last_seen_at = (
                        datetime.utcnow()
                    )

                    package.is_active = True


                    if title:

                        package.title = title

                    existing_packages += 1

                    print()
                    print(
                        "♻️ EXISTING PACKAGE"
                    )

                    print(
                        f"Title: {title}"
                    )

                    print(
                        f"URL: {url}"
                    )

                else:

                    

                    package = Package(
                        route_id=route.id,
                        url=url,
                        title=title,
                        is_active=True,
                        first_seen_at=datetime.utcnow(),
                        last_seen_at=datetime.utcnow(),
                    )

                    db.add(
                        package
                    )


                    db.flush()

                    new_packages += 1

                    print()
                    print(
                        "🆕 NEW PACKAGE"
                    )

                    print(
                        f"Title: {title}"
                    )

                    print(
                        f"URL: {url}"
                    )

                    #
                    # اگر Baseline داریم،
                    # یعنی این Package واقعاً
                    # بعداً اضافه شده.
                    #
                    # پس Change + Task بساز.
                    #

                    if has_baseline:

                        create_change_with_task(
                            db,
                            route_id=route.id,
                            package_id=package.id,
                            change_type="package_added",
                            package_name=title,
                            old_value=None,
                            new_value=url,
                        )

                        print(
                            "🔔 Change created: package_added"
                        )


            existing_route_packages = (
                db.query(Package)
                .filter(
                    Package.route_id == route.id,
                    Package.is_active == True
                )
                .all()
            )

            for old_package in existing_route_packages:

                if (
                    old_package.url
                    not in discovered_urls
                ):

                    old_package.is_active = False

                    old_package.last_seen_at = (
                        datetime.utcnow()
                    )

                    removed_packages += 1

                    print()
                    print(
                        "❌ PACKAGE REMOVED"
                    )

                    print(
                        f"Title: {old_package.title}"
                    )

                    print(
                        f"URL: {old_package.url}"
                    )

                    #
                    # فقط اگر Baseline داشتیم،
                    # حذف شدن Package را
                    # Change واقعی حساب کن.
                    #

                    if has_baseline:

                        create_change_with_task(
                            db,
                            route_id=route.id,
                            package_id=old_package.id,
                            change_type="package_removed",
                            package_name=old_package.title,
                            old_value=old_package.url,
                            new_value=None,
                        )

                        print(
                            "🔔 Change created: package_removed"
                        )

            db.commit()

            await browser.close()

        print()
        print("=" * 70)
        print("DISCOVERY RESULT")
        print("=" * 70)

        print(
            f"Package pages found: {len(discovered_urls)}"
        )

        print(
            f"New packages: {new_packages}"
        )

        print(
            f"Existing packages: {existing_packages}"
        )

        print(
            f"Removed packages: {removed_packages}"
        )

        print()
        print(
            "✅ Package discovery completed"
        )


        return {
            "route_id": route.id,
            "route_name": route.name,
            "package_pages_found": len(
                discovered_urls
            ),
            "new_packages": new_packages,
            "existing_packages": existing_packages,
            "removed_packages": removed_packages,
            "discovered_urls": sorted(
                discovered_urls
            ),
        }

    except Exception as exc:

        db.rollback()

        print()
        print("=" * 70)
        print("❌ PACKAGE DISCOVERY FAILED")
        print("=" * 70)

        print(
            f"Route ID: {route_id}"
        )

        print(
            f"Error: {exc}"
        )

        raise

    finally:

        db.close()