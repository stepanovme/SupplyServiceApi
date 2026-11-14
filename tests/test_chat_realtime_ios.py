from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import app.api as api

class DB:
    def close(self): pass
class SessionRepo:
    def __init__(self, db): pass
    def get_by_token(self, token): return SimpleNamespace(user_id='alice') if token == 'good' else None
class Chats:
    def __init__(self, db): pass
    def get_member(self, chat_id, user_id): return object() if chat_id == 7 and user_id == 'alice' else None
    def get_members(self, chat_id): return [SimpleNamespace(user_id='alice'), SimpleNamespace(user_id='bob')]
class Users:
    def __init__(self, db): pass
    def get_by_ids(self, ids): return [SimpleNamespace(name='Alice',surname='A',patronymic=None)]

def test_websocket_auth_and_typing(monkeypatch):
    for key, value in [('AuthSessionLocal',DB),('SupplySessionLocal',DB),('SessionRepository',SessionRepo),('ChatRepository',Chats),('AuthUserRepository',Users),('_get_badge_counts',lambda _: {}),('_get_notification_unread_count',lambda _: 0),('tenant_cookie_name',lambda: 'session')]: monkeypatch.setattr(api,key,value)
    events=[]
    monkeypatch.setattr(api.ws_manager,'broadcast_to_chat',lambda members,data,exclude_user_id=None: events.append(data))
    with TestClient(api.app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/api/supply/ws?user_id=bob',headers={'cookie':'session=good'}): pass
        with client.websocket_connect('/api/supply/ws?user_id=alice',headers={'cookie':'session=good'}) as ws:
            ws.receive_json(); ws.receive_json()
            ws.send_json({'type':'typing','chat_id':7,'is_typing':True}); ws.send_text('ping')
            assert ws.receive_text() == 'pong'
            assert events[0]['user_name'] == 'A Alice'
            ws.send_json({'type':'typing','chat_id':8,'is_typing':True}); ws.send_text('ping')
            assert ws.receive_text() == 'pong' and len(events) == 1

def test_apns_token_signature(tmp_path):
    import base64
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from cryptography.hazmat.primitives import hashes, serialization
    from app.services.apns_service import _jwt
    key=ec.generate_private_key(ec.SECP256R1()); path=tmp_path/'key.p8'
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    head,payload,sig=_jwt('team','key',str(path)).split('.')
    signature=base64.urlsafe_b64decode(sig+'==')
    key.public_key().verify(encode_dss_signature(int.from_bytes(signature[:32],'big'),int.from_bytes(signature[32:],'big')),f'{head}.{payload}'.encode(),ec.ECDSA(hashes.SHA256()))


def test_inline_attachment_checks_membership_and_identity(monkeypatch):
    from fastapi import HTTPException
    from app.routes.chats_routes import attachment_content
    class Repo:
        def __init__(self, member=True, attachment_message=3): self.member=member; self.attachment_message=attachment_message
        def get_member(self, chat_id, user_id): return self.member
        def get_message_by_id(self, message_id): return SimpleNamespace(chat_id=2)
        def get_attachment_by_id(self, attachment_id): return SimpleNamespace(message_id=self.attachment_message)
    class Service:
        def __init__(self, repo): self.repo=repo
        def download_attachment(self, attachment_id): return '/tmp/test.png', 'test.png'
    service=Service(Repo())
    monkeypatch.setattr('app.routes.chats_routes.build_service', lambda *_: service)
    response=attachment_content(2,3,4,None,None,SimpleNamespace(user_id='alice'))
    assert response.media_type == 'image/png' and response.headers['content-disposition'].startswith('inline')
    service.repo=Repo(member=False)
    with pytest.raises(HTTPException) as error:
        attachment_content(2,3,4,None,None,SimpleNamespace(user_id='alice'))
    assert error.value.status_code == 403
    service.repo=Repo(attachment_message=9)
    with pytest.raises(HTTPException) as error:
        attachment_content(2,3,4,None,None,SimpleNamespace(user_id='alice'))
    assert error.value.status_code == 404
