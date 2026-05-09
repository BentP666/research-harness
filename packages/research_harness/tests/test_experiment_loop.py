"""Tests for experiment_loop primitive."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from research_harness.primitives.experiment_loop_impl import experiment_loop
from research_harness.primitives.types import ExperimentBudget
from research_harness.storage.db import Database


@dataclass(frozen=True)
class _FakeCodeGen:
    """Stand-in for code_generate output."""

    files: dict[str, str] = field(default_factory=dict)
    entry_point: str = "main.py"
    description: str = ""
    model_used: str = "fake"
    cost_usd: float = 0.01
    tokens_used: int = 100


@pytest.fixture
def db(tmp_path: Path) -> Database:
    d = Database(db_path=tmp_path / "loop.db")
    d.migrate()
    conn = d.connect()
    try:
        conn.execute("INSERT INTO topics (id, name) VALUES (1, 'test-topic')")
        conn.commit()
    finally:
        conn.close()
    return d


def _script(value: float) -> str:
    return f"print('val_acc: {value}')\n"


def test_loop_records_runs_and_picks_best(db: Database):
    scripted = [0.50, 0.72, 0.65, 0.80, 0.78]
    calls: list[int] = []

    def gen(*, iteration: int, **_: object) -> _FakeCodeGen:
        calls.append(iteration)
        val = scripted[iteration]
        return _FakeCodeGen(files={"main.py": _script(val)})

    out = experiment_loop(
        db=db,
        topic_id=1,
        code_generate_fn=gen,
        name="prompt-tune",
        task_description="Pick best prompt",
        primary_metric="val_acc",
        direction="max",
        mode="agent",
        timeout_sec=20.0,
        budget=ExperimentBudget(max_iterations=5, patience=10),
    )

    assert out.total_iterations == 5, out.runs
    assert out.best_iteration == 3
    assert out.best_value == pytest.approx(0.80)
    assert out.stopped_reason == "budget_iterations"
    assert out.total_cost_usd == pytest.approx(0.05)
    assert out.total_tokens == 500
    assert calls == [0, 1, 2, 3, 4]

    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT iteration, primary_metric_value, status FROM experiment_loop_runs WHERE experiment_id = ? ORDER BY iteration",
            (out.experiment_id,),
        ).fetchall()
        best_run = conn.execute(
            "SELECT best_run_id, status, stopped_reason FROM experiments WHERE id = ?",
            (out.experiment_id,),
        ).fetchone()
    finally:
        conn.close()

    assert len(rows) == 5
    assert [r["status"] for r in rows] == ["completed"] * 5
    assert best_run["best_run_id"] == out.best_run_id
    assert best_run["status"] == "completed"
    assert best_run["stopped_reason"] == "budget_iterations"


def test_loop_early_stops_on_patience(db: Database):
    scripted = [0.50, 0.60, 0.55, 0.58, 0.59, 0.57]

    def gen(*, iteration: int, **_: object) -> _FakeCodeGen:
        return _FakeCodeGen(files={"main.py": _script(scripted[iteration])})

    out = experiment_loop(
        db=db,
        topic_id=1,
        code_generate_fn=gen,
        task_description="Patience test",
        primary_metric="val_acc",
        direction="max",
        budget=ExperimentBudget(max_iterations=10, patience=3),
    )

    assert out.best_iteration == 1
    assert out.best_value == pytest.approx(0.60)
    assert out.stopped_reason == "patience"
    assert out.total_iterations < 10


def test_loop_handles_invalid_entry(db: Database):
    """Generator that forgets the entry file should not crash the loop."""

    responses = [
        _FakeCodeGen(files={"helper.py": "x = 1\n"}, entry_point="main.py"),
        _FakeCodeGen(files={"main.py": _script(0.9)}, entry_point="main.py"),
    ]

    def gen(*, iteration: int, **_: object) -> _FakeCodeGen:
        return responses[iteration]

    out = experiment_loop(
        db=db,
        topic_id=1,
        code_generate_fn=gen,
        task_description="Bad then good",
        primary_metric="val_acc",
        budget=ExperimentBudget(max_iterations=2, patience=5),
    )

    assert out.best_value == pytest.approx(0.9)
    assert out.best_iteration == 1

    conn = db.connect()
    try:
        statuses = [
            r["status"]
            for r in conn.execute(
                "SELECT status FROM experiment_loop_runs WHERE experiment_id = ? ORDER BY iteration",
                (out.experiment_id,),
            ).fetchall()
        ]
    finally:
        conn.close()
    assert statuses == ["invalid", "completed"]


def test_loop_validator_rejects_agent_code_with_subprocess(db: Database):
    bad_code = "import subprocess\nsubprocess.run(['ls'])\nprint('val_acc: 0.9')\n"
    good_code = _script(0.8)
    responses = [
        _FakeCodeGen(files={"main.py": bad_code}),
        _FakeCodeGen(files={"main.py": good_code}),
    ]

    def gen(*, iteration: int, **_: object) -> _FakeCodeGen:
        return responses[iteration]

    out = experiment_loop(
        db=db,
        topic_id=1,
        code_generate_fn=gen,
        task_description="Validator guards",
        primary_metric="val_acc",
        mode="agent",
        budget=ExperimentBudget(max_iterations=2, patience=5),
    )

    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT iteration, status, feedback_to_next FROM experiment_loop_runs WHERE experiment_id = ? ORDER BY iteration",
            (out.experiment_id,),
        ).fetchall()
    finally:
        conn.close()

    assert rows[0]["status"] == "invalid"
    assert "subprocess" in rows[0]["feedback_to_next"].lower()
    assert rows[1]["status"] == "completed"
    assert out.best_value == pytest.approx(0.8)


def test_loop_budget_cost_stops_loop(db: Database):
    def gen(*, iteration: int, **_: object) -> _FakeCodeGen:
        return _FakeCodeGen(
            files={"main.py": _script(0.5 + 0.01 * iteration)},
            cost_usd=0.6,  # 2 iterations exhaust $1.0 budget
        )

    out = experiment_loop(
        db=db,
        topic_id=1,
        code_generate_fn=gen,
        task_description="Cost guard",
        primary_metric="val_acc",
        budget=ExperimentBudget(max_iterations=10, max_cost_usd=1.0, patience=10),
    )

    assert out.stopped_reason == "budget_cost"
    assert out.total_iterations == 2


def test_loop_fixtures_override_generated_files(db: Database):
    """Fixture files must not be overwritten by the generator."""

    generator_tries_to_cheat = _FakeCodeGen(
        files={
            "main.py": ("from scorer import score\nprint(f'val_acc: {score()}')\n"),
            "scorer.py": "def score(): return 0.99\n",
        }
    )
    fixture_scorer = "def score(): return 0.42\n"

    def gen(**_: object) -> _FakeCodeGen:
        return generator_tries_to_cheat

    out = experiment_loop(
        db=db,
        topic_id=1,
        code_generate_fn=gen,
        task_description="Fixture integrity",
        fixture_files={"scorer.py": fixture_scorer},
        primary_metric="val_acc",
        budget=ExperimentBudget(max_iterations=1, patience=5),
    )

    assert out.best_value == pytest.approx(0.42)
    conn = db.connect()
    try:
        files_json = conn.execute(
            "SELECT files_json FROM experiment_loop_runs WHERE experiment_id = ? ORDER BY iteration",
            (out.experiment_id,),
        ).fetchone()["files_json"]
    finally:
        conn.close()

    files = json.loads(files_json)
    assert files["scorer.py"] == fixture_scorer
