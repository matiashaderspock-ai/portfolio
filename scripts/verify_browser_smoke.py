#!/usr/bin/env python3
"""Bounded, loopback-only browser smoke checks for the portfolio.

Start an ephemeral preview automatically. Requires Playwright and Chromium;
use --browser /path/to/chromium to reuse a system installation.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ["grok", "gastalo", "cumpafit", "trading-bot-scout",
            "trading-automations", "monitor"]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def geometry(page):
    return page.evaluate("""() => Object.fromEntries(
      ['body', '.site-header', '#work', '.project-stage'].map(selector => {
        const box = document.querySelector(selector).getBoundingClientRect();
        return [selector, {left: box.left, width: box.width}];
      }))""")


def assert_stable(before, after):
    for selector in before:
        for dimension in ("left", "width"):
            change = abs(before[selector][dimension] - after[selector][dimension])
            assert change <= 0.5, (
                f"Film shifted {selector} {dimension} by {change:.2f}px: "
                f"{before[selector]} -> {after[selector]}"
            )


def check_page(browser, base, language, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    # Never fetch third-party fonts, analytics, or navigate to external apps.
    context.route("**/*", lambda route: route.continue_()
                  if route.request.url.startswith(base + "/") else route.abort())
    page = context.new_page()
    page.set_default_timeout(5000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(base + ("/es/" if language == "es" else "/") + "#work")
        expect(page.locator(".project-browser.is-ready")).to_be_visible()
        expect(page.locator(".project-tile")).to_have_count(len(PROJECTS))
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

        for index, project in enumerate(PROJECTS):
            expect(page.locator(".project-card:visible")).to_have_attribute("id", project)
            expect(page.locator(".project-controls [role=status]")).to_have_text(
                f"{index + 1:02d} / 06")
            if index < len(PROJECTS) - 1:
                page.locator(".project-controls button").last.click()
        expect(page.locator(".project-controls button").last).to_be_disabled()

        # Roving keyboard selection and both native installation disclosures.
        page.locator(".project-tile.is-selected").press("Home")
        expect(page.locator("#grok")).to_be_visible()
        for project in ("gastalo", "cumpafit"):
            page.locator(".project-tile.is-selected").press("ArrowRight")
            panel = page.locator("#" + project)
            expect(panel).to_be_visible()
            detail = panel.locator(".project-install")
            link = detail.locator("a")
            expect(link).not_to_be_visible()
            detail.locator("summary").press("Enter")
            expect(link).to_be_visible()
            expect(link).to_have_attribute(
                "href", f"https://matiashaderspock-ai.github.io/{project}/")
            expect(detail.locator("li")).to_have_count(2)
            detail.locator("summary").press("Space")
            expect(link).not_to_be_visible()

        page.locator(".project-tile.is-selected").press("End")
        expect(page.locator("#monitor")).to_be_visible()
        page.locator(".project-tile.is-selected").press("Home")
        stage = page.locator(".project-stage")
        stage.scroll_into_view_if_needed()
        box = stage.bounding_box()
        x, y = box["x"] + box["width"] * 0.6, box["y"] + 150
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x - 100, y, steps=6)
        page.mouse.up()
        expect(page.locator("#gastalo")).to_be_visible()
        expect(page.locator("dialog.project-film")).not_to_be_visible()
        page.locator(".project-tile.is-selected").press("Home")
        tile = page.locator(".project-tile").first
        dialog = page.locator("dialog.project-film")
        video = dialog.locator("video")
        for dismissal in ("button", "escape", "backdrop"):
            tile.focus()
            before = geometry(page)
            # Linux must retain classic scrollbars, or this regression is hidden.
            if width == 1180:
                assert page.evaluate("innerWidth - document.body.clientWidth") >= 10, (
                    "Classic scrollbar fixture is unavailable; shift check is invalid")
            tile.press("Enter")
            expect(dialog).to_be_visible()
            expect(video).to_have_attribute("src", "/media/bot-fleet-night.mp4")
            assert_stable(before, geometry(page))
            scroll_y = page.evaluate("scrollY")
            page.mouse.move(2, 2)
            page.mouse.wheel(0, 300)
            # Allow the browser's wheel action to settle before checking scroll lock.
            page.wait_for_timeout(100)
            assert abs(page.evaluate("scrollY") - scroll_y) <= 0.5
            if dismissal == "button":
                dialog.locator("button").click()
            elif dismissal == "escape":
                page.keyboard.press("Escape")
            else:
                page.mouse.click(2, 2)
            expect(dialog).not_to_be_visible()
            expect(tile).to_be_focused()
            # Native close queues its event; visibility can change before cleanup.
            page.wait_for_function("""() => {
              const film = document.querySelector('.project-film video');
              return !film.hasAttribute('src') && film.paused;
            }""")
            assert_stable(before, geometry(page))
        assert not errors, errors
        print(f"PASS {language} {width}px: navigation, pointer swipe, install help, stable film and dismissals")
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Optional system Chromium executable")
    args = parser.parse_args()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "public")))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=args.browser,
                # Playwright normally hides the scrollbar: that masks this bug.
                ignore_default_args=["--hide-scrollbars"],
                args=["--no-sandbox", "--disable-features=OverlayScrollbar"])
            try:
                for language in ("en", "es"):
                    for width in (1180, 390):
                        check_page(browser, base, language, width)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
