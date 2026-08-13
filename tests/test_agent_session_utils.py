import hashlib
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class AgentSessionUtilsTest(unittest.TestCase):
    def test_extracts_stable_file_session_id_from_marker(self):
        from utils.session_utils import extract_session_id_from_message

        expected_digest = hashlib.sha256("voice-message".encode("utf-8")).hexdigest()[:16]

        self.assertEqual(
            extract_session_id_from_message("@@/tmp/voice-message.m4a@@ 今天天气怎么样"),
            f"file_{expected_digest}",
        )

    def test_remove_filename_markers_returns_clean_message(self):
        from utils.session_utils import remove_filename_markers

        self.assertEqual(
            remove_filename_markers("@@/tmp/voice-message.m4a@@ 今天天气怎么样"),
            "今天天气怎么样",
        )

    def test_remove_filename_markers_preserves_original_when_only_marker_exists(self):
        from utils.session_utils import remove_filename_markers

        self.assertEqual(
            remove_filename_markers("@@/tmp/voice-message.m4a@@"),
            "@@/tmp/voice-message.m4a@@",
        )


if __name__ == "__main__":
    unittest.main()
