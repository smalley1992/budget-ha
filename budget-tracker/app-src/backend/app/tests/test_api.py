from collections.abc import Generator
import io
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import database, models
from app.database import Base, get_db
from app.main import app
from app.routers import ai_import
from app.routers.backups import _validate_sqlite_backup
from app.services import ai_import as ai_import_service
from app.services.ai_import import call_google_ai, validate_ai_import_file
from app.services.common import seed_default_categories


def create_family(client: TestClient) -> tuple[str, str]:
    first = client.post("/api/users", json={"name": "Alex", "icon": "A"}).json()
    second = client.post("/api/users", json={"name": "Sam", "icon": "S"}).json()
    return first["id"], second["id"]


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        seed_default_categories(db)

    def override_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_leftover_and_combined_summary(client: TestClient) -> None:
    alex_id, sam_id = create_family(client)
    client.post("/api/months", json={"period": "2026-06"})
    client.post("/api/income-lines", json={"user_id": alex_id, "period": "2026-06", "name": "Pay", "amount": 2000})
    client.post("/api/income-lines", json={"user_id": sam_id, "period": "2026-06", "name": "Pay", "amount": 1500})
    client.post("/api/budget-lines", json={"user_id": alex_id, "period": "2026-06", "type": "bill", "name": "Mortgage", "amount": 800})
    client.post("/api/budget-lines", json={"user_id": sam_id, "period": "2026-06", "type": "expense", "name": "Food", "amount": 300})

    alex = client.get("/api/summary", params={"period": "2026-06", "view": alex_id}).json()
    sam = client.get("/api/summary", params={"period": "2026-06", "view": sam_id}).json()
    combined = client.get("/api/summary", params={"period": "2026-06", "view": "combined"}).json()

    assert alex["totals"]["leftover"] == 1200
    assert sam["totals"]["leftover"] == 1200
    assert combined["totals"]["leftover"] == alex["totals"]["leftover"] + sam["totals"]["leftover"]
    assert set(combined["by_user"]) == {alex_id, sam_id}


def test_first_run_has_categories_without_seeded_users_or_fake_income(client: TestClient) -> None:
    users = client.get("/api/users").json()
    categories = client.get("/api/categories").json()

    assert users == []
    assert {"kind": "bill", "name": "Utilities"} in [
        {"kind": category["kind"], "name": category["name"]} for category in categories
    ]
    assert {"kind": "debt_payment", "name": "Credit card"} in [
        {"kind": category["kind"], "name": category["name"]} for category in categories
    ]


def test_user_profile_can_be_created_updated_and_deleted(client: TestClient) -> None:
    created = client.post("/api/users", json={"name": "Sam", "icon": "S"}).json()
    updated = client.patch(f"/api/users/{created['id']}", json={"name": "Sam", "icon": "SM", "salary": 2400}).json()

    assert updated["id"] == "sam"
    assert updated["name"] == "Sam"
    assert updated["icon"] == "SM"
    assert updated["salary"] == 2400
    assert client.delete("/api/users/sam").status_code == 204
    assert client.get("/api/users").json() == []


def test_debt_payment_ledger_lifecycle(client: TestClient) -> None:
    alex_id, _ = create_family(client)
    debt = client.post("/api/debts", json={"user_id": alex_id, "name": "Credit Cards", "starting_balance": 2000}).json()
    line = client.post(
        "/api/budget-lines",
        json={
            "user_id": alex_id,
            "period": "2026-06",
            "type": "debt_payment",
            "name": "Card payment",
            "amount": 100,
            "linked_debt_id": debt["id"],
        },
    ).json()
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 2000

    client.post(f"/api/budget-lines/{line['id']}/mark-paid")
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 1900

    client.patch(f"/api/budget-lines/{line['id']}", json={"amount": 150})
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 1850

    client.post(f"/api/budget-lines/{line['id']}/mark-planned")
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 2000

    client.post(f"/api/budget-lines/{line['id']}/mark-paid")
    client.delete(f"/api/budget-lines/{line['id']}")
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 2000


