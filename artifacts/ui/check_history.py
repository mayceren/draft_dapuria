"""Browser checks using fixture chats in the isolated preview database."""

import json
import sqlite3
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUTPUT = Path(__file__).resolve().parent
DATABASE = OUTPUT / "history-actions-preview.sqlite3"
FIRST, SECOND = "history-first", "history-second"


def seed():
    recipes = [{"id": f"recipe-{i}", "title": f"Menu contoh {i}",
                "ingredient_names": ["nasi", "telur", "garam"],
                "matched_recipe_items": ["nasi", "telur"], "missing_items": ["garam"],
                "steps_text": "1. Siapkan bahan. 2. Panaskan 1.5 sdm minyak. Masak hingga matang. 3. Sajikan."} for i in range(5)]
    result = {"status": "ok", "user_ingredients": ["nasi", "telur"], "results": recipes}
    state = {"phase": "await_query", "pending": None, "latest_result": result,
             "inventory": ["nasi", "telur"], "excluded_ingredients": [],
             "messages": [{"role": "user", "content": "Aku punya nasi dan telur"},
                          {"role": "assistant", "content": "Ini pilihan resepmu.", "result": result}]}
    with sqlite3.connect(DATABASE) as connection:
        for chat_id, title, day in [(FIRST, "Sarapan sederhana", "24"), (SECOND, "Menu makan malam", "25")]:
            timestamp = f"2026-10-{day}T12:00:00+00:00"
            connection.execute("""INSERT INTO conversations
                (owner_id, id, title, created_at, updated_at, snapshot, pinned) VALUES (?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(owner_id, id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at,
                snapshot=excluded.snapshot, pinned=0""",
                ("local", chat_id, title, timestamp, timestamp, json.dumps(state)))


def menu(page, chat_id):
    body = page.get_by_test_id("stPopoverBody")
    if body.count() and body.is_visible():
        page.keyboard.press("Escape")
    page.locator(f".st-key-history_menu_{chat_id}").get_by_role("button").click()
    body.wait_for(state="visible")
    return body


