import logging
import sys
import time
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse
from playwright.sync_api import sync_playwright, Page


PROJECT_DIRECTORY = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_DIRECTORY.joinpath("data")


def set_up_logging(is_debug: bool) -> None:
    """Set up logging for this script."""
    level = logging.DEBUG if is_debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def scroll_to_bottom_of_page(page: Page, max_scrolls: int = 50) -> None:
    """Scroll to the bottom of an infinite scrolling page."""

    for i in range(max_scrolls):
        old_height = page.evaluate("document.body.scrollHeight")
        page.keyboard.press("End")

        page.wait_for_timeout(3000)
        new_height = page.evaluate("document.body.scrollHeight")
        logging.debug(f"Scroll {i + 1:02d}: {old_height = }, {new_height = }")

        if new_height == old_height:
            break


def extract_coupon_urls(page: Page) -> list[str]:
    """Extract Great Clips coupon URLs from meta ads."""
    hrefs = page.locator('a[href*="offers.greatclips.com"]').evaluate_all(
        "elements => elements.map(element => element.href)"
    )
    logging.debug(f"Located {len(hrefs)} matching links on page.")
    coupon_urls = set()
    for href in hrefs:
        cleaned_href = unquote(href)
        parsed_href = urlparse(cleaned_href)
        logging.debug(parsed_href)
        coupon_url = parse_qs(parsed_href.query).get("u", [])[0]
        if coupon_url is not None:
            coupon_urls.add(coupon_url)
        else:
            logging.debug(f"No coupon URL found in {cleaned_href}.")
    coupon_urls = sorted(coupon_urls)
    logging.debug(f"Extracted {len(coupon_urls)} coupon URLs.")
    return coupon_urls


def save_coupon_urls(urls: list[str]) -> None:
    """Write the coupon URLs to a text file."""
    save_path = DATA_DIRECTORY.joinpath("coupon_urls.txt")
    save_path.write_text("\n".join(urls), encoding="utf-8")
    logging.debug(f"Wrote {len(urls)} coupon URLS to {save_path.as_posix()}.")


def main() -> None:
    _start = time.perf_counter()

    parser = ArgumentParser(description=f"{Path(__file__).name} script.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Set logging level to DEBUG",
    )
    args = parser.parse_args()
    set_up_logging(args.debug)

    logging.info(f"Running {Path(__file__).name}.")
    logging.info("Launching Playwright.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        logging.info("Fetching Meta ads search page.")
        meta_ads_url = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&sort_data[mode]=relevancy_monthly_grouped&sort_data[direction]=desc&view_all_page_id=93203055080"
        page.goto(meta_ads_url, wait_until="networkidle")
        logging.info("Scrolling to bottom of page.")
        scroll_to_bottom_of_page(page)
        logging.info("Extracting coupon URLs.")
        coupon_urls = extract_coupon_urls(page)
        logging.info("Saving coupon URLs.")
        save_coupon_urls(coupon_urls)
    _end = time.perf_counter()
    logging.info(
        f"Finished running {Path(__file__).name} in {(_end - _start):02.2f} seconds."
    )


if __name__ == "__main__":
    main()