def test_payment_date_defaults_inside_selected_period_without_moving_planned_balances(client: TestClient) -> None:
    alex_id, _ = create_family(client)
    debt = client.post("/api/debts", json={"user_id": alex_id, "name": "Card", "starting_balance": 500}).json()
    line = client.post(
        "/api/budget-lines",
        json={
            "user_id": alex_id,
            "period": "2026-07",
            "type": "debt_payment",
            "name": "Card payment",
            "amount": 100,
            "status": "planned",
            "linked_debt_id": debt["id"],
        },
    ).json()

    assert line["payment_date"].startswith("2026-07-")
    assert line["paid_date"] is None
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 500

    paid = client.post(f"/api/budget-lines/{line['id']}/mark-paid").json()
    assert paid["paid_date"] == paid["payment_date"]
    assert client.get("/api/debts", params={"user_id": alex_id}).json()[0]["current_balance"] == 400


def test_savings_contribution_ledger_lifecycle(client: TestClient) -> None:
    _, sam_id = create_family(client)
    pot = client.post("/api/savings-pots", json={"user_id": sam_id, "name": "Holiday", "starting_balance": 500}).json()
    line = client.post(
        "/api/budget-lines",
        json={
            "user_id": sam_id,
            "period": "2026-06",
            "type": "savings_contribution",
            "name": "Holiday saving",
            "amount": 100,
            "linked_savings_pot_id": pot["id"],
        },
    ).json()
    assert client.get("/api/savings-pots", params={"user_id": sam_id}).json()[0]["current_balance"] == 500

    client.post(f"/api/budget-lines/{line['id']}/mark-paid")
    assert client.get("/api/savings-pots", params={"user_id": sam_id}).json()[0]["current_balance"] == 600

    client.patch(f"/api/budget-lines/{line['id']}", json={"amount": 125})
    assert client.get("/api/savings-pots", params={"user_id": sam_id}).json()[0]["current_balance"] == 625

    client.post(f"/api/budget-lines/{line['id']}/mark-planned")
    assert client.get("/api/savings-pots", params={"user_id": sam_id}).json()[0]["current_balance"] == 500


def test_untargeted_savings_goes_to_general_savings(client: TestClient) -> None:
    alex_id, _ = create_family(client)
    line = client.post(
        "/api/budget-lines",
        json={
            "user_id": alex_id,
            "period": "2026-06",
            "type": "savings_contribution",
            "name": "Spare cash",
            "amount": 25,
            "status": "paid",
        },
    ).json()
    pots = client.get("/api/savings-pots", params={"user_id": alex_id}).json()

    assert line["linked_savings_pot_id"] == pots[0]["id"]
    assert pots[0]["name"] == "General savings"
    assert pots[0]["current_balance"] == 25


