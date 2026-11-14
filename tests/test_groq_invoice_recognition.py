from types import SimpleNamespace
import json
import pytest
from fastapi import HTTPException
from app.services import groq_invoice_recognition as groq
from app.services.invoice_service import InvoiceService


def test_recognition_passes_images_and_requests_json(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    requests = []
    def post(url, headers, json, timeout):
        requests.append(json)
        content = 'Счёт № 123' if len(requests) == 1 else '{"invoice_num":"123","items":[]}'
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {'choices':[{'message':{'content':content}}]})
    monkeypatch.setattr(groq.httpx, 'post', post)
    assert groq.recognize_invoice_text('invoice.png', b'example') == 'Счёт № 123'
    assert requests[0]['model'] == 'qwen/qwen3.8-27b'
    assert requests[0]['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert json.loads(groq.extract_invoice_json('Output JSON'))['invoice_num'] == '123'
    assert requests[1]['response_format'] == {'type':'json_object'}


def test_groq_errors_and_file_limits(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    with pytest.raises(HTTPException) as exc: groq.extract_invoice_json('test')
    assert exc.value.status_code == 503
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    monkeypatch.setattr(groq.httpx, 'post', lambda *args, **kwargs: SimpleNamespace(status_code=429))
    with pytest.raises(HTTPException) as exc: groq.extract_invoice_json('test')
    assert exc.value.status_code == 503
    with pytest.raises(HTTPException) as exc: list(groq._pages('invoice.txt', b'file'))
    assert exc.value.status_code == 400


def test_only_invoice_files_can_be_sent(tmp_path):
    path = tmp_path / 'other.png'; path.write_bytes(b'example')
    service = InvoiceService.__new__(InvoiceService)
    service.repo = SimpleNamespace(get_invoice_by_id=lambda _: SimpleNamespace(file_id=None), get_invoice_files=lambda _: [])
    service.file_repo = SimpleNamespace(get_file_by_id=lambda _: None)
    with pytest.raises(HTTPException) as exc: service.parse_invoice_file_and_update(1, str(path), 'user', provider='groq')
    assert exc.value.status_code == 403


def test_groq_result_updates_invoice_using_existing_pipeline(tmp_path, monkeypatch):
    path = tmp_path / 'invoice.png'; path.write_bytes(b'example')
    invoice = SimpleNamespace(file_id='file-1')
    saved = []; items = []
    service = InvoiceService.__new__(InvoiceService)
    service.repo = SimpleNamespace(get_invoice_by_id=lambda _: invoice,
        get_invoice_files=lambda _: [], save_invoice=lambda row: saved.append(row),
        delete_invoice_items_by_invoice_id=lambda invoice_id: items.clear(),
        create_invoice_item=lambda invoice_id, item: items.append(item) or item)
    service.file_repo = SimpleNamespace(get_file_by_id=lambda _: SimpleNamespace(file_path=str(path)), add_audit=lambda _: None)
    monkeypatch.setattr(groq, 'recognize_invoice_text', lambda p, b: 'Счёт № 123')
    monkeypatch.setattr(groq, 'extract_invoice_json', lambda prompt: '{"invoice_num":"123","items":[]}')
    monkeypatch.setattr(service, '_normalize_invoice_payload', lambda payload: {'invoice_num':'123', 'invoice_date':None, 'vat_rate':None, 'vat_amount':None, 'total_amount':100, 'items':[{'name':'Товар'}]})
    monkeypatch.setattr(service, '_recognised_requisites', lambda payload: {})
    result = service.parse_invoice_file_and_update(10, str(path), 'user', provider='groq')
    assert result['status'] == 'success' and result['items_count'] == 1
    assert saved[0].num == '123' and saved[0].total_amount == 100
