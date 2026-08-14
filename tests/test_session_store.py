"""SessionStore 单元测试。

覆盖: 新建/追加/最近列表倒序/加载/状态更新/上下文/原子写盘/防路径穿越。
纯标准库 unittest 实现(环境未装 pytest), 用临时目录隔离,
不依赖 SolidWorks 或第三方包, 契合内网离线约束。
"""

import json
import tempfile
import time
import unittest
from pathlib import Path

from service.session_store import SessionStore


class SessionStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "sessions"
        self.store = SessionStore(base_dir=str(self.base))

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_session_returns_id_and_writes_file(self):
        sid = self.store.create_session(title="测试会话")
        self.assertTrue(isinstance(sid, str) and sid)

        session = self.store.load(sid)
        self.assertIsNotNone(session)
        self.assertEqual(session["id"], sid)
        self.assertEqual(session["title"], "测试会话")
        self.assertEqual(session["status"], "active")
        self.assertEqual(session["messages"], [])
        self.assertEqual(session["context"], {})
        self.assertTrue(session["started_at"])
        self.assertTrue(session["updated_at"])

    def test_create_with_first_message(self):
        sid = self.store.create_session(
            title="", first_message={"role": "user", "text": "画一个底板"})
        session = self.store.load(sid)
        self.assertEqual(len(session["messages"]), 1)
        self.assertEqual(session["messages"][0]["role"], "user")
        self.assertEqual(session["messages"][0]["text"], "画一个底板")
        self.assertTrue(session["messages"][0].get("ts"))

    def test_append_message(self):
        sid = self.store.create_session(title="s")
        self.assertTrue(self.store.append_message(sid, {"role": "user", "text": "第一句"}))
        self.assertTrue(self.store.append_message(
            sid, {"role": "ai", "text": "计划A", "type": "plan"}))

        msgs = self.store.get_messages(sid)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["text"], "第一句")
        self.assertEqual(msgs[1]["role"], "ai")
        self.assertEqual(msgs[1]["type"], "plan")

    def test_append_to_missing_session_returns_false(self):
        self.assertFalse(
            self.store.append_message("not_exist_id", {"role": "user", "text": "x"}))

    def test_default_title_derived_from_first_append(self):
        sid = self.store.create_session(title="")  # 默认 "未命名会话"
        self.store.append_message(sid, {"role": "user", "text": "帮我画一个直径50的圆柱做支撑轴"})
        session = self.store.load(sid)
        self.assertEqual(session["title"], "帮我画一个直径50的圆柱做支撑轴"[:24])

    def test_set_status(self):
        sid = self.store.create_session(title="s")
        self.assertTrue(self.store.set_status(sid, "done"))
        self.assertEqual(self.store.load(sid)["status"], "done")
        # 非法状态回落为 active
        self.assertTrue(self.store.set_status(sid, "weird"))
        self.assertEqual(self.store.load(sid)["status"], "active")
        self.assertFalse(self.store.set_status("no_id", "done"))

    def test_set_context(self):
        sid = self.store.create_session(title="s")
        plan = {"title": "底板", "operations": [{"type": "extrude"}]}
        self.assertTrue(self.store.set_context(sid, "last_plan", plan))
        self.assertEqual(self.store.load(sid)["context"]["last_plan"], plan)
        self.assertFalse(self.store.set_context("no_id", "k", 1))

    def test_list_recent_ordered_by_updated_desc(self):
        ids = []
        for i in range(4):
            sid = self.store.create_session(title=f"会话{i}")
            ids.append(sid)
            time.sleep(0.01)

        recent = self.store.list_recent(limit=3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["id"], ids[-1])
        self.assertEqual(recent[1]["id"], ids[-2])
        self.assertEqual(recent[2]["id"], ids[-3])
        for item in recent:
            self.assertTrue(
                set(item.keys()) >= {"id", "title", "status", "started_at", "updated_at"})

    def test_list_recent_reorders_after_update(self):
        a = self.store.create_session(title="A")
        time.sleep(0.01)
        b = self.store.create_session(title="B")
        time.sleep(0.01)
        self.store.append_message(a, {"role": "user", "text": "更新A"})

        recent = self.store.list_recent(limit=2)
        self.assertEqual(recent[0]["id"], a)
        self.assertEqual(recent[1]["id"], b)

    def test_list_recent_zero_or_negative_limit(self):
        self.store.create_session(title="s")
        self.assertEqual(self.store.list_recent(limit=0), [])
        self.assertEqual(self.store.list_recent(limit=-5), [])

    def test_get_messages_missing_returns_empty(self):
        self.assertEqual(self.store.get_messages("no_id"), [])

    def test_atomic_write_no_tmp_leftover(self):
        sid = self.store.create_session(title="s")
        self.store.append_message(sid, {"role": "user", "text": "x"})
        leftover = list(self.base.rglob("*.tmp"))
        self.assertEqual(leftover, [])
        files = list(self.base.rglob("*.json"))
        self.assertTrue(files)

    def test_path_traversal_is_blocked(self):
        malicious = "../../etc/passwd"
        self.assertIsNone(self.store.load(malicious))
        self.assertFalse(
            self.store.append_message(malicious, {"role": "user", "text": "x"}))
        self.assertFalse(self.store.set_status(malicious, "done"))

    def test_index_file_is_valid_json(self):
        self.store.create_session(title="s1")
        self.store.create_session(title="s2")
        index_path = self.base / "index.json"
        self.assertTrue(index_path.exists())
        data = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertIn("sessions", data)
        self.assertEqual(len(data["sessions"]), 2)


if __name__ == "__main__":
    unittest.main()