def test_rollover_static_items_without_attachments(client: TestClient) -> None:
    alex_id, _ = create_family(client)
    client.post("/api/income-lines", json={"user_id": alex_id, "period": "2026-06", "name": "Salary", "amount": 2000, "is_static": True})
    static_line = client.post(
        "/api/budget-lines",
        json={"user_id": alex_id, "period": "2026-06", "type": "bill", "name": "Broadband", "amount": 40, "is_static": True, "status": "paid"},
    ).json()
    client.post(
        "/api/budget-lines",
        json={"user_id": alex_id, "period": "2026-06", "type": "expense", "name": "Coffee", "amount": 3.5},
    )
    upload = client.post(
        f"/api/budget-lines/{static_line['id']}/attachments",
        files={"file": ("bill.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert upload.status_code == 200

    result = client.post("/api/months/rollover", json={"source_period": "2026-06", "target_period": "2026-07"}).json()
    assert result["copied_income_lines"] == 1
    assert result["copied_budget_lines"] == 1

    income = client.get("/api/income-lines", params={"period": "2026-07", "user_id": alex_id}).json()
    lines = client.get("/api/budget-lines", params={"period": "2026-07", "user_id": alex_id}).json()
    assert len(income) == 1
    assert len(lines) == 1
    assert lines[0]["name"] == "Broadband"
    assert lines[0]["status"] == "planned"
    assert lines[0]["payment_date"].startswith("2026-07-")
    assert lines[0]["attachment_count"] == 0


def test_upload_validation_rejects_bad_files(client: TestClient) -> None:
    alex_id, _ = create_family(client)
    line = client.post(
        "/api/budget-lines",
        json={"user_id": alex_id, "period": "2026-06", "type": "expense", "name": "Coffee", "amount": 3.5},
    ).json()
    bad_extension = client.post(
        f"/api/budget-lines/{line['id']}/attachments",
        files={"file": ("receipt.exe", b"nope", "application/octet-stream")},
    )
    mime_mismatch = client.post(
        f"/api/budget-lines/{line['id']}/attachments",
        files={"file": ("receipt.png", b"not really png", "application/pdf")},
    )
    assert bad_extension.status_code == 400
    assert mime_mismatch.status_code == 400


def create_sqlite_database(db_path):
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with SessionFactory() as db:
        seed_default_categories(db)
    return engine, SessionFactory


def point_app_at_database(db_path, monkeypatch):
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(database.settings, "database_url", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", SessionFactory)
    return SessionFactory


def test_database_can_be_exported_and_imported(tmp_path, monkeypatch) -> None:
    active_path = tmp_path / "active.db"
    _, session_factory = create_sqlite_database(active_path)
    with session_factory() as db:
        db.add(models.User(slug="before", name="Before", icon="B"))
        db.commit()

    restore_path = tmp_path / "restore.sqlite3"
    _, restore_session_factory = create_sqlite_database(restore_path)
    with restore_session_factory() as db:
        db.add(models.User(slug="restored", name="Restored", icon="R"))
        db.commit()

    point_app_at_database(active_path, monkeypatch)

    with TestClient(app) as test_client:
        export_response = test_client.get("/api/backups/database")
        assert export_response.status_code == 200
        assert export_response.content.startswith(b"SQLite format 3")

        import_response = test_client.post(
            "/api/backups/database/import",
            files={"file": ("restore.sqlite3", restore_path.read_bytes(), "application/vnd.sqlite3")},
        )
        assert import_response.status_code == 200
        assert active_path.read_bytes().startswith(b"SQLite format 3")
        assert test_client.get("/api/users").json() == [{"id": "restored", "name": "Restored", "icon": "R", "salary": 0}]


def test_database_import_rejects_unsafe_attachment_metadata(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "unsafe.sqlite3"
    _, session_factory = create_sqlite_database(db_path)
    with session_factory() as db:
        user = models.User(slug="alex", name="Alex", icon="A")
        month = models.Month(period="2026-06")
        db.add_all([user, month])
        db.flush()
        line = models.BudgetLine(user_id=user.id, month_id=month.id, type="expense", name="Coffee", amount_cents=350)
        db.add(line)
        db.flush()
        db.add(
            models.Attachment(
                budget_line_id=line.id,
                original_filename="receipt.pdf",
                stored_filename="../secrets.pdf",
                content_type="application/pdf",
                size_bytes=10,
            )
        )
        db.commit()

    with pytest.raises(HTTPException):
        _validate_sqlite_backup(db_path)


def test_ai_import_preview_uses_existing_budget_context(client: TestClient, monkeypatch) -> None:
    alex_id, _ = create_family(client)
    client.post("/api/months", json={"period": "2026-06"})
    existing = client.post(
        "/api/budget-lines",
        json={"user_id": alex_id, "period": "2026-06", "type": "bill", "name": "Water", "amount": 52},
    ).json()

    captured = {}

    def fake_call_google_ai(api_key, model, prompt, mime_type, content):
        captured["api_key"] = api_key
        captured["prompt"] = prompt
        captured["mime_type"] = mime_type
        captured["content"] = content
        return {
            "document_type": "bill",
            "summary": "North Water bill",
            "proposals": [
                {
                    "source_text": "North Water 51.99",
                    "date": "2026-06-03",
                    "action": "update_existing",
                    "item_kind": "budget",
                    "user_id": alex_id,
                    "period": "2026-06",
                    "type": "bill",
                    "name": "Water",
                    "amount": 51.99,
                    "status": "paid",
                    "paid_date": "2026-06-03",
                    "linked_debt_id": None,
                    "linked_savings_pot_id": None,
                    "match_existing_line_id": existing["id"],
                    "confidence": 0.91,
                    "reasoning": "Merchant and amount are close to the existing water bill.",
                }
            ],
        }

    monkeypatch.setattr(ai_import, "call_google_ai", fake_call_google_ai)
    response = client.post(
        "/api/ai-import/preview",
        data={"period": "2026-06", "view": alex_id, "api_key": "test-key"},
        files={"file": ("water.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["proposals"][0]["match_existing_line_id"] == existing["id"]
    assert captured["api_key"] == "test-key"
    assert captured["mime_type"] == "application/pdf"
    assert captured["content"].startswith(b"%PDF")
    assert "Water" in captured["prompt"]


def test_ai_import_rejects_unsupported_upload_type() -> None:
    class FakeUpload:
        filename = "statement.exe"
        content_type = "application/octet-stream"

    with pytest.raises(HTTPException):
        validate_ai_import_file(FakeUpload(), 10)  # type: ignore[arg-type]


def test_google_ai_retries_transient_server_errors(monkeypatch) -> None:
    attempts = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"{\\"document_type\\":\\"receipt\\",\\"summary\\":\\"ok\\",\\"proposals\\":[]}"}]}}]}'

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ai_import_service.urllib.error.HTTPError(
                request.full_url,
                500,
                "Internal error encountered.",
                hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"Internal error encountered."}}'),
            )
        return FakeResponse()

    monkeypatch.setattr(ai_import_service.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ai_import_service.time, "sleep", lambda seconds: None)

    result = call_google_ai("test-key", "gemma-4-31b-it", "prompt", "image/jpeg", b"image")

    assert attempts["count"] == 2
    assert result["document_type"] == "receipt"


