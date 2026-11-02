"""UI flow regression tests; retrieval is stubbed to avoid model downloads."""
from pathlib import Path
from typing import ClassVar

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

import dapuria
from dapuria.llama_service import LlamaService


def start_search(app, text):
    app.chat_input[0].set_value(text).run()
    assert not app.exception
    assert not app.exception


class FakeRecipeService:
    calls: ClassVar[list[str]] = []

    def __init__(self, settings):
        pass

    def handle_user_input(self, query):
        self.calls.append(query)
        return {'status': 'ok', 'user_ingredients': ['telur'], 'results': [{
            'title': 'Telur dadar', 'matched_recipe_items': ['telur'],
            'missing_items': ['garam'], 'final_score': 0.8,
            'retrieval_source': 'semantic', 'sbert_score': 0.8,
            'sbert_score_norm': 1.0, 'coverage_recipe': 0.5,
            'coverage_user': 1.0, 'ingredient_efficiency': 0.66,
        }]}

    def clarification_candidates(self, result):
        return ['garam']

    def build_grounded_payload(self, result):
        return {'status': 'ok', 'recipes': [{'title': 'Telur dadar'}]}


@pytest.mark.parametrize('answer,expected_calls', [
    ('Tidak ada, lanjut saja', ['telur']),
    ('Ada, tambahkan', ['telur', 'telur, garam']),
])
def test_quick_reply_and_fresh_query(monkeypatch, answer, expected_calls):
    import streamlit as st
    st.cache_resource.clear()
    FakeRecipeService.calls = []
    monkeypatch.setattr(dapuria, 'RecipeService', FakeRecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
    app.run()
    assert not app.exception
    start_search(app, 'telur')
    assert not app.exception
    assert app.session_state.phase == 'await_confirmation'
    next(b for b in app.button if b.label == answer).click().run()
    assert not app.exception
    assert FakeRecipeService.calls == expected_calls
    assert app.session_state.phase == 'await_query'
    assert any('Yuk, masak yang ini.' in x.value for x in app.markdown)
    app.button(key='continue_chat').click().run()
    start_search(app, 'mulai dari awal, tahu')
    assert not app.exception
    assert app.session_state.latest_result is None
    assert app.session_state.phase == 'await_confirmation'
    assert not any('class="recipe-full"' in x.value for x in app.markdown)
    st.cache_resource.clear()


def test_main_recipe_and_alternative_dialog(monkeypatch):
    import streamlit as st
    st.cache_resource.clear()
    class FiveRecipes(FakeRecipeService):
        def handle_user_input(self, query):
            result = super().handle_user_input(query)
            base = result['results'][0]
            result['results'] = [dict(base, title=f'Resep pilihan {i}',
                ingredient_names=['telur', 'garam'], steps_text=f'Langkah resep {i}.') for i in range(1, 6)]
            return result
    monkeypatch.setattr(dapuria, 'RecipeService', FiveRecipes)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    next(b for b in app.button if b.label == 'telur, bawang putih, tomat').click().run()
    next(b for b in app.button if b.label == 'Tidak ada, lanjut saja').click().run()
    assert not app.exception
    html = '\n'.join(x.value for x in app.markdown)
    assert 'Langkah resep 1.' in html
    assert 'Langkah resep 2.' not in html
    assert 'Resep lainnya' in html
    assert len([b for b in app.button if b.label == 'Lihat detail']) == 4
    app.button(key='detail_recipe_2').click().run()
    assert not app.exception
    assert any('Langkah resep 2.' in x.value for x in app.markdown)
    app.button(key='close_recipe').click().run()
    assert not app.exception
    assert app.session_state.phase == 'await_query'
    assert not any('Langkah resep 2.' in x.value for x in app.markdown)
    next(b for b in app.button if b.label == 'Mulai percakapan baru').click().run()
    assert app.session_state.messages == []
    assert app.session_state.latest_result is None
    st.cache_resource.clear()


@pytest.mark.parametrize('reply,extras', [
    ('garam apa?', []), ('mungkin ada', []), ('aku punya tahu juga', ['tahu'])
])
def test_unclear_confirmation_stays_pending_then_accepts_answer(monkeypatch, reply, extras):
    import streamlit as st
    st.cache_resource.clear()
    FakeRecipeService.calls = []
    monkeypatch.setattr(dapuria, 'RecipeService', FakeRecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'telur')
    pending = app.session_state.pending.copy()
    app.chat_input[0].set_value(reply).run()
    assert not app.exception
    assert app.session_state.phase == 'await_confirmation'
    assert app.session_state.pending == {**pending, 'additional_ingredients': extras, 'retained_ingredients': ['telur']}
    assert app.session_state.latest_result is None
    assert FakeRecipeService.calls == ['telur']
    assert any('belum bisa memastikan' in m['content'] for m in app.session_state.messages)
    app.chat_input[0].set_value('garamnya ada').run()
    assert not app.exception
    assert app.session_state.phase == 'await_query'
    assert app.session_state.pending is None
    assert FakeRecipeService.calls == ['telur', ', '.join(['telur', 'garam'] + extras)]
    assert app.session_state.latest_result['status'] == 'ok'
    st.cache_resource.clear()


def test_conversational_input_reaches_retrieval_as_canonical_inventory(monkeypatch):
    import streamlit as st

    from dapuria import recipe_service as recipe_module
    from dapuria.recipe_service import RecipeService

    calls = []

    class Retriever:
        def __init__(self, settings):
            pass

        def retrieve(self, query, ingredients):
            calls.append((query, ingredients))
            return [{'id': 'r1', 'title': 'Nasi telur',
                     'ingredient_names': ['nasi', 'telur'], 'sbert_score': 0.8,
                     'steps_text': 'Masak nasi dan telur.'}]

    st.cache_resource.clear()
    monkeypatch.setattr(recipe_module, 'HybridRetriever', Retriever)
    monkeypatch.setattr(dapuria, 'RecipeService', RecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'aku punya nasi sama telur')
    assert not app.exception
    assert calls == [('nasi, telur', ['nasi', 'telur'])]
    assert app.session_state.latest_result['user_ingredients'] == ['nasi', 'telur']
    assert any('Bahan yang terbaca: nasi, telur' in item.value for item in app.caption)
    st.cache_resource.clear()


@pytest.mark.parametrize('reply', [
    'adanya kaldu jamur', 'kaldu jamur aja yang ada',
    'kaldu ayam nggak ada, adanya kaldu jamur',
])
def test_specific_clarification_variant_reaches_search_and_history_without_generic_stock(monkeypatch, reply):
    import os

    import streamlit as st

    from dapuria import recipe_service as recipe_module
    from dapuria.chat_history import ChatHistoryStore
    from dapuria.recipe_service import RecipeService

    calls = []
    pantry = ['nasi', 'blueband', 'telur', 'garam', 'lada']

    class Retriever:
        def __init__(self, settings):
            pass

        def retrieve(self, query, ingredients):
            calls.append((query, ingredients))
            return [{'id': stock, 'title': f'Nasi telur {stock}',
                     'ingredient_names': pantry + [stock], 'sbert_score': score,
                     'steps_text': 'Langkah memasak dari data resep.'}
                    for stock, score in [('kaldu jamur', 0.8), ('kaldu ayam', 0.7)]]

    st.cache_resource.clear()
    monkeypatch.setattr(recipe_module, 'HybridRetriever', Retriever)
    monkeypatch.setattr(dapuria, 'RecipeService', RecipeService)
    monkeypatch.setattr(RecipeService, 'clarification_candidates', lambda self, result: ['kaldu'])
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'aku punya nasi, blueband, telur, garam, dan lada')
    question = app.session_state.messages[-1]['content']
    assert question.count('?') == 1 and question.count('kaldu') == 1
    assert 'blueband' not in question
    chat_id = app.session_state.conversation_id
    # Existing pending questions can also be resumed in a fresh browser session.
    reopened = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
    reopened.query_params['chat'] = chat_id
    reopened.run()
    assert len(calls) == 1
    reopened.chat_input[0].set_value(reply).run()
    assert not reopened.exception
    expected = pantry + ['kaldu jamur']
    assert calls[-1] == (', '.join(expected), expected)
    assert reopened.session_state.inventory == expected
    assert reopened.session_state.pending is None
    by_id = {recipe['id']: recipe for recipe in reopened.session_state.latest_result['results']}
    assert 'kaldu jamur' in by_id['kaldu jamur']['matched_recipe_items']
    assert 'kaldu ayam' in by_id['kaldu ayam']['missing_items']
    assert 'kaldu ayam' not in by_id['kaldu ayam']['matched_recipe_items']
    saved = ChatHistoryStore(Path(os.environ['DAPURIA_HISTORY_PATH'])).load('local', chat_id)
    assert saved['inventory'] == expected
    assert saved['latest_result']['user_ingredients'] == expected
    st.cache_resource.clear()


