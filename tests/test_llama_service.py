import json

import pytest

from dapuria.llama_service import LlamaService


def _offline(service: LlamaService):
    service.available = lambda: False
    return service


def test_single_candidate_yes_confirms_only_that_candidate():
    service = _offline(LlamaService())
    assert service.parse_confirmation("ya", ["bawang merah"]) == ["bawang merah"]


def test_single_candidate_no_confirms_nothing():
    service = _offline(LlamaService())
    assert service.parse_confirmation("tidak", ["bawang merah"]) == []


def test_generic_yes_does_not_confirm_hidden_multiple_candidates():
    service = _offline(LlamaService())
    assert (
        service.parse_confirmation(
            "ya", ["bawang merah", "bawang putih", "kaldu", "garam"]
        )
        == []
    )


def test_explicit_multi_candidate_reply_only_keeps_named_items():
    service = _offline(LlamaService())
    result = service.parse_confirmation(
        "aku punya bawang merah dan garam",
        ["bawang merah", "bawang putih", "kaldu", "garam"],
    )
    assert result == ["bawang merah", "garam"]


def test_clarification_offline_preserves_context_and_optional_choice():
    service = _offline(LlamaService())
    question = service.clarification_question(['telur', 'tahu'], ['bawang merah'])
    assert 'telur' not in question and 'tahu' not in question
    assert 'bawang merah' in question
    assert 'Kalau nggak ada' in question
    assert question.count('?') == 1
    assert service.clarification_question(['telur'], []) == ''


def test_clarification_rejects_empty_or_incomplete_model_output():
    service = LlamaService()
    service.available = lambda: True
    for response in ['', 'Ada garam?', '   ']:
        service._chat = lambda *args, **kwargs: response
        question = service.clarification_question(['telur'], ['garam', 'bawang merah'])
        assert 'garam dan bawang merah' in question
        assert 'mana yang kamu punya?' in question


def test_clarification_accepts_model_response():
    service = LlamaService()
    service.available = lambda: True
    response = json.dumps({'question': 'Kamu punya garam juga?'})
    service._chat = lambda *args, **kwargs: response
    assert service.clarification_question(['telur'], ['garam']) == (
        'Kamu punya garam juga? Kalau nggak ada, kita lanjut pakai bahan yang kamu punya.'
    )


def test_clarification_falls_back_on_timeout_or_malformed_response():
    import requests
    service = LlamaService()
    service.available = lambda: True
    for error in [requests.Timeout(), KeyError('message'), ValueError('invalid JSON')]:
        def fail(*args, **kwargs):
            raise error
        service._chat = fail
        assert 'Ada garam' in service.clarification_question(['telur'], ['garam'])


def test_negative_and_uncertain_replies_never_confirm_single_candidate():
    service = LlamaService()
    service.available = lambda: True
    def unexpected(*args, **kwargs):
        raise AssertionError('Explicit negatives must not call the model')
    service._chat = unexpected
    for reply in ['garam nggak ada', 'iya tapi sudah habis', 'garam ada tapi sudah habis',
                  'nggak ada!', 'mungkin ada garam', 'belum punya garam']:
        assert service.parse_confirmation(reply, ['garam']) == []


def test_other_ingredient_is_not_a_generic_yes():
    service = _offline(LlamaService())
    assert service.parse_confirmation('ada telur saja', ['garam']) == []
    assert service.parse_confirmation('iya!', ['garam']) == ['garam']
    assert service.parse_confirmation('ada kok', ['garam']) == ['garam']


def test_negation_stays_with_its_clause():
    service = _offline(LlamaService())
    assert service.parse_confirmation(
        'bawang merah nggak ada, garam ada', ['bawang merah', 'garam']
    ) == ['garam']


def test_confirmation_model_schema_and_exact_allowlist():
    service = LlamaService()
    service.available = lambda: True
    for raw in ['null', '[]', '{"confirmed_ingredients": null}',
                '{"confirmed_ingredients": "garam"}', '{"confirmed_ingredients": [42]}',
                '{"confirmed_ingredients": ["garam dan gula"]}', 'invalid']:
        service._chat = lambda *args, **kwargs: raw
        assert service.parse_confirmation('yang tadi itu', ['garam']) == []
    service._chat = lambda *args, **kwargs: '{"confirmed_ingredients": ["garam", "garam", "telur"]}'
    assert service.parse_confirmation('yang tadi itu', ['garam']) == ['garam']


def test_generic_multi_yes_never_delegated_to_model():
    service = LlamaService()
    service.available = lambda: True
    service._chat = lambda *args, **kwargs: '{"confirmed_ingredients": ["garam", "gula"]}'
    assert service.parse_confirmation('iya!', ['garam', 'gula']) == []


