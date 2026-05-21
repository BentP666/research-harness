import asyncio

from research_harness.acquisition import pipeline


class DummyCandidate:
    paper_id = 1


async def _fake_download_batch(candidates, download_path):
    return ["ok", len(candidates), str(download_path)]


def test_run_download_batch_inside_running_event_loop(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "download_batch", _fake_download_batch)

    async def call_inside_loop():
        return pipeline._run_download_batch([DummyCandidate()], tmp_path)

    assert asyncio.run(call_inside_loop()) == ["ok", 1, str(tmp_path)]
