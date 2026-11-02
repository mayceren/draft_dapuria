import json
import sqlite3

import pytest

from dapuria.chat_history import ChatHistoryStore


def snapshot():
    result = {'status': 'ok', 'user_ingredients': ['telur'], 'results': [{
        'id': 'r1', 'title': 'Telur dadar', 'ingredient_names': ['telur', 'garam'],
        'matched_recipe_items': ['telur'], 'missing_items': ['garam'],
        'steps_text': '1. Kocok telur.\n2. Masak sampai matang.', 'final_score': 0.8,
    }]}
    return {
        'messages': [{'role': 'user', 'content': 'aku punya telur'},
                     {'role': 'assistant', 'content': 'Ada garam?'}],
        'phase': 'await_confirmation',
        'pending': {'candidate_staples': ['garam'], 'original_query': 'aku punya telur',
                    'initial_result': result, 'additional_ingredients': ['lada']},
        'latest_result': None,
        'inventory': ['telur'],
        'excluded_ingredients': [],
    }


def test_restart_restores_pending_inventory_and_original_recipe(tmp_path):
    path = tmp_path / 'nested' / 'history.sqlite3'
    original = snapshot()
    ChatHistoryStore(path).save('local', 'chat-1', {**original, 'widget_secret': 'ignore me'})
    reopened = ChatHistoryStore(path)
    assert reopened.load('local', 'chat-1') == original
    assert reopened.list('local')[0]['title'] == 'aku punya telur'


def test_updates_do_not_duplicate_chat_or_overwrite_custom_title(tmp_path):
    store = ChatHistoryStore(tmp_path / 'history.sqlite3')
    original = snapshot()
    store.save('local', 'chat-1', original)
    created_at = store.list('local')[0]['created_at']
    store.rename('local', 'chat-1', '  Menu  makan malam  ')
    original['messages'].append({'role': 'user', 'content': 'iya'})
    store.save('local', 'chat-1', original)
    assert len(store.list('local')) == 1
    assert store.list('local')[0]['created_at'] == created_at
    assert store.list('local')[0]['title'] == 'Menu makan malam'
    assert store.load('local', 'chat-1') == original
    assert store.list('local', 'MAKAN')[0]['id'] == 'chat-1'
    assert store.list('local', '%') == []
    with pytest.raises(ValueError):
        store.rename('local', 'chat-1', '   ')


def test_owner_scoping_and_single_chat_delete(tmp_path):
    store = ChatHistoryStore(tmp_path / 'history.sqlite3')
    for owner, chat in [('one', 'chat-1'), ('two', 'chat-1'), ('one', 'chat-2')]:
        store.save(owner, chat, snapshot())
    store.rename('unknown', 'chat-1', 'Wrong owner')
    store.delete('one', 'chat-1')
    assert store.load('one', 'chat-1') is None
    assert store.load('two', 'chat-1') == snapshot()
    assert store.load('one', 'chat-2') == snapshot()
    assert store.load("one' OR 1=1 --", 'chat-1') is None
    assert store.list('unknown') == []


def test_empty_or_unserializable_state_does_not_overwrite_saved_chat(tmp_path):
    store = ChatHistoryStore(tmp_path / 'history.sqlite3')
    store.save('local', 'empty', {'messages': []})
    assert store.list('local') == []
    original = snapshot()
    store.save('local', 'chat-1', original)
    invalid = {**original, 'latest_result': {'score': float('nan')}}
    with pytest.raises(ValueError):
        store.save('local', 'chat-1', invalid)
    assert store.load('local', 'chat-1') == original


def test_invalid_saved_state_reports_error_without_removing_other_chats(tmp_path):
    path = tmp_path / 'history.sqlite3'
    store = ChatHistoryStore(path)
    store.save('local', 'bad', snapshot())
    store.save('local', 'good', snapshot())
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE conversations SET snapshot = '[]' WHERE id = 'bad'")
    with pytest.raises(ValueError):
        store.load('local', 'bad')
    assert store.load('local', 'good') == snapshot()


def test_old_history_without_inventory_remains_readable(tmp_path):
    path = tmp_path / 'history.sqlite3'
    store = ChatHistoryStore(path)
    original = snapshot()
    store.save('local', 'old', original)
    del original['inventory']
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE conversations SET snapshot = ? WHERE id = ?',
                           (json.dumps(original), 'old'))
    restored = store.load('local', 'old')
    assert restored['inventory'] == ['telur']
    assert restored['pending'] == original['pending']


def test_legacy_database_gets_pin_column_without_changing_chats(tmp_path):
    path = tmp_path / 'old.sqlite3'
    original = snapshot()
    with sqlite3.connect(path) as connection:
        connection.execute('''CREATE TABLE conversations (
            owner_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, snapshot TEXT NOT NULL,
            PRIMARY KEY (owner_id, id))''')
        connection.execute('INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?)',
                           ('local', 'old', 'Judul lama', '2026-01-01', '2026-01-01', json.dumps(original)))
    store = ChatHistoryStore(path)
    assert store.load('local', 'old') == original
    assert store.list('local')[0]['pinned'] is False
    store.set_pinned('local', 'old', True)
    reopened = ChatHistoryStore(path)
    assert reopened.list('local')[0]['pinned'] is True
    assert reopened.list('local')[0]['title'] == 'Judul lama'
    assert reopened.load('local', 'old') == original


def test_pinned_chats_sort_first_and_keep_pin_after_saving_or_renaming(tmp_path):
    store = ChatHistoryStore(tmp_path / 'chats.sqlite3')
    store.save('local', 'old', snapshot())
    store.save('local', 'new', snapshot())
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE conversations SET updated_at = '2026-01-01' WHERE id = 'old'")
        connection.execute("UPDATE conversations SET updated_at = '2026-02-01' WHERE id = 'new'")
    store.set_pinned('local', 'old', True)
    assert [row['id'] for row in store.list('local')] == ['old', 'new']
    assert store.list('local')[0]['updated_at'] == '2026-01-01'
    store.rename('local', 'old', 'Menu favorit')
    store.save('local', 'old', snapshot())
    assert store.list('local')[0]['pinned'] is True
    assert store.list('local', 'FAVORIT')[0]['title'] == 'Menu favorit'
    store.set_pinned('local', 'old', False)
    assert all(not row['pinned'] for row in store.list('local'))


def test_pin_operations_are_scoped_to_owner_and_deleted_chat_stays_deleted(tmp_path):
    store = ChatHistoryStore(tmp_path / 'chats.sqlite3')
    for owner in ['one', 'two']:
        store.save(owner, 'same-id', snapshot())
    store.set_pinned('one', 'same-id', True)
    store.set_pinned('unknown', 'same-id', True)
    assert store.list('one')[0]['pinned'] is True
    assert store.list('two')[0]['pinned'] is False
    store.delete('one', 'same-id')
    store.set_pinned('one', 'same-id', False)
    assert store.list('one') == []
    assert store.load('two', 'same-id') == snapshot()
