import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def settle(page):
    page.get_by_test_id("stChatInputTextArea").wait_for()
    page.wait_for_function("document.querySelector('[data-testid=stApp]').getAttribute('data-test-script-state') === 'notRunning'")
    page.evaluate("""() => Promise.all(document.getAnimations()
      .filter(a => Number.isFinite(a.effect.getTiming().iterations))
      .map(a => a.finished.catch(() => {})))""")


def main():
    output = Path(__file__).resolve().parent
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8517", wait_until="domcontentloaded")
        page.locator(".hero h2").wait_for(timeout=30000)
        page.wait_for_function("getComputedStyle(document.querySelector('.hero')).opacity === '1'")
        settle(page)
        page.screenshot(path=str(output / "home-desktop.png"), full_page=True)
        assert page.get_by_test_id("stException").count() == 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        print("Desktop welcome: rendered without overflow or exceptions", flush=True)
        mobile = browser.new_context(viewport={"width": 390, "height": 844},
                                     device_scale_factor=1, is_mobile=True, has_touch=True,
                                     reduced_motion="reduce")
        phone = mobile.new_page()
        phone.goto("http://127.0.0.1:8517", wait_until="domcontentloaded")
        phone.locator(".hero h2").wait_for(timeout=30000)
        collapse = phone.get_by_test_id("stSidebarCollapseButton").get_by_role("button")
        if collapse.count() and collapse.is_visible():
            collapse.click()
        settle(phone)
        phone.evaluate("document.activeElement.blur(); document.querySelector('.stMain').scrollTop = 0;")
        phone.wait_for_function("""() => {
            document.activeElement.blur();
            document.querySelector('.stMain').scrollTop = 0;
            return document.querySelector('.brand').getBoundingClientRect().top >= 56;
        }""")
        phone.screenshot(path=str(output / "home-mobile.png"), full_page=False)
        assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert phone.locator(".floating-label").first.evaluate("e => getComputedStyle(e).animationName") == "none"
        assert phone.get_by_test_id("stException").count() == 0
        assert not errors, errors
        print("Mobile welcome: no overflow; reduced motion respected", flush=True)
        if "--restore" in sys.argv:
            with sqlite3.connect(output / "preview.sqlite3") as connection:
                chat_id = connection.execute(
                    "SELECT id FROM conversations WHERE owner_id='local' ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()[0]
            saved_url = "http://127.0.0.1:8517/?chat=" + chat_id
            page.goto(saved_url, wait_until="domcontentloaded")
            page.locator(".recipe-full").first.wait_for(timeout=15000)
            settle(page)
            page.locator(".result-intro").evaluate("e => e.scrollIntoView({block:'start'})")
            page.screenshot(path=str(output / "results-desktop.png"), full_page=False)
            phone.goto(saved_url, wait_until="domcontentloaded")
            phone.locator(".recipe-full").first.wait_for(timeout=15000)
            collapse = phone.get_by_test_id("stSidebarCollapseButton").get_by_role("button")
            if collapse.count() and collapse.is_visible():
                collapse.click()
            settle(phone)
            phone.evaluate("document.activeElement.blur()")
            phone.locator(".result-intro").evaluate("e => e.scrollIntoView({block:'start'})")
            phone.screenshot(path=str(output / "results-mobile.png"), full_page=False)
            assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            assert page.get_by_test_id("stException").count() == 0
            assert phone.get_by_test_id("stException").count() == 0
            print("Saved recipes restored after a real server restart without loading SBERT", flush=True)
        if "--exercise" in sys.argv:
            page.get_by_test_id("stChatInputTextArea").fill("aku punya nasi sama telur")
            page.get_by_test_id("stChatInputTextArea").press("Enter")
            page.locator(".activity").first.wait_for(timeout=15000)
            page.screenshot(path=str(output / "search-loading.png"), full_page=True)
            print("Submitted pantry; waiting for real SBERT and clarification...", flush=True)
            page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True).wait_for(timeout=180000)
            page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True).click()
            page.locator(".recipe-full").first.wait_for(timeout=120000)
            settle(page)
            page.locator(".result-intro").evaluate("e => e.scrollIntoView({block:'start'})")
            page.screenshot(path=str(output / "results-desktop.png"), full_page=True)
            assert page.get_by_test_id("stException").count() == 0
            with page.expect_download() as download_info:
                page.get_by_role("button", name="Simpan resep", exact=True).first.click()
            download_info.value.save_as(str(output / "recipe-example.txt"))
            assert "LANGKAH MEMASAK" in (output / "recipe-example.txt").read_text(encoding="utf-8")
            conversation_url = page.url
            print("Real recipe cards and recipe download passed", flush=True)
            page.reload(wait_until="domcontentloaded")
            page.locator(".recipe-full").first.wait_for(timeout=30000)
            page.get_by_role("button", name="Mulai percakapan baru", exact=True).click()
            page.locator(".hero h2").wait_for(timeout=15000)
            page.get_by_role("button", name="aku punya nasi sama telur", exact=True).click()
            page.locator(".recipe-full").first.wait_for(timeout=15000)
            print("Browser refresh and reopening a saved conversation passed", flush=True)
            phone.goto(conversation_url, wait_until="domcontentloaded")
            phone.locator(".recipe-full").first.wait_for(timeout=30000)
            collapse = phone.get_by_test_id("stSidebarCollapseButton").get_by_role("button")
            if collapse.count() and collapse.is_visible():
                collapse.click()
            settle(phone)
            phone.locator(".result-intro").evaluate("e => e.scrollIntoView({block:'start'})")
            phone.screenshot(path=str(output / "results-mobile.png"), full_page=True)
            assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            assert phone.get_by_test_id("stException").count() == 0
            assert not errors, errors
            print("Mobile recipe cards passed; history URL: " + conversation_url, flush=True)
        browser.close()


if __name__ == "__main__":
    main()
