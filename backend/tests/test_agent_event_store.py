"""Agent 事件持久化测试。

覆盖：写入不在事件循环里执行、每条事件只占一行、seq/event_id 在读取
时补齐、重放游标语义不变。
"""

import asyncio
import json

import pytest

from app.core.sqlite import connect
from app.services import agent_run_store as runs


@pytest.fixture
def admitted_run(test_client, admin_headers):
    """准入一次运行。"""
    from tests.test_langchain import new_thread

    cid = new_thread(test_client, admin_headers)
    run, _created = asyncio.run(runs.admit_run(cid, "event-store-test"))
    return cid, run


class TestEventWritePath:
    """写入路径。"""

    @pytest.mark.asyncio
    async def test_append_event_yields_control_to_the_event_loop(
        self, admitted_run
    ):
        """写入必须让出事件循环。

        ``loop.call_soon`` 排的回调只有在循环拿到控制权时才会执行；
        如果 append_event 全程同步阻塞，回调就来不及跑。
        """
        cid, run = admitted_run
        marker: list[str] = []
        loop = asyncio.get_running_loop()

        task = asyncio.create_task(
            runs.append_event(run, runs.protocol_event("values", {"probe": 1}))
        )
        loop.call_soon(marker.append, "scheduled")
        await task

        assert marker == ["scheduled"], "事件循环在写入期间被阻塞了"

    @pytest.mark.asyncio
    async def test_each_event_occupies_exactly_one_row(self, admitted_run):
        """每条事件只写一行——payload 直接落库，不做先插后改。"""
        cid, run = admitted_run
        for index in range(5):
            await runs.append_event(
                run, runs.protocol_event("values", {"index": index})
            )

        with connect() as db:
            rows = db.execute(
                "SELECT payload FROM agent_events WHERE conversation_id=? AND run_id=?",
                (cid, run["run_id"]),
            ).fetchall()

        assert len(rows) == 5
        for row in rows:
            payload = json.loads(row["payload"])
            # seq 与 event_id 在读取时补齐，落库的 payload 不含它们
            assert "seq" not in payload
            assert "event_id" not in payload
            assert payload["type"] == "event"

    @pytest.mark.asyncio
    async def test_read_fills_sequence_and_event_id(self, admitted_run):
        """读取时补齐单调递增的 seq 与稳定的 event_id。"""
        cid, run = admitted_run
        for index in range(3):
            await runs.append_event(
                run, runs.protocol_event("values", {"index": index})
            )

        events = await runs.read_events(cid, 0)
        assert len(events) == 3
        seqs = [event["seq"] for event in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 3
        for event in events:
            assert event["event_id"] == f"{run['run_id']}:{event['seq']}"

    @pytest.mark.asyncio
    async def test_cursor_replay_is_stable(self, admitted_run):
        """按游标重放语义不变：增量读取与全量一致。"""
        cid, run = admitted_run
        for index in range(4):
            await runs.append_event(
                run, runs.protocol_event("values", {"index": index})
            )

        first = await runs.read_events(cid, 0)
        assert first == await runs.read_events(cid, 0)
        assert await runs.read_events(cid, first[0]["seq"]) == first[1:]

    @pytest.mark.asyncio
    async def test_finish_run_appends_terminal_event(self, admitted_run):
        """结束运行会追加终止事件。"""
        cid, run = admitted_run
        await runs.finish_run(run, "cancelled", "已取消")

        events = await runs.read_events(cid, 0)
        assert events[-1]["method"] == "lifecycle"
        # cancelled / interrupted / waiting_approval 都归入 interrupted 阶段
        assert events[-1]["params"]["data"]["event"] == "interrupted"
        assert events[-1]["params"]["data"]["error"] == "已取消"
