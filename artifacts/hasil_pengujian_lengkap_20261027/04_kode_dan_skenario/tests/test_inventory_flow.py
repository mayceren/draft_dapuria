"""Direct conversational searches, preferences, and history across UI reruns."""

import os
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import dapuria
from dapuria.chat_history import ChatHistoryStore
from dapuria.llama_service import LlamaService
from dapuria.preferences import ingredient_is_excluded
from dapuria.preprocessing import parse_user_ingredients

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(monkeypatch):
    class Recipes:
        calls = []
        busy_states = []

        def __init__(self, settings):
            pass

        def handle_user_input(self, text, excluded_ingredients=None):
            excluded = list(excluded_ingredients or [])
            self.calls.append((text, excluded))
            self.busy_states.append(st.session_state.submission is not None)
            ingredients = [name for name in parse_user_ingredients(text)
                           if not ingredient_is_excluded(name, excluded)]
            return {"status": "ok", "user_ingredients": ingredients,
                    "excluded_ingredients": excluded, "results": [{
                        "id": "r1", "title": "Menu dapurmu", "ingredient_names": ingredients,
                        "matched_recipe_items": ingredients, "missing_items": [],
                        "steps_text": "Masak sesuai langkah resep.",
                    }]}

        def clarification_candidates(self, result):
            return []

        def build_grounded_payload(self, result):
            return {"status": "ok", "recipes": result["results"]}

    st.cache_resource.clear()
    monkeypatch.setattr(dapuria, "RecipeService", Recipes)
    monkeypatch.setattr(LlamaService, "available", lambda self: False)
    yield AppTest.from_file(APP).run(), Recipes
    st.cache_resource.clear()


def send(ui, text):
    ui.chat_input[0].set_value(text).run()
    assert not ui.exception
    assert len(ui.multiselect) == 0
    assert not any(button.label in {"Koreksi bahan", "Ubah bahan", "Cari resep"}
                   for button in ui.button)


def test_input_searches_immediately_and_followups_keep_context(app):
    ui, recipes = app
    send(ui, "aku punya nasi sama telur")
    chat_id = ui.session_state.conversation_id
    assert recipes.calls == [("nasi, telur", [])]
    assert recipes.busy_states == [True]
    assert len(ui.chat_input) == 0
    ui.button(key="continue_chat").click().run()
    send(ui, "aku juga punya wortel")
    assert recipes.calls[-1] == ("nasi, telur, wortel", [])
    assert ui.session_state.conversation_id == chat_id
    ui.button(key="continue_chat").click().run()
    send(ui, "telurnya ternyata habis")
    assert recipes.calls[-1] == ("nasi, wortel", [])
    ui.button(key="fresh_search").click().run()
    assert ui.session_state.inventory == []
    assert ui.session_state.excluded_ingredients == []
    assert ui.session_state.messages == []
    assert ui.session_state.conversation_id != chat_id


def test_preferences_survive_restart_and_permission_restores_owned_food(app):
    ui, recipes = app
    send(ui, "aku punya nasi sama ayam, jangan pakai ayam")
    chat_id = ui.session_state.conversation_id
    assert ui.session_state.inventory == ["nasi", "ayam"]
    assert ui.session_state.latest_result["user_ingredients"] == ["nasi"]
    assert recipes.calls == [("nasi, ayam", ["ayam"])]
    restored = AppTest.from_file(APP)
    restored.query_params["chat"] = chat_id
    restored.run()
    assert restored.session_state.excluded_ingredients == ["ayam"]
    assert len(restored.chat_input) == 0
    assert len(recipes.calls) == 1
    restored.button(key="continue_chat").click().run()
    send(restored, "aku juga punya wortel")
    assert recipes.calls[-1] == ("nasi, ayam, wortel", ["ayam"])
    restored.button(key="continue_chat").click().run()
    send(restored, "boleh pakai ayam")
    assert restored.session_state.inventory == ["nasi", "ayam", "wortel"]
    assert restored.session_state.excluded_ingredients == []
    assert restored.session_state.latest_result["user_ingredients"] == ["nasi", "ayam", "wortel"]
    saved = ChatHistoryStore(Path(os.environ["DAPURIA_HISTORY_PATH"])).load("local", chat_id)
    assert saved["excluded_ingredients"] == []


def test_preferences_without_usable_food_do_not_load_search(app):
    ui, recipes = app
    send(ui, "jangan pakai ayam")
    assert recipes.calls == []
    assert ui.session_state.excluded_ingredients == ["ayam"]
    assert ui.session_state.inventory == []
    assert not ui.chat_input[0].disabled
    send(ui, "aku punya telur")
    assert recipes.calls == [("telur", ["ayam"])]


def test_legacy_review_resumes_without_editor_or_automatic_model_loading(app):
    ui, recipes = app
    store = ChatHistoryStore(Path(os.environ["DAPURIA_HISTORY_PATH"]))
    store.save("local", "old-review", {
        "messages": [{"role": "user", "content": "aku punya telur"}],
        "inventory": ["telur"], "phase": "review_ingredients", "pending": None,
        "latest_result": {"status": "ok", "results": []},
    })
    restored = AppTest.from_file(APP)
    restored.query_params["chat"] = "old-review"
    restored.run()
    assert not restored.exception
    assert restored.session_state.phase == "await_query"
    assert restored.session_state.latest_result is None
    assert restored.session_state.inventory == ["telur"]
    assert len(restored.multiselect) == 0
    assert recipes.calls == []
    send(restored, "cari resep")
    assert recipes.calls == [("telur", [])]


def test_unexpected_summary_failure_unlocks_chat_and_preserves_inventory(app, monkeypatch):
    ui, recipes = app

    def fail(self, payload):
        raise RuntimeError("Temporary summary failure")

    monkeypatch.setattr(LlamaService, "grounded_summary", fail)
    send(ui, "nasi, telur")
    assert recipes.calls == [("nasi, telur", [])]
    assert ui.session_state.submission is None
    assert ui.session_state.inventory == ["nasi", "telur"]
    assert ui.session_state.phase == "await_query"
    assert not ui.chat_input[0].disabled
    assert "belum berhasil" in ui.session_state.messages[-1]["content"]


def test_new_constraint_replaces_pending_question_and_searches_again(app, monkeypatch):
    ui, recipes = app
    monkeypatch.setattr(recipes, "clarification_candidates",
                        lambda self, result: [] if result["excluded_ingredients"] else ["garam"])
    send(ui, "nasi, telur")
    assert ui.session_state.phase == "await_confirmation"
    send(ui, "jangan pakai garam")
    assert recipes.calls == [("nasi, telur", []), ("nasi, telur", ["garam"])]
    assert ui.session_state.pending is None
    assert ui.session_state.latest_result["excluded_ingredients"] == ["garam"]
