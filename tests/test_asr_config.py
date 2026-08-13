import importlib
import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASR_ROOT = PROJECT_ROOT / "HDZB_ASR"
if str(ASR_ROOT) not in sys.path:
    sys.path.insert(0, str(ASR_ROOT))


class AsrConfigTest(unittest.TestCase):
    def test_reads_runtime_settings_from_environment(self):
        overrides = {
            "ASR_SERVER_HOST": "127.0.0.1",
            "ASR_SERVER_PORT": "18015",
            "COMPANION_SERVICE_URL": "http://companion.test",
            "AGENT_SERVICE_URL": "http://agent.test",
            "SAVE_FILE_DIR": "/tmp/hdzb-uploads",
        }
        original_values = {key: os.environ.get(key) for key in overrides}

        try:
            os.environ.update(overrides)

            from core import config

            importlib.reload(config)

            self.assertEqual(config.HOST, "127.0.0.1")
            self.assertEqual(config.PORT, 18015)
            self.assertEqual(config.COMPANION_SERVICE_URL, "http://companion.test")
            self.assertEqual(config.AGENT_SERVICE_URL, "http://agent.test")
            self.assertEqual(config.SAVE_FILE_DIR, "/tmp/hdzb-uploads")
        finally:
            for key, value in original_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

            if "core.config" in sys.modules:
                importlib.reload(sys.modules["core.config"])


if __name__ == "__main__":
    unittest.main()