def test_google_ai_falls_back_when_gemma_31b_keeps_failing(monkeypatch) -> None:
    calls: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"{\\"document_type\\":\\"receipt\\",\\"summary\\":\\"fallback\\",\\"proposals\\":[]}"}]}}]}'

    def fake_urlopen(request, timeout):
        if "gemma-4-31b-it" in request.full_url:
            calls.append("gemma-4-31b-it")
            raise ai_import_service.urllib.error.HTTPError(
                request.full_url,
                500,
                "Internal error encountered.",
                hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"Internal error encountered."}}'),
            )
        calls.append("gemma-4-26b-a4b-it")
        return FakeResponse()

    monkeypatch.setattr(ai_import_service.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ai_import_service.time, "sleep", lambda seconds: None)

    result = call_google_ai("test-key", "gemma-4-31b-it", "prompt", "image/jpeg", b"image")

    assert calls == ["gemma-4-31b-it", "gemma-4-31b-it", "gemma-4-31b-it", "gemma-4-26b-a4b-it"]
    assert result["summary"] == "fallback"


def test_google_ai_suppresses_thought_summaries(monkeypatch) -> None:
    captured_body: dict = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"{\\"document_type\\":\\"receipt\\",\\"summary\\":\\"ok\\",\\"proposals\\":[]}"}]}}]}'

    def fake_urlopen(request, timeout):
        captured_body.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(ai_import_service.urllib.request, "urlopen", fake_urlopen)

    result = call_google_ai("test-key", "gemini-2.5-flash", "prompt", "image/jpeg", b"image")

    thinking_config = captured_body["generationConfig"]["thinkingConfig"]
    assert thinking_config["includeThoughts"] is False
    assert thinking_config["thinkingBudget"] == 0
    assert "systemInstruction" in captured_body
    assert result["summary"] == "ok"


def test_google_ai_falls_back_when_response_is_thought_only(monkeypatch) -> None:
    calls: list[str] = []

    class FakeThoughtOnlyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return (
                b'{"candidates":[{"content":{"parts":[{"text":"thinking instead of final JSON","thought":true}]},'
                b'"finishReason":"MAX_TOKENS"}]}'
            )

    class FakeFinalResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"{\\"document_type\\":\\"receipt\\",\\"summary\\":\\"fallback\\",\\"proposals\\":[]}"}]}}]}'

    def fake_urlopen(request, timeout):
        if "gemma-4-31b-it" in request.full_url:
            calls.append("gemma-4-31b-it")
            return FakeThoughtOnlyResponse()
        calls.append("gemma-4-26b-a4b-it")
        return FakeFinalResponse()

    monkeypatch.setattr(ai_import_service.urllib.request, "urlopen", fake_urlopen)

    result = call_google_ai("test-key", "gemma-4-31b-it", "prompt", "image/jpeg", b"image")

    assert calls == ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
    assert result["summary"] == "fallback"
