"""Browser checks against preview_chat.py (deliberately slow fake retrieval)."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUTPUT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8518"


def settled(page):
    page.wait_for_function("document.querySelector('[data-testid=stApp]').getAttribute('data-test-script-state') === 'notRunning'")
    page.evaluate("""() => Promise.all(document.getAnimations()
        .filter(a => Number.isFinite(a.effect.getTiming().iterations))
        .map(a => a.finished.catch(() => {})))""")


def check_bubbles(page):
    bounds = page.locator(".brand").bounding_box()
    users = page.locator('[class*="st-key-bubble_user_"] [data-testid="stChatMessage"]')
    for bubble in users.all():
        rect = bubble.bounding_box()
        assert abs(rect["x"] + rect["width"] - bounds["x"] - bounds["width"]) < 3
        assert rect["width"] < bounds["width"]
    assistants = page.locator('[class*="st-key-bubble_assistant_"] [data-testid="stChatMessage"]')
    for bubble in assistants.all():
        rect = bubble.bounding_box()
        assert abs(rect["x"] - bounds["x"]) < 3
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
    assert page.get_by_test_id("stException").count() == 0


def exercise(page, suffix):
    page.goto(URL)
    composer = page.get_by_test_id("stChatInputTextArea")
    composer.fill("aku punya nasi sama telur, jangan pakai ayam")
    composer.press("Enter")
    expect(composer).to_be_disabled()
    send = page.get_by_test_id("stChatInput").locator("button")
    assert send.count() > 0
    assert send.evaluate_all("buttons=>buttons.every(b=>b.disabled)")
    expect(page.get_by_test_id("stMultiSelect")).to_have_count(0)
    page.screenshot(path=str(OUTPUT / f"direct-loading-{suffix}.png"), full_page=True)
    no = page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True)
    no.wait_for(timeout=15000)
    expect(composer).to_be_enabled()
    no.click()
    page.locator(".recipe-full").wait_for()
    settled(page)
    expect(composer).to_have_count(0)
    expect(page.get_by_role("button", name="Lanjutkan percakapan", exact=True)).to_be_visible()
    expect(page.get_by_test_id("stMultiSelect")).to_have_count(0)
    assert "kaldu ayam" not in page.locator(".recipe-full .ingredients").inner_text()
    assert page.locator(".recipe-head h2").inner_text() == "Resep uji 2"
    assert page.locator(".other-row").count() == 4
    expect(page.get_by_text("Bahan yang dihindari: ayam", exact=True)).to_be_visible()
    check_bubbles(page)
    saved_url = page.url
    page.reload()
    page.locator(".recipe-full").wait_for()
    expect(composer).to_have_count(0)
    assert page.url == saved_url
    expect(page.get_by_text("Bahan yang dihindari: ayam", exact=True)).to_be_visible()
    page.screenshot(path=str(OUTPUT / f"filtered-results-{suffix}.png"), full_page=True)
    page.get_by_role("button", name="Lanjutkan percakapan", exact=True).click()
    composer.fill("aku juga punya wortel")
    composer.press("Enter")
    no.wait_for(timeout=15000)
    no.click()
    page.locator(".recipe-full").wait_for()
    settled(page)
    assert "wortel" in page.locator(".recipe-full .ingredients").inner_text()
    assert "kaldu ayam" not in page.locator(".recipe-full .ingredients").inner_text()
    page.get_by_role("button", name="Lanjutkan percakapan", exact=True).click()
    composer.fill("boleh pakai ayam")
    composer.press("Enter")
    no.wait_for(timeout=15000)
    no.click()
    page.locator(".recipe-full").wait_for()
    settled(page)
    expect(page.get_by_text("Bahan yang dihindari: ayam", exact=True)).to_have_count(0)
    assert "kaldu ayam" in page.locator(".recipe-full .ingredients").inner_text()
    assert "wortel" in page.locator(".recipe-full .ingredients").inner_text()
    check_bubbles(page)
    latest_user = page.locator('.st-key-bubble_user_latest [data-testid="stChatMessage"]')
    motion = latest_user.evaluate("e=>getComputedStyle(e).animationName")
    assert motion == ("none" if suffix == "mobile" else "messageIn")
    page.screenshot(path=str(OUTPUT / f"direct-results-{suffix}.png"), full_page=True)
    page.get_by_role("button", name="Cari resep baru", exact=True).click()
    expect(composer).to_be_enabled()
    expect(page.get_by_text("Bahan yang dihindari: ayam", exact=True)).to_have_count(0)
    expect(page.locator(".recipe-full")).to_have_count(0)
    print(f"{suffix}: direct search without editor, disabled send, filters, context, permissions, refresh and new conversation passed", flush=True)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        exercise(page, "desktop")
        mobile = browser.new_page(viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True, reduced_motion="reduce")
        exercise(mobile, "mobile")
        print("Reduced motion respected", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