@pytest.mark.parametrize('query,reply,expected', [
    ('aku punya nasi sama telur. Bisa masak apa?',
     'ada, aku juga ada garam sama lada',
     ['nasi', 'telur', 'bawang putih', 'garam', 'lada']),
    ('nasi, telur', 'tidak ada bawang putih, tapi aku punya garam sama lada',
     ['nasi', 'telur', 'garam', 'lada']),
    ('nasi, telur, garam', 'ada, aku juga ada garam sama lada',
     ['nasi', 'telur', 'garam', 'bawang putih', 'lada']),
])
def test_volunteered_ingredients_reach_reranking_and_visible_inventory(monkeypatch, query, reply, expected):
    import streamlit as st

    from dapuria import recipe_service as recipe_module
    from dapuria.preprocessing import parse_user_ingredients
    from dapuria.recipe_service import RecipeService

    calls = []

    class Retriever:
        def __init__(self, settings):
            pass

        def retrieve(self, text, ingredients):
            calls.append((text, ingredients))
            return [{'id': 'r1', 'title': 'Nasi telur',
                     'ingredient_names': ['nasi', 'telur', 'bawang putih', 'garam', 'lada'],
                     'sbert_score': 0.8, 'steps_text': 'Masak nasi dan telur.'}]

    st.cache_resource.clear()
    monkeypatch.setattr(recipe_module, 'HybridRetriever', Retriever)
    monkeypatch.setattr(RecipeService, 'clarification_candidates', lambda self, result: ['bawang putih'])
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, query)
    assert not app.exception
    assert app.session_state.phase == 'await_confirmation'
    app.chat_input[0].set_value(reply).run()
    assert not app.exception
    assert app.session_state.phase == 'await_query'
    assert calls == [
        (', '.join(parse_user_ingredients(query)), parse_user_ingredients(query)),
        (', '.join(expected), expected),
    ]
    result = app.session_state.latest_result
    assert result['user_ingredients'] == expected
    assert result['results'][0]['matched_user_items'] == sorted(expected)
    assert any('Bahan yang terbaca: ' + ', '.join(expected) in item.value for item in app.caption)
    assert any('lada' in message['content'] for message in app.session_state.messages
               if message['role'] == 'assistant')
    st.cache_resource.clear()



