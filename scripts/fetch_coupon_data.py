import asyncio
import logging
import re
import sys
from argparse import ArgumentParser
from datetime import date, datetime
from pathlib import Path
import time

from crawlee import ConcurrencySettings
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.router import Router
from crawlee.storage_clients import MemoryStorageClient


PROJECT_DIRECTORY = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_DIRECTORY.joinpath("data")
router = Router[PlaywrightCrawlingContext]()


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


def load_coupon_urls() -> list[str]:
    """Load coupon URLs from the data directory."""
    load_path = DATA_DIRECTORY.joinpath("coupon_urls.txt")
    coupon_urls = load_path.read_text(encoding="utf-8").splitlines()
    logging.debug(f"Loaded {len(coupon_urls)} coupon URLs from {load_path.as_posix()}.")
    return coupon_urls


@router.default_handler
async def default_handler(context: PlaywrightCrawlingContext) -> None:
    """Extract data from coupon pages."""
    context.log.info(f"Processing {context.request.url}")
    description_element = await context.page.query_selector("p#description")
    description = (
        await description_element.text_content()
        if description_element is not None
        else None
    )
    terms_and_conditions_element = await context.page.query_selector(
        "p#terms_and_conditions"
    )
    terms_and_conditions = (
        await terms_and_conditions_element.text_content()
        if terms_and_conditions_element is not None
        else None
    )

    price = None
    if match := re.search(r"\$\d+.?\d*", description):
        price = match[0]

    expiration_date = None
    if match := re.search(r"\d{2}/\d{2}/\d{4}", terms_and_conditions):
        date_string = match[0]
        expiration_date = datetime.strptime(date_string, "%m/%d/%Y").date()

    data = {
        "url": context.request.url,
        "price": price,
        "expriation_date": expiration_date,
        "description": description,
        "terms_and_conditions": terms_and_conditions,
    }

    # Only keep active coupons
    if expiration_date > date.today():
        await context.push_data(data)


async def main() -> None:
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

    storage_client = MemoryStorageClient()
    concurrency_settings = ConcurrencySettings(
        desired_concurrency=5,
        min_concurrency=1,
        max_concurrency=10,
    )
    crawler = PlaywrightCrawler(
        browser_type="chromium",
        concurrency_settings=concurrency_settings,
        request_handler=router,
        storage_client=storage_client,
    )
    urls_to_crawl = load_coupon_urls()
    await crawler.run(urls_to_crawl)
    await crawler.export_data(DATA_DIRECTORY.joinpath("coupon_data.json"), indent=4)

    _end = time.perf_counter()
    logging.info(
        f"Finished running {Path(__file__).name} in {(_end - _start):02.2f} seconds."
    )


if __name__ == "__main__":
    asyncio.run(main())