def exercise(page, suffix):
    page.goto("http://127.0.0.1:8518")
    page.get_by_test_id("stChatInputTextArea").wait_for()
    seed()
    page.goto(f"http://127.0.0.1:8518/?chat={SECOND}")
    page.locator(".recipe-full").wait_for()
    expect(page.get_by_role("button", name="Simpan resep", exact=True)).to_have_count(0)
    expect(page.locator(".recipe-full .steps-list li")).to_have_text([
        "Siapkan bahan.", "Panaskan 1.5 sdm minyak. Masak hingga matang.", "Sajikan."])
    hint = page.get_by_text("Pilih Lanjutkan percakapan untuk menambah bahan atau batasan, atau Cari resep baru untuk mulai lagi.", exact=True)
    actions = page.locator(".st-key-result_actions")
    assert hint.bounding_box()["y"] < actions.bounding_box()["y"]
    actions.scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / f"results-bottom-actions-{suffix}.png"))
    page.locator(".st-key-detail_recipe_2").get_by_role("button").click()
    recipe_dialog = page.get_by_role("dialog")
    expect(recipe_dialog.locator(".steps-list li")).to_have_text([
        "Siapkan bahan.", "Panaskan 1.5 sdm minyak. Masak hingga matang.", "Sajikan."])
    expect(recipe_dialog.get_by_role("button", name="Simpan resep", exact=True)).to_have_count(0)
    recipe_dialog.get_by_role("button", name="Kembali ke rekomendasi", exact=True).click()
    expect(recipe_dialog).to_have_count(0)
    expect(page.get_by_role("button", name="Unduh chat", exact=True)).to_have_count(0)
    expect(page.get_by_test_id("stMainMenu")).to_be_hidden()
    page.get_by_test_id("stMain").evaluate("e => e.scrollTop = 0")
    brand_box = page.locator(".brand").bounding_box()
    assert 0 <= brand_box["y"] <= 25, brand_box
    expand = page.get_by_test_id("stExpandSidebarButton")
    if expand.count() and expand.is_visible():
        arrow_box = expand.bounding_box()
        logo_box = page.locator(".brand-icon").bounding_box()
        assert arrow_box["x"] + arrow_box["width"] <= logo_box["x"], (arrow_box, logo_box)
    page.screenshot(path=str(OUTPUT / f"main-conversation-{suffix}.png"))
    expect(page.locator(".recipe-reasons, .reason-summary")).to_have_count(0)
    page.locator(".recipe-full").scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / f"recommendation-results-{suffix}.png"))
    sidebar = page.get_by_test_id("stSidebar")
    expand = page.get_by_test_id("stExpandSidebarButton")
    if expand.count() and expand.is_visible():
        expand.click()
    body = menu(page, FIRST)
    body.get_by_role("button", name="Pin chat", exact=True).click()
    expect(sidebar.locator(".history-group").first).to_have_text("Disematkan")
    assert page.url.endswith(f"chat={SECOND}")
    body = menu(page, FIRST)
    expect(body.get_by_role("button", name="Lepas pin", exact=True)).to_be_visible()
    expect(body.get_by_role("button")).to_have_count(3)
    expect(body.get_by_role("textbox")).to_have_count(0)
    body.get_by_role("button", name="Ubah nama", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).fill("Menu sarapan favorit")
    page.screenshot(path=str(OUTPUT / f"history-rename-{suffix}.png"))
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).press("Enter")
    expect(dialog).to_have_count(0)
    title = sidebar.get_by_role("button", name="Menu sarapan favorit", exact=True)
    expect(title).to_contain_text("Menu sarapan favorit")
    page.reload()
    page.locator(".recipe-full").wait_for()
    if expand.count() and expand.is_visible():
        expand.click()
    expect(sidebar.locator(".history-group").first).to_have_text("Disematkan")
    body = menu(page, FIRST)
    page.screenshot(path=str(OUTPUT / f"history-menu-{suffix}.png"))
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
    brand = sidebar.locator(".sidebar-brand").bounding_box()
    collapse = sidebar.get_by_role("button", name="Collapse sidebar", exact=True)
    arrow = collapse.bounding_box()
    assert abs((brand["y"] + brand["height"] / 2) - (arrow["y"] + arrow["height"] / 2)) <= 3
    assert brand["y"] < 25
    body.get_by_role("button", name="Ubah nama", exact=True).click()
    expect(dialog.get_by_role("textbox", name="Judul percakapan", exact=True)).to_have_value("Menu sarapan favorit")
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).fill("   ")
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).press("Enter")
    expect(dialog.get_by_text("Judul percakapan tidak boleh kosong.", exact=True)).to_be_visible()
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).fill("Jangan disimpan")
    dialog.get_by_role("button", name="Batal", exact=True).click()
    expect(dialog).to_have_count(0)
    expect(sidebar.get_by_role("button", name="Menu sarapan favorit", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    collapse.click()
    expect(expand).to_be_visible()
    expand.click()
    body = menu(page, FIRST)
    body.get_by_role("button", name="Lepas pin", exact=True).click()
    expect(sidebar.get_by_text("Disematkan", exact=True)).to_have_count(0)
    body = menu(page, FIRST)
    body.get_by_role("button", name="Hapus chat", exact=True).click()
    expect(page.locator(f".st-key-history_{FIRST}")).to_have_count(0)
    assert page.url.endswith(f"chat={SECOND}")
    expect(page.locator(".recipe-full")).to_be_visible()
    body = menu(page, SECOND)
    body.get_by_role("button", name="Hapus chat", exact=True).click()
    page.get_by_test_id("stChatInputTextArea").wait_for()
    expect(page.locator(".recipe-full")).to_have_count(0)
    assert page.get_by_test_id("stException").count() == 0
    with sqlite3.connect(DATABASE) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversations WHERE id IN (?, ?)",
                                  (FIRST, SECOND)).fetchone()[0] == 0
    print(f"{suffix}: bottom actions, numbered cooking steps, no downloads, rename, pin and deletion passed", flush=True)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        exercise(browser.new_page(viewport={"width": 1440, "height": 1100}), "desktop")
        exercise(browser.new_page(viewport={"width": 390, "height": 844},
                                   is_mobile=True, has_touch=True, reduced_motion="reduce"), "mobile")
        browser.close()


if __name__ == "__main__":
    main()
