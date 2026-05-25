from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

from fastapi.testclient import TestClient

from research_harness.longtask import LongTaskStore, LongTaskSupervisor
from research_harness_mcp import http_api


def test_longtask_api_lists_run_detail_and_approves_gate(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".longrun"
    store = LongTaskStore(home)
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run("API run", "- [ ] Inspect state", max_workers=1)
    task_id = store.get_run_detail(run.id)["tasks"][0]["id"]

    monkeypatch.setattr(http_api, "LONGTASK_HOME", home)
    client = TestClient(http_api.app)
    gate_response = client.post(
        f"/api/longtasks/runs/{run.id}/gates",
        json={
            "task_id": task_id,
            "gate_type": "continue_next_wave",
            "title": "Continue?",
            "token": "approve-me",
        },
    )
    assert gate_response.status_code == 201
    gate_id = gate_response.json()["id"]

    runs = client.get("/api/longtasks/runs").json()
    assert runs[0]["id"] == run.id

    detail = client.get(f"/api/longtasks/runs/{run.id}").json()
    assert detail["run"]["title"] == "API run"
    assert detail["tasks"][0]["title"] == "Inspect state"
    assert detail["gates"][0]["token_required"] is True
    assert detail["gates"][0]["notification"]["title"] == "Continue?"
    assert detail["gates"][0]["notification"]["action_url"].startswith(
        "http://testserver/api/longtasks/gates/"
    )
    assert "approve-me" not in str(detail["gates"][0]["notification"])

    bad = client.post(
        f"/api/longtasks/gates/{gate_id}/decision",
        json={"decision": "approved", "actor": "phone", "token": "bad"},
    )
    assert bad.status_code == 403

    good = client.post(
        f"/api/longtasks/gates/{gate_id}/decision",
        json={"decision": "approved", "actor": "phone", "token": "approve-me"},
    )
    assert good.status_code == 200
    assert good.json()["accepted"] is True


def test_longtask_api_accepts_signed_gate_action_link(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".longrun"
    store = LongTaskStore(home)
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run("Signed API run", "- [ ] Inspect state", max_workers=1)
    gate = supervisor.create_gate(
        run_id=run.id,
        task_id=None,
        gate_type="continue_next_wave",
        title="Continue by link?",
        token="do-not-leak",
    )

    monkeypatch.setattr(http_api, "LONGTASK_HOME", home)
    client = TestClient(http_api.app)
    detail = client.get(f"/api/longtasks/runs/{run.id}").json()
    approve_url = detail["gates"][0]["notification"]["actions"]["approve"]["url"]
    assert "do-not-leak" not in approve_url

    response = client.get(approve_url.replace("http://testserver", ""))

    assert response.status_code == 200
    assert response.json()["requires_post"] is True
    assert store.get_run_detail(run.id)["gates"][0]["status"] == "pending"

    parsed = urlparse(approve_url.replace("http://testserver", ""))
    query = parse_qs(parsed.query)
    query["view"] = ["1"]
    confirm_with_ui_url = (
        f"{parsed.path}?{urlencode({k: v[0] for k, v in query.items()})}"
    )
    confirm_response = client.get(confirm_with_ui_url)
    assert confirm_response.status_code == 200
    assert "Mobile confirmation" in confirm_response.text
    assert "Confirm this decision" in confirm_response.text

    response = client.post(approve_url.replace("http://testserver", ""))
    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert store.get_run_detail(run.id)["gates"][0]["status"] == "approved"

    replay = client.post(approve_url.replace("http://testserver", ""))
    assert replay.status_code == 409

    expired_signature = supervisor.sign_gate_action(
        gate.id,
        decision="approved",
        expires_at=1,
    )
    expired = client.get(
        f"/api/longtasks/gates/{gate.id}/action",
        params={
            "decision": "approved",
            "expires_at": 1,
            "signature": expired_signature,
        },
    )
    assert expired.status_code == 403


def test_longtask_api_admin_token_when_configured(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".longrun"
    LongTaskStore(home)
    monkeypatch.setattr(http_api, "LONGTASK_HOME", home)
    monkeypatch.setenv("RESEARCH_HARNESS_LONGTASK_ADMIN_TOKEN", "admin-secret")
    client = TestClient(http_api.app)

    unauth = client.get("/api/longtasks/runs")
    assert unauth.status_code == 401

    auth = client.get(
        "/api/longtasks/runs",
        headers={"X-LongTask-Token": "admin-secret"},
    )
    assert auth.status_code == 200


def test_longtask_api_dispatch_and_supervise_are_dry_run_by_default(
    tmp_path,
    monkeypatch,
) -> None:
    home = tmp_path / ".longrun"
    store = LongTaskStore(home)
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        "Dispatch API run",
        "- [ ] First node\n- [ ] Second node",
        max_workers=2,
    )

    monkeypatch.setattr(http_api, "LONGTASK_HOME", home)
    client = TestClient(http_api.app)

    dispatch = client.post(
        f"/api/longtasks/runs/{run.id}/dispatch",
        json={"limit": 1},
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["dispatched"] == 1
    assert store.get_run_detail(run.id)["tasks"][0]["status"] == "complete"

    supervise = client.post(
        f"/api/longtasks/runs/{run.id}/supervise",
        json={"max_cycles": 3},
    )
    assert supervise.status_code == 200
    assert supervise.json()["stop_reason"] == "complete"
    assert store.get_run_detail(run.id)["run"]["status"] == "complete"

    blocked_execute = client.post(
        f"/api/longtasks/runs/{run.id}/dispatch",
        json={"execute": True},
    )
    assert blocked_execute.status_code == 403
