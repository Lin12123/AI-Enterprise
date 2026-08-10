import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.openai_config import get_openai_api_key, mask_api_key, redact_secrets, safe_exception_message


class TestOpenAiConfig(unittest.TestCase):
    def test_get_openai_api_key_reads_only_environment_variable(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-value"}, clear=False):
            self.assertEqual(get_openai_api_key(), "test-key-value")

    def test_missing_openai_api_key_message_asks_user_to_set_env_var(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "请先设置环境变量 OPENAI_API_KEY"):
                get_openai_api_key()

    def test_mask_api_key_shows_only_first_6_and_last_4(self):
        masked = mask_api_key("abcdef1234567890wxyz")

        self.assertEqual(masked, "abcdef***wxyz")
        self.assertNotIn("1234567890", masked)

    def test_mask_api_key_handles_missing_or_short_values(self):
        self.assertEqual(mask_api_key(None), "not set")
        self.assertEqual(mask_api_key("short"), "***")

    def test_redact_secrets_removes_key_like_values(self):
        redacted = redact_secrets(
            "OPENAI_API_KEY=secretvalue12345 Authorization: Bearer anothersecret12345"
        )

        self.assertIn("OPENAI_API_KEY=[redacted]", redacted)
        self.assertIn("Authorization: Bearer [redacted]", redacted)
        self.assertNotIn("secretvalue", redacted)
        self.assertNotIn("anothersecret", redacted)

    def test_safe_exception_message_does_not_include_full_key(self):
        message = safe_exception_message(RuntimeError("failed with OPENAI_API_KEY=secretvalue12345"))

        self.assertIn("RuntimeError", message)
        self.assertIn("[redacted]", message)
        self.assertNotIn("secretvalue", message)


if __name__ == "__main__":
    unittest.main()