def test_history_can_resume_pending_conversation_after_browser_restart(monkeypatch):
    import os

    import streamlit as st

    from dapuria.chat_history import ChatHistoryStore

    st.cache_resource.clear()
    FakeRecipeService.calls = []
    monkeypatch.setattr(dapuria, 'RecipeService', FakeRecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    path = str(Path(__file__).resolve().parents[1] / 'app.py')
    app = AppTest.from_file(path).run()
    start_search(app, 'telur')
    app.chat_input[0].set_value('aku punya lada juga').run()
    chat_id = app.session_state.conversation_id
    next(b for b in app.button if b.label == 'Mulai percakapan baru').click().run()
    assert app.session_state.messages == []
    assert any(b.key == f'history_{chat_id}' for b in app.button)
    app.button(key=f'history_{chat_id}').click().run()
    assert app.session_state.phase == 'await_confirmation'
    assert app.session_state.pending['additional_ingredients'] == ['lada']
    # A fresh Streamlit session reloads the persisted snapshot, not session memory.
    st.cache_resource.clear()
    reopened = AppTest.from_file(path)
    reopened.query_params['chat'] = chat_id
    reopened.run()
    assert not reopened.exception
    assert reopened.session_state.phase == 'await_confirmation'
    assert FakeRecipeService.calls == ['telur']
    next(b for b in reopened.button if b.label == 'Ada, tambahkan').click().run()
    assert not reopened.exception
    assert FakeRecipeService.calls == ['telur', 'telur, garam, lada']
    saved = ChatHistoryStore(Path(os.environ['DAPURIA_HISTORY_PATH'])).load('local', chat_id)
    assert saved['phase'] == 'await_query'
    assert saved['pending'] is None
    assert saved['messages'][-1]['result'] == saved['latest_result']
    st.cache_resource.clear()


def test_history_rename_search_and_delete(monkeypatch):
    import os

    import streamlit as st

    from dapuria.chat_history import ChatHistoryStore

    st.cache_resource.clear()
    monkeypatch.setattr(dapuria, 'RecipeService', FakeRecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'telur')
    chat_id = app.session_state.conversation_id
    assert not any(field.key == f'chat_title_{chat_id}' for field in app.text_input)
    app.button(key=f'open_rename_{chat_id}').click().run()
    app.text_input(key=f'chat_title_{chat_id}').set_value('   ')
    app.button(key=f'rename_chat_{chat_id}').click().run()
    assert app.error
    assert app.session_state.renaming_chat_id == chat_id
    app.button(key=f'cancel_rename_{chat_id}').click().run()
    assert app.session_state.renaming_chat_id is None
    store = ChatHistoryStore(Path(os.environ['DAPURIA_HISTORY_PATH']))
    assert store.list('local')[0]['title'] == 'telur'
    assert not any(field.key == f'chat_title_{chat_id}' for field in app.text_input)
    app.button(key=f'open_rename_{chat_id}').click().run()
    assert app.text_input(key=f'chat_title_{chat_id}').value == 'telur'
    app.text_input(key=f'chat_title_{chat_id}').set_value('Menu sore')
    next(b for b in app.button if b.label == 'Simpan judul').click().run()
    assert not app.exception
    app.text_input(key='history_search').set_value('MENU SORE').run()
    assert app.button(key=f'history_{chat_id}').label == 'Menu sore'
    app.button(key=f'delete_chat_{chat_id}').click().run()
    assert not app.exception
    assert app.session_state.messages == []
    assert ChatHistoryStore(Path(os.environ['DAPURIA_HISTORY_PATH'])).load('local', chat_id) is None
    assert not any(b.key == f'history_{chat_id}' for b in app.button)
    st.cache_resource.clear()


def test_history_row_actions_manage_inactive_chats_without_changing_active_context(monkeypatch):
    import os

    import streamlit as st

    from dapuria.chat_history import ChatHistoryStore

    st.cache_resource.clear()
    FakeRecipeService.calls = []
    monkeypatch.setattr(dapuria, 'RecipeService', FakeRecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'telur')
    first = app.session_state.conversation_id
    next(b for b in app.button if b.label == 'Mulai percakapan baru').click().run()
    start_search(app, 'tahu')
    second = app.session_state.conversation_id
    active_pending = app.session_state.pending.copy()
    store = ChatHistoryStore(Path(os.environ['DAPURIA_HISTORY_PATH']))
    app.button(key=f'pin_chat_{first}').click().run()
    assert not app.exception
    assert store.list('local')[0]['id'] == first
    assert store.list('local')[0]['pinned'] is True
    app.button(key=f'open_rename_{first}').click().run()
    app.text_input(key=f'chat_title_{first}').set_value('Menu sarapan')
    app.button(key=f'rename_chat_{first}').click().run()
    assert store.list('local')[0]['title'] == 'Menu sarapan'
    assert store.list('local')[0]['pinned'] is True
    assert app.session_state.conversation_id == second
    assert app.session_state.pending == active_pending
    app.button(key=f'pin_chat_{first}').click().run()
    assert all(not item['pinned'] for item in store.list('local'))
    app.button(key=f'pin_chat_{first}').click().run()
    reopened = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
    reopened.query_params['chat'] = second
    reopened.run()
    assert not reopened.exception
    assert reopened.button(key=f'pin_chat_{first}').label == 'Lepas pin'
    assert reopened.session_state.pending == active_pending
    reopened.text_input(key='history_search').set_value('SARAPAN').run()
    reopened.button(key=f'delete_chat_{first}').click().run()
    assert store.load('local', first) is None
    assert reopened.session_state.conversation_id == second
    assert reopened.session_state.pending == active_pending
    reopened.text_input(key='history_search').set_value('').run()
    reopened.button(key=f'delete_chat_{second}').click().run()
    assert reopened.session_state.messages == []
    assert store.list('local') == []
    assert FakeRecipeService.calls == ['telur', 'tahu']
    st.cache_resource.clear()


def test_welcome_does_not_load_models_and_service_failure_preserves_chat(monkeypatch):
    import os

    import streamlit as st

    from dapuria.chat_history import ChatHistoryStore

    calls = []
    class UnavailableService:
        def __init__(self, settings):
            calls.append('init')
            raise RuntimeError('Model unavailable')

    st.cache_resource.clear()
    monkeypatch.setattr(dapuria, 'RecipeService', UnavailableService)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    assert not app.exception
    assert calls == []
    start_search(app, 'telur')
    assert not app.exception
    assert calls == ['init']
    assert 'belum siap' in app.session_state.messages[-1]['content']
    saved = ChatHistoryStore(Path(os.environ['DAPURIA_HISTORY_PATH'])).load('local', app.session_state.conversation_id)
    assert saved['messages'][-1]['role'] == 'assistant'
    assert saved['latest_result'] is None
    # Reading the chat also works while model initialization is unavailable.
    reopened = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
    reopened.query_params['chat'] = app.session_state.conversation_id
    reopened.run()
    assert not reopened.exception
    assert reopened.session_state.messages == saved['messages']
    assert calls == ['init']
    st.cache_resource.clear()


def test_history_storage_failure_does_not_block_chat(monkeypatch, tmp_path):
    import streamlit as st

    blocked = tmp_path / 'not_a_directory'
    blocked.write_text('file', encoding='utf-8')
    monkeypatch.setenv('DAPURIA_HISTORY_PATH', str(blocked / 'history.sqlite3'))
    monkeypatch.setattr(dapuria, 'RecipeService', FakeRecipeService)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    st.cache_resource.clear()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'telur')
    assert not app.exception
    assert app.session_state.phase == 'await_confirmation'
    assert any('Penyimpanan riwayat' in warning.value for warning in app.warning)
    st.cache_resource.clear()


