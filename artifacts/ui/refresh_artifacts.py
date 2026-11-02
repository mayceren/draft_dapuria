"""Capture current UI with sample corpus recipes and an isolated history store."""

import csv
import hashlib
import json
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent
DATABASE = OUTPUT / "artifacts-preview.sqlite3"
URL = "http://127.0.0.1:8518"
sys.path.insert(0, str(ROOT / "src"))

from dapuria.chat_history import ChatHistoryStore
from dapuria.preprocessing import ingredient_matches

PANTRY = ["nasi", "telur", "bawang putih", "kecap manis", "garam", "lada", "minyak goreng"]
TITLES = ["Nasi goreng telur", "Nasi Goreng Telur Cabe Hijau", "Nasi goreng smoke beef",
          "Nasi Goreng Merah Telur Ceplok", "Nasi Goreng Telur Sosis"]


def example_result():
    with (ROOT / "data/corpus/resep_5000_clean_SAFE.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    recipes = []
    for index, title in enumerate(TITLES):
        row = next(row for row in rows if row["title_clean"] == title)
        names = json.loads(row["ingredient_names"])
        matched = [name for name in names if any(ingredient_matches(item, name) for item in PANTRY)]
        recipes.append({"id": f"artifact-recipe-{index}", "title": title, "ingredient_names": names,
                        "matched_recipe_items": matched, "missing_items": [name for name in names if name not in matched],
                        "steps_text": row["steps_text"]})
    return {"status": "ok", "user_ingredients": PANTRY, "results": recipes}


def seed(store, result):
    state = {"phase": "await_query", "pending": None, "latest_result": result,
             "inventory": PANTRY, "excluded_ingredients": [],
             "messages": [{"role": "user", "content": "Aku punya nasi, telur, bawang putih, kecap manis, garam, lada, dan minyak goreng."},
                          {"role": "assistant", "content": "Ini lima ide masakan untukmu. Pilih resep yang paling kamu suka, ya.", "result": result}]}
    for chat_id, title in [("artifact-current", "Ide nasi goreng untuk hari ini"),
                           ("artifact-other", "Sarapan sederhana")]:
        store.save("local", chat_id, state)
        store.rename("local", chat_id, title)
    store.set_pinned("local", "artifact-other", True)
    return state


def settle(page):
    page.wait_for_function("document.querySelector('[data-testid=stApp]').getAttribute('data-test-script-state') === 'notRunning'")
    page.evaluate("""() => Promise.all(document.getAnimations()
        .filter(a => Number.isFinite(a.effect.getTiming().iterations))
        .map(a => a.finished.catch(() => {})))""")
    assert page.get_by_test_id("stException").count() == 0


def capture(page, *names):
    for name in names:
        page.screenshot(path=str(OUTPUT / name), animations="disabled")


def top(page):
    page.get_by_role("main").evaluate("e=>{document.activeElement.blur(); e.scrollTop=0;}")


def open_menu(page, chat_id):
    expand = page.get_by_test_id("stExpandSidebarButton")
    if expand.count() and expand.is_visible():
        expand.click()
    page.locator(f".st-key-history_menu_{chat_id}").get_by_role("button").click()
    body = page.get_by_test_id("stPopoverBody")
    expect(body).to_be_visible()
    return body


def exercise(page, suffix, store, result):
    page.goto(URL)
    page.locator(".hero").wait_for()
    settle(page)
    top(page)
    capture(page, f"home-{suffix}.png", *(["mobile-top-check.png"] if suffix == "mobile" else []))

    state = seed(store, result)
    page.goto(f"{URL}/?chat=artifact-current")
    page.locator(".recipe-full").wait_for()
    settle(page)
    expect(page.get_by_text("Detail penelitian", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Simpan resep", exact=True)).to_have_count(0)
    expect(page.locator(".recipe-reasons, .reason-summary")).to_have_count(0)
    top(page)
    capture(page, f"main-conversation-{suffix}.png", f"direct-results-{suffix}.png")
    page.locator(".result-intro").scroll_into_view_if_needed()
    capture(page, f"features-results-{suffix}.png")
    page.locator(".result-intro").evaluate("e=>e.scrollIntoView({block:'start'})")
    capture(page, f"results-{suffix}.png", f"recommendation-results-{suffix}.png")
    steps = page.locator(".recipe-full .steps-list")
    expect(steps.locator("li")).not_to_have_count(0)
    steps.scroll_into_view_if_needed()
    capture(page, f"cooking-steps-{suffix}.png")
    page.locator(".st-key-result_actions").scroll_into_view_if_needed()
    capture(page, f"results-bottom-actions-{suffix}.png")
    page.locator(".st-key-detail_recipe_2").get_by_role("button").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("Detail penelitian", exact=True)).to_have_count(0)
    capture(page, f"recipe-detail-{suffix}.png")
    dialog.get_by_role("button", name="Kembali ke rekomendasi", exact=True).click()
    settle(page)

    top(page)
    menu = open_menu(page, "artifact-other")
    capture(page, f"history-menu-{suffix}.png")
    menu.get_by_role("button", name="Ubah nama", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).fill("Sarapan favorit")
    capture(page, f"history-rename-{suffix}.png")
    dialog.get_by_role("textbox", name="Judul percakapan", exact=True).press("Enter")
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("button", name="Sarapan favorit", exact=True)).to_be_visible()
    for index in range(16):
        chat_id = f"artifact-overflow-{index}"
        store.save("local", chat_id, state)
        store.rename("local", chat_id, f"Ide masak {index + 1}: nasi, telur, bawang putih, kecap, garam, dan lada")
    page.reload()
    page.locator(".recipe-full").wait_for()
    expand = page.get_by_test_id("stExpandSidebarButton")
    if expand.count() and expand.is_visible():
        expand.click()
    settle(page)
    content = page.get_by_test_id("stSidebarContent")
    assert content.evaluate("e=>getComputedStyle(e).overflowX === 'hidden'")
    capture(page, f"history-no-horizontal-scroll-{suffix}.png")
    for index in range(16):
        store.delete("local", f"artifact-overflow-{index}")

    filtered = {**result, "excluded_ingredients": ["udang"]}
    store.save("local", "artifact-filtered", {**state, "excluded_ingredients": ["udang"], "latest_result": filtered})
    page.goto(f"{URL}/?chat=artifact-filtered")
    page.locator(".recipe-full").wait_for()
    settle(page)
    collapse = page.get_by_test_id("stSidebarCollapseButton").get_by_role("button")
    if suffix == "mobile" and collapse.count() and collapse.is_visible():
        collapse.click()
        settle(page)
    top(page)
    capture(page, f"filtered-results-{suffix}.png")

    page.get_by_role("button", name="Cari resep baru", exact=True).click()
    composer = page.get_by_test_id("stChatInputTextArea")
    composer.fill("aku punya nasi, blueband, telur, garam, dan lada")
    composer.press("Enter")
    expect(composer).to_be_disabled()
    page.locator(".activity").first.wait_for()
    capture(page, f"direct-loading-{suffix}.png", f"loading-disabled-{suffix}.png",
            *(["search-loading.png"] if suffix == "desktop" else []))
    page.get_by_role("button", name="Tidak ada, lanjut saja", exact=True).wait_for(timeout=25000)
    settle(page)
    top(page)
    capture(page, f"clarification-question-{suffix}.png")
    composer.fill("adanya kaldu jamur")
    composer.press("Enter")
    page.locator(".recipe-full").wait_for(timeout=25000)
    settle(page)
    assert "kaldu jamur" in page.locator(".pantry-summary").inner_text()
    top(page)
    capture(page, f"clarification-variant-{suffix}.png")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
    print(f"{suffix}: current screenshots refreshed; research panel hidden in main recipe and dialog", flush=True)


def main():
    started_at = datetime.now(timezone.utc)
    store = ChatHistoryStore(DATABASE)
    result = example_result()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for suffix, viewport in [("desktop", {"width": 1440, "height": 1100}),
                                 ("mobile", {"width": 390, "height": 844})]:
            for item in store.list("local"):
                store.delete("local", item["id"])
            page = browser.new_page(viewport=viewport, is_mobile=suffix == "mobile",
                                    has_touch=suffix == "mobile", reduced_motion="reduce")
            exercise(page, suffix, store, result)
            page.close()
        browser.close()
    screenshots = []
    for path in sorted(OUTPUT.glob("*.png")):
        if path.stat().st_mtime < started_at.timestamp() - 1:
            raise RuntimeError(f"Screenshot belum diperbarui: {path.name}")
        data = path.read_bytes()
        width, height = struct.unpack(">II", data[16:24])
        screenshots.append({"file": path.name, "width": width, "height": height,
                            "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"generated_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                "recipe_source": "data/corpus/resep_5000_clean_SAFE.csv",
                "preview_database": DATABASE.name, "screenshots": screenshots}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {len(screenshots)} screenshots and manifest.json", flush=True)


if __name__ == "__main__":
    main()