def test_availability_requires_configured_model(monkeypatch):
    from types import SimpleNamespace

    import requests
    service = LlamaService()
    for payload, expected in [
        ({'models': [{'name': 'llama3:latest'}]}, True),
        ({'models': [{'name': 'other:latest'}]}, False),
        ({'models': []}, False), ({'models': None}, False), ([], False),
    ]:
        monkeypatch.setattr(requests, 'get', lambda *a, **k: SimpleNamespace(
            ok=True, json=lambda: payload
        ))
        assert service.available() is expected


def test_summary_uses_fallback_for_empty_or_malformed_response():
    service = LlamaService()
    service.available = lambda: True
    payload = {'status': 'ok', 'recipes': [{'title': 'Telur dadar'}]}
    for response in ['', '   ', None]:
        service._chat = lambda *args, **kwargs: response
        assert 'Telur dadar' in service.grounded_summary(payload)
    def malformed(*args, **kwargs):
        raise KeyError('message')
    service._chat = malformed
    assert 'Telur dadar' in service.grounded_summary(payload)


@pytest.mark.parametrize('reply,status,ingredients', [
    ('garam apa?', 'unclear', []),
    ('garam apa', 'unclear', []),
    ('apakah ada garam', 'unclear', []),
    ('mungkin ada garam', 'unclear', []),
    ('aku mau beli garam', 'unclear', []),
    ('aku punya tahu juga', 'unclear', []),
    ('garamnya ada', 'confirmed', ['garam']),
    ('aku punya garamnya', 'confirmed', ['garam']),
    ('garam', 'confirmed', ['garam']),
    ('garamnya nggak ada', 'declined', []),
    ('iya tapi sudah habis', 'declined', []),
    ('tidak ada', 'declined', []),
    ('lanjut', 'declined', []),
])
def test_confirmation_distinguishes_unclear_from_declined(reply, status, ingredients):
    service = _offline(LlamaService())
    result = service.interpret_confirmation(reply, ['garam'])
    assert result.status == status
    assert result.ingredients == ingredients


def test_question_never_delegates_to_model():
    service = LlamaService()
    def unexpected():
        raise AssertionError('A question must stay pending without model inference')
    service.available = unexpected
    assert service.interpret_confirmation('garam apa?', ['garam']).status == 'unclear'


@pytest.mark.parametrize('response', [
    'Resep terbaik: Pizza, tambahkan keju.',
    'null', '[]',
    '{"opening": "Tambahkan keju", "recipe_ids": ["r1", "r2"]}',
    '{"opening": "Ini resep yang aku temukan", "recipe_ids": ["pizza"]}',
    '{"opening": "Ini resep yang aku temukan", "recipe_ids": ["r2", "r1"]}',
    '{"opening": "Ini resep yang aku temukan", "recipe_ids": ["r1"]}',
    '{"opening": "Ini resep yang aku temukan", "recipe_ids": ["r1", "r2"], "steps": "Tambahkan keju"}',
])
def test_summary_rejects_invented_facts_and_changed_ranking(response):
    service = LlamaService()
    service.available = lambda: True
    service._chat = lambda *args, **kwargs: response
    payload = {'status': 'ok', 'recipes': [
        {'recipe_id': 'r1', 'title': 'Telur dadar'},
        {'recipe_id': 'r2', 'title': 'Tahu goreng'},
    ]}
    summary = service.grounded_summary(payload)
    assert summary.startswith('Ini resep yang aku temukan: Telur dadar, Tahu goreng.')
    assert 'Pizza' not in summary and 'keju' not in summary


def test_summary_accepts_valid_json_and_renders_source_titles():
    service = LlamaService()
    service.available = lambda: True
    def chat(messages, **kwargs):
        assert kwargs['json_mode'] is True
        data = json.loads(messages[-1]['content'])
        assert data['recipes'] == [{'recipe_id': 'r1', 'title': 'Telur dadar'}]
        return json.dumps({
            'opening': 'Ini ide masakan yang bisa kamu cek', 'recipe_ids': ['r1']
        })
    service._chat = chat
    summary = service.grounded_summary({'status': 'ok', 'recipes': [
        {'recipe_id': 'r1', 'title': 'Telur dadar', 'steps': 'Langkah asli'}
    ]})
    assert summary.startswith('Ini ide masakan yang bisa kamu cek: Telur dadar.')


