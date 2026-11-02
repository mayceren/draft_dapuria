"""Browser regression on the real retrieval server started by preview_query.py."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUTPUT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8518"
QUERY = "dada ayam 250 gr, kecap, garam, saus tiram, bawang putih, bawang bombay"


def capture_results(page, label):
    page.locator(".recipe-full").wait_for(timeout=120000)
    expect(page.locator(".recipe-head h2")).to_have_text("826) Ayam Kecap Bombay")
    expect(page.locator(".recipe-full .chip.missing")).to_have_text(["air", "minyak goreng"])
    expect(page.locator(".pantry-summary")).not_to_contain_text("250 gr")
    assert all(any(char.isalpha() for char in name) for name in
               page.locator(".recipe-full .ingredients li").all_text_contents())
    assert page.get_by_test_id("stException").count() == 0
    page.locator(".result-intro").evaluate("e=>e.scrollIntoView({block:'start'})")
    page.screenshot(path=str(OUTPUT / f"results-{label}.png"), animations="disabled")
    page.locator(".other-heading").scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / f"alternatives-{label}.png"), animations="disabled")
    titles = page.locator(".other-row h3").all_text_contents()
    assert len(set(title.casefold() for title in titles)) == len(titles)
    page.locator(".st-key-detail_recipe_2").get_by_role("button").click()
    dialog = page.get_by_role("dialog")
    assert all(any(char.isalpha() for char in name) for name in
               dialog.locator(".ingredients li").all_text_contents())
    page.screenshot(path=str(OUTPUT / f"detail-{label}.png"), animations="disabled")
    dialog.get_by_role("button", name="Kembali ke rekomendasi", exact=True).click()
    expect(dialog).to_have_count(0)
    print(label, "top recipe needs air + minyak goreng; canonical input and alternate detail passed", flush=True)
    return titles


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, reduced_motion="reduce")
    page.goto(URL)
    composer = page.get_by_test_id("stChatInputTextArea")
    composer.fill(QUERY)
    composer.press("Enter")
    page.wait_for_function("""() => document.querySelector('.recipe-full') ||
        Array.from(document.querySelectorAll('button')).some(b=>b.textContent.includes('Tidak ada, lanjut saja'))""", timeout=120000)
    no = page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True)
    if no.count() and no.is_visible():
        no.click()
    titles = capture_results(page, "desktop")
    saved_url = page.url
    phone = browser.new_page(viewport={"width": 390, "height": 844},
                             is_mobile=True, has_touch=True, reduced_motion="reduce")
    phone.goto(saved_url)
    assert capture_results(phone, "mobile") == titles
    (OUTPUT / "browser_verification.json").write_text(json.dumps(
        {"query": QUERY, "primary_title": "826) Ayam Kecap Bombay", "missing_items": ["air", "minyak goreng"],
         "alternative_titles": titles, "desktop": "passed", "mobile": "passed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    browser.close()
