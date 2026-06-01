from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.database import Base
from app.models import ProductEvent, User
from app.wechat import WechatSession
from app import models  # noqa: F401


def make_event_payload(**overrides) -> dict:
    payload = {
        "eventName": "home_view",
        "clientId": "client-test-1",
        "page": "home",
        "properties": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def auth_headers(client: TestClient, code: str = "event-code") -> dict[str, str]:
    response = client.post("/api/auth/wechat", json={"code": code})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_product_event_accepts_anonymous_user(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    with TestClient(main_module.app) as client:
        response = client.post("/api/events", json=make_event_payload())

    main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    event_id = response.json()["id"]
    db = testing_session()
    event = db.get(ProductEvent, event_id)
    assert event is not None
    assert event.user_id is None
    assert event.event_name == "home_view"
    assert event.properties_json == {"source": "test"}
    db.close()


def test_product_event_links_authenticated_user(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    async def fake_exchange_wechat_code(code, settings):
        return WechatSession(openid=f"event_{code}")

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    monkeypatch.setattr(main_module, "exchange_wechat_code", fake_exchange_wechat_code)
    with TestClient(main_module.app) as client:
        headers = auth_headers(client, "user-a")
        response = client.post(
            "/api/events",
            json=make_event_payload(eventName="quiz_generate_success", sessionId="session-1"),
            headers=headers,
        )

    main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    event_id = response.json()["id"]
    db = testing_session()
    user = db.scalar(select(User).where(User.openid == "event_user-a"))
    event = db.get(ProductEvent, event_id)
    assert user is not None
    assert event is not None
    assert event.user_id == user.id
    assert event.session_id == "session-1"
    db.close()


def test_product_event_validates_required_fields(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    with TestClient(main_module.app) as client:
        missing_event = client.post(
            "/api/events",
            json={"clientId": "client-test-1", "page": "home"},
        )
        invalid_properties = client.post(
            "/api/events",
            json=make_event_payload(properties=["not-object"]),
        )

    main_module.app.dependency_overrides.clear()

    assert missing_event.status_code == 422
    assert invalid_properties.status_code == 422