def test_previous_recommendations_remain_available_without_retrieval(monkeypatch):
    import streamlit as st

    class QueryRecipes(FakeRecipeService):
        calls: ClassVar[list[str]] = []

        def handle_user_input(self, query):
            result = super().handle_user_input(query)
            result['user_ingredients'] = [query]
            result['results'][0]['title'] = f'Resep {query}'
            return result

        def clarification_candidates(self, result):
            return []

    st.cache_resource.clear()
    monkeypatch.setattr(dapuria, 'RecipeService', QueryRecipes)
    monkeypatch.setattr(LlamaService, 'available', lambda self: False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    start_search(app, 'telur')
    app.button(key='continue_chat').click().run()
    start_search(app, 'mulai dari awal, tahu')
    assert not app.exception
    assert app.session_state.latest_result['results'][0]['title'] == 'Resep tahu'
    app.button(key='past_result_1').click().run()
    assert not app.exception
    assert app.session_state.selected_result['results'][0]['title'] == 'Resep telur'
    assert app.session_state.latest_result['results'][0]['title'] == 'Resep tahu'
    assert QueryRecipes.calls == ['telur', 'tahu']
    app.button(key='show_latest').click().run()
    assert app.session_state.selected_result is None
    assert QueryRecipes.calls == ['telur', 'tahu']
    st.cache_resource.clear()
