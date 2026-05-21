import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Union
from urllib.parse import urldefrag, urlparse
from xml.etree import ElementTree

import requests

# Crawl4AI imports
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    MemoryAdaptiveDispatcher,
)
from slugify import slugify
from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


def is_sitemap(url: str) -> bool:
    return url.endswith("sitemap.xml") or "sitemap" in urlparse(url).path


def is_txt(url: str) -> bool:
    return url.endswith(".txt")


def _safe_filename(url: str, ext: str) -> str:
    # Use slug + short hash to avoid collisions and keep names readable
    slug = slugify(url)[:80] or "page"
    h = hashlib.sha1(url.encode("utf8")).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{timestamp}-{h}.{ext}"


def ensure_dir(path: Union[str, Path]) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _save_markdown(
    outdir: Path, crawl_results: list[dict[str, Any]], encoding: str = "utf-8"
) -> None:
    for items in crawl_results:
        filename = _safe_filename(items["url"], "md")
        outpath = outdir / filename
        outpath.parent.mkdir(parents=True, exist_ok=True)
        with open(outpath, "w", encoding=encoding) as f:
            f.write(items["markdown"])
            logger.info(f"Saved: {outpath}")


async def crawl_markdown_file(url: str) -> list[dict[str, Any]]:
    browser_config = BrowserConfig(headless=True)
    crawl_config = CrawlerRunConfig()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=crawl_config)
        if result.success and result.markdown:
            return [{"url": url, "markdown": result.markdown}]
        else:
            logger.warning(f"Failed to crawl {url}: {result.error_message}")
            return []


def parse_sitemap(sitemap_url: str) -> list[str]:
    resp = requests.get(sitemap_url)
    urls = []

    if resp.status_code == 200:
        try:
            tree = ElementTree.fromstring(resp.content)
            urls = [loc.text for loc in tree.findall(".//{*}loc")]
        except Exception as e:
            logger.error(f"Error parsing sitemap XML: {e}")
    return urls


async def crawl_batch(
    urls: list[str], max_concurrent: int = 10
) -> list[dict[str, Any]]:
    """Batch crawl using logic from 3-crawl_sitemap_in_parallel.py."""
    browser_config = BrowserConfig(headless=True, verbose=False)
    crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=70.0,
        check_interval=1.0,
        max_session_permit=max_concurrent,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(
            urls=urls, config=crawl_config, dispatcher=dispatcher
        )
        return [
            {"url": r.url, "markdown": r.markdown}
            for r in results
            if r.success and r.markdown
        ]


def _extract_url_to_markdown(
    start_url: str,
    outdir: Path,
    depth: int,
    max_pages: int,
    follow_external: bool,
    concurrency: int,
    sitemap: bool,
):
    if sitemap and start_url[-1] == "/":
        start_url = f"{start_url}sitemap.xml"
    elif sitemap:
        start_url = f"{start_url}/sitemap.xml"

    crawl_results = []
    if is_txt(start_url):
        logger.info(f"Detected .txt/markdown file: {start_url}")
        crawl_results.extend(asyncio.run(crawl_markdown_file(start_url)))
    elif is_sitemap(start_url):
        logger.info(f"Detected sitemap: {start_url}")
        sitemap_urls = parse_sitemap(start_url)
        if not sitemap_urls:
            logger.warning("No URLs found in sitemap.")
            return
        logger.info(f"Found {len(sitemap_urls)} URLs in sitemap.")
        crawl_results.extend(
            asyncio.run(crawl_batch(sitemap_urls, max_concurrent=concurrency))
        )
    else:
        logger.info(f"Detected regular URL: {start_url}")
        crawl_results = asyncio.run(
            crawl_recursive_internal_links(
                [start_url], max_depth=depth, max_concurrent=concurrency
            )
        )

    _save_markdown(outdir, crawl_results)


async def crawl_recursive_internal_links(
    start_urls, max_depth=3, max_concurrent=10
) -> list[dict[str, Any]]:
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=70.0,
        check_interval=1.0,
        max_session_permit=max_concurrent,
    )

    visited = set()

    def normalize_url(url):
        return urldefrag(url)[0]

    current_urls = set([normalize_url(u) for u in start_urls])
    results_all = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for depth in range(max_depth):
            urls_to_crawl = [
                normalize_url(url)
                for url in current_urls
                if normalize_url(url) not in visited
            ]
            if not urls_to_crawl:
                break

            results = await crawler.arun_many(
                urls=urls_to_crawl, config=run_config, dispatcher=dispatcher
            )
            next_level_urls = set()

            for result in results:
                norm_url = normalize_url(result.url)
                visited.add(norm_url)

                if result.success and result.markdown:
                    results_all.append({"url": result.url, "markdown": result.markdown})
                    for link in result.links.get("internal", []):
                        next_url = normalize_url(link["href"])
                        if next_url not in visited:
                            next_level_urls.add(next_url)

            current_urls = next_level_urls

    return results_all
