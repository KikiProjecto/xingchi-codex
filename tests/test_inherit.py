"""Local history selection does not require a key or a running model."""

from pathlib import Path
from io import StringIO
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from xingchi_history import inherited_launch_args, label, list_threads, pick_thread, read_thread, select_thread, serve_history


FIRST = "10000000-0000-0000-0000-000000000001"
SECOND = "20000000-0000-0000-0000-000000000002"
OTHER = "30000000-0000-0000-0000-000000000003"


class InheritTests(unittest.TestCase):
    def test_direct_inherit_starts_with_full_access_without_approval_prompts(self):
        args = inherited_launch_args(FIRST, Path.cwd(), Path("runner.py"))
        self.assertEqual(args[0], "--dangerously-bypass-approvals-and-sandbox")
        self.assertEqual(args[-2], "--")
        self.assertIn(FIRST, args[-1])
        self.assertIn("mcp_servers.xingchi_inherit=", args[2])

    def test_in_chat_inherit_replaces_conflicting_permission_flags(self):
        variants = [
            ["-s", "read-only", "-a", "on-request"],
            ["--sandbox", "workspace-write", "--ask-for-approval", "on-request"],
            ["--sandbox=read-only", "--ask-for-approval=on-request"],
            ["-sread-only", "-aon-request"],
            ["--full-auto"], ["--approve-for-me"], ["--not-so-yolo"],
            ["--yolo"], ["--dangerously-bypass-approvals-and-sandbox"],
        ]
        kept = ["-m", "selected-model", "-C", "/project", "--search", "--no-alt-screen",
                "-c", 'model_reasoning_effort="high"', "--add-dir", "-some-directory"]
        for flags in variants:
            with self.subTest(flags=flags):
                args = inherited_launch_args(FIRST, Path.cwd(), Path("runner.py"), [*kept, *flags])
                self.assertEqual(args[:len(kept)], kept)
                self.assertEqual(args[len(kept)], "--dangerously-bypass-approvals-and-sandbox")
                self.assertEqual(len(args), len(kept) + 5)

    def test_picker_selects_an_id_or_number_without_starting_a_model(self):
        threads = [{"id": FIRST, "name": "First task", "archived": False},
                   {"id": SECOND, "name": "Second task", "archived": False}]
        for choice in ("2\n", "@" + SECOND + "\n"):
            with self.subTest(choice=choice):
                input_ = StringIO(choice)
                input_.isatty = lambda: True
                with patch("sys.stdin", input_), patch("sys.stderr", StringIO()):
                    self.assertEqual(pick_thread(threads)["id"], SECOND)

    def test_lists_active_and_archived_pages_but_not_a_sibling_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory).resolve()
            first = {"id": FIRST, "cwd": str(cwd), "updatedAt": 1, "name": "Bevy migration"}
            second = {"id": SECOND, "cwd": str(cwd), "updatedAt": 5, "name": "Bevy renderer\x1b[31m"}
            other = {"id": OTHER, "cwd": str(cwd / "sibling"), "updatedAt": 9}
            request = Mock(side_effect=[{"data": [first], "nextCursor": "page2"},
                                        {"data": [other]}, {"data": [second]}])
            threads = list_threads(request, cwd)
            self.assertEqual([thread["id"] for thread in threads], [SECOND, FIRST])
            self.assertEqual(request.call_args_list[1].kwargs["cursor"], "page2")
            self.assertTrue(request.call_args_list[2].kwargs["archived"])
            self.assertEqual(select_thread(threads, "Bevy migration")["id"], FIRST)
            self.assertEqual(select_thread(threads, "20000000")["id"], SECOND)
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                select_thread(threads, "bevy")
            self.assertNotIn("\x1b", label(threads[0]))

    def test_full_id_is_checked_against_current_directory_before_reading_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory).resolve()
            request = Mock(return_value={"thread": {"id": FIRST, "cwd": str(cwd / "other")}})
            with self.assertRaisesRegex(RuntimeError, "not a saved session in this directory"):
                read_thread(request, FIRST, cwd)
            request.assert_called_once_with("thread/read", threadId=FIRST, includeTurns=False)

    def test_mcp_tool_cannot_select_another_session(self):
        @contextmanager
        def history(_):
            yield request

        request = Mock(side_effect=[{"thread": {"id": FIRST, "cwd": str(Path.cwd().resolve())}},
                                    {"data": [{"id": "turn_saved"}], "nextCursor": "older"}])
        messages = [
            {"id": 1, "method": "tools/call", "params": {"name": "read_saved_history",
                                                       "arguments": {"thread_id": SECOND}}},
            {"id": 2, "method": "tools/call", "params": {"name": "read_saved_history",
                                                       "arguments": {"view": "summary", "cursor": "newer"}}},
        ]
        output = StringIO()
        with patch("xingchi_history.local_history", history), \
                patch("sys.stdin", StringIO("\n".join(json.dumps(m) for m in messages))), \
                patch("sys.stdout", output):
            serve_history(FIRST, lambda: [])
        rejected, allowed = [json.loads(line)["result"] for line in output.getvalue().splitlines()]
        self.assertTrue(rejected["isError"])
        self.assertFalse(allowed["isError"])
        self.assertIn("older", allowed["content"][0]["text"])
        self.assertEqual(request.call_count, 2)
        request.assert_called_with("thread/turns/list", threadId=FIRST, cursor="newer",
                                   sortDirection="desc", limit=1, itemsView="summary")
