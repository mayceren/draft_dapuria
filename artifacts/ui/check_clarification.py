"""Exercise the reported stock-variant reply with fixture recipe retrieval."""

import json
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

OUTPUT = Path(__file__).resolve().parent


def exercise(page, suffix):
    page.goto("http://127.0.0.1:8518")
    composer = page.get_by_test_id("stChatInputTextArea")
    composer.fill("aku punya nasi, blueband, telur, garam, dan lada")
    composer.press("Enter")
    page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True).wait_for(timeout=15000)
    question = page.locator('.st-key-bubble_assistant_latest [data-testid="stChatMessageContent"]').inner_text()
    assert question == "Ada kaldu juga? Kalau nggak ada, kita lanjut pakai bahan yang kamu punya."
    assert question.count("?") == 1
    chat_id = parse_qs(urlsplit(page.url).query)["chat"][0]
    page.reload()
    page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True).wait_for()
    composer.fill("adanya kaldu jamur")
    composer.press("Enter")
    expect(composer).to_be_disabled()
    page.locator(".recipe-full").wait_for(timeout=15000)
    expect(composer).to_have_count(0)
    assert "kaldu jamur" in page.locator(".pantry-summary").inner_text()
    assert page.get_by_test_id("stException").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
    with sqlite3.connect(OUTPUT / "clarification-preview.sqlite3") as connection:
        state = json.loads(connection.execute(
            "SELECT snapshot FROM conversations WHERE owner_id='local' AND id=?", (chat_id,),
        ).fetchone()[0])
    assert state["inventory"] == ["nasi", "blueband", "telur", "garam", "lada", "kaldu jamur"]
    assert state["pending"] is None
    assert all("kaldu ayam" not in recipe["matched_recipe_items"] for recipe in state["latest_result"]["results"])
    page.locator(".pantry-summary").scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / f"clarification-variant-{suffix}.png"))
    print(f"{suffix}: one natural question, pending history resumed, mushroom stock accepted without generic/chicken stock", flush=True)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        exercise(browser.new_page(viewport={"width": 1440, "height": 1100}), "desktop")
        exercise(browser.new_page(viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True, reduced_motion="reduce"), "mobile")
        browser.close()


if __name__ == "__main__":
    main()