@pytest.mark.parametrize('reply,status,confirmed,additional', [
    ('ada, aku juga ada garam sama lada', 'confirmed', ['bawang putih'], ['garam', 'lada']),
    ('iya, aku punya garam dan lada', 'confirmed', ['bawang putih'], ['garam', 'lada']),
    ('ada. Aku punya garam sama lada.', 'confirmed', ['bawang putih'], ['garam', 'lada']),
    ('tidak ada bawang putih, tapi aku punya garam sama lada', 'declined', [], ['garam', 'lada']),
    ('tidak ada, aku punya lada', 'declined', [], ['lada']),
    ('ada, tapi lada habis', 'confirmed', ['bawang putih'], []),
    ('ada telur saja', 'unclear', [], ['telur']),
    ('bawang putih ada, aku juga ada garam', 'confirmed', ['bawang putih'], ['garam']),
    ('ada, aku punya bawang putih dan garam', 'confirmed', ['bawang putih'], ['garam']),
    ('ada, aku punya garam sama garam', 'confirmed', ['bawang putih'], ['garam']),
    ('ada, aku juga punya telor', 'confirmed', ['bawang putih'], ['telur']),
    ('ada, aku mau beli lada', 'confirmed', ['bawang putih'], []),
    ('ada, mungkin ada garam', 'confirmed', ['bawang putih'], []),
    ('ada, aku punya garam sama lada, lada nggak ada', 'confirmed', ['bawang putih'], ['garam']),
    ('bawang putih apa?', 'unclear', [], []),
    ('ada, terima kasih', 'confirmed', ['bawang putih'], []),
    ('yang tadi itu', 'unclear', [], []),
])
def test_clarification_reply_preserves_volunteered_inventory(reply, status, confirmed, additional):
    service = _offline(LlamaService())
    result = service.interpret_clarification_reply(reply, ['bawang putih'])
    assert result.confirmation.status == status
    assert result.confirmation.ingredients == confirmed
    assert result.additional_ingredients == additional


def test_model_cannot_supply_volunteered_ingredients():
    service = LlamaService()
    service.available = lambda: True
    service._chat = lambda *a, **k: json.dumps({
        'confirmed_ingredients': ['bawang putih', 'garam', 'lada'],
        'additional_ingredients': ['garam', 'lada'],
    })
    result = service.interpret_clarification_reply('yang tadi itu', ['bawang putih'])
    assert result.confirmation.ingredients == ['bawang putih']
    assert result.additional_ingredients == []


@pytest.mark.parametrize('response', [
    'Kamu punya nasi dan telur, ya. Ada kaldu? Kita butuh kaldu, apakah ada?',
    '{"question": "Ada kaldu? Ada semua bahan yang dibutuhkan?"}',
    '{"question": "Ada kaldu juga?", "extra": "Apakah punya semuanya?"}',
    '{"question": "Ada kaldu ayam juga?"}',
    'null', '[]', '{"question": null}',
])
def test_clarification_never_repeats_or_introduces_unasked_variants(response):
    service = LlamaService()
    service.available = lambda: True
    service._chat = lambda *args, **kwargs: response
    question = service.clarification_question(['nasi', 'blueband', 'telur', 'garam', 'lada'], ['kaldu'])
    assert question == 'Ada kaldu juga? Kalau nggak ada, kita lanjut pakai bahan yang kamu punya.'
    assert question.count('?') == 1 and question.count('kaldu') == 1
    assert 'blueband' not in question


@pytest.mark.parametrize('reply', [
    'adanya kaldu jamur', 'yang ada kaldu jamur', 'cuma ada kaldu jamur',
    'aku punya kaldu jamur', 'kaldu jamur', 'kaldu jamur ada',
    'kaldu jamur aja yang ada', 'ada, aku punya kaldu jamur',
    'kaldu ayam nggak ada, adanya kaldu jamur',
    'adanya kaldu jamur, tapi kaldu ayam habis',
])
def test_named_stock_variant_confirms_generic_stock_without_broadening(reply):
    service = LlamaService()
    service.available = lambda: (_ for _ in ()).throw(AssertionError('Named variants must not need a model'))
    result = service.interpret_clarification_reply(reply, ['kaldu'])
    assert result.confirmation.status == 'confirmed'
    assert result.confirmation.ingredients == ['kaldu jamur']
    assert result.additional_ingredients == []


@pytest.mark.parametrize('reply,status', [
    ('adanya kaldu jamur nggak ada', 'declined'),
    ('mungkin adanya kaldu jamur', 'unclear'),
    ('adanya kaldu jamur?', 'unclear'),
    ('aku mau beli kaldu jamur', 'unclear'),
    ('adanya kaldu jamur, kaldu jamur nggak ada', 'declined'),
])
def test_variant_questions_negations_and_plans_do_not_become_inventory(reply, status):
    service = _offline(LlamaService())
    result = service.interpret_clarification_reply(reply, ['kaldu'])
    assert result.confirmation.status == status
    assert result.confirmation.ingredients == []
    assert result.additional_ingredients == []


def test_variant_and_volunteered_ingredients_remain_separate():
    service = _offline(LlamaService())
    result = service.interpret_clarification_reply('adanya kaldu jamur, aku juga punya lada', ['kaldu'])
    assert result.confirmation.ingredients == ['kaldu jamur']
    assert result.additional_ingredients == ['lada']
    assert service.interpret_confirmation('adanya kaldu jamur', ['kaldu ayam']).status == 'unclear'
    assert service.interpret_confirmation('ada kaldu ayam', ['ayam']).status == 'unclear'
    assert service.interpret_confirmation('ada ayam', ['kaldu']).status == 'unclear'
