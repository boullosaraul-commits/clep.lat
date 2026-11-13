"""Captura y evidencia del mismo documento, sin resolver desafíos de acceso."""
import os
import shutil
from urllib.parse import urlsplit

from calidad_visual import document_check, raster_check

DOM_EVIDENCE = """() => {
  const visible = e => e.getBoundingClientRect().width > 0 &&
    e.getBoundingClientRect().height > 0 && getComputedStyle(e).visibility !== 'hidden';
  return {
    title: document.title,
    headings: [...document.querySelectorAll('h1,h2,[role=heading]')]
      .filter(visible).slice(0, 12).map(e => e.innerText),
    ready: document.readyState === 'complete' && !document.querySelector('main[aria-busy=true], main [role=progressbar]'),
    challenge: !!document.querySelector(
      'iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"], ' +
      '#challenge-form, #cf-challenge-running, script[src*="/cdn-cgi/challenge-platform/"]')
  };
}"""


def capture(url, title, width, height):
    from playwright.sync_api import sync_playwright

    executable = os.getenv("CLEP_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": height}, accept_downloads=False)
            response = page.goto(url, wait_until="load", timeout=15000)
            evidence = page.evaluate(DOM_EVIDENCE)
            headers = response.headers if response else {}
            evidence.update(
                status=response.status if response else None,
                mime=headers.get("content-type", "").split(";")[0].lower(),
                url=page.url,
                challenge=evidence["challenge"] or headers.get("cf-mitigated") == "challenge",
            )
            check = document_check(evidence, title)
            content = b""
            if check.valid:
                content = page.screenshot(timeout=6000, animations="disabled")
                check = raster_check(content, capture_title=title)
            location = urlsplit(evidence["url"])
            return content, check, f"HTTP={evidence['status']}; destino={location.hostname or '?'}"
        finally:
            browser.close()
