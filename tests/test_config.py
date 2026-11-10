"""Runtime configuration is read from the environment, never source constants."""

import os
import unittest
from unittest.mock import patch

from segmenta_rfm_atlas.config import Settings


class SettingsTests(unittest.TestCase):
    def test_reads_mongo_and_flask_secrets_from_environment(self):
        values = {
            "MODEL_PATH": "model.joblib",
            "OUT_OF_RANGE_POLICY": "warn",
            "MONGO_URI": "mongodb+srv://example.invalid/",
            "MONGO_DATABASE": "academic_demo",
            "MONGO_COLLECTION": "predictions",
            "FLASK_SECRET_KEY": "test-value-only",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = Settings.from_environment()
        self.assertEqual(settings.mongo_uri, values["MONGO_URI"])
        self.assertEqual(settings.secret_key, values["FLASK_SECRET_KEY"])
        self.assertEqual(settings.out_of_range_policy, "warn")

    def test_rejects_unrecognized_range_policy(self):
        with patch.dict(os.environ, {"OUT_OF_RANGE_POLICY": "ignore"}, clear=True):
            with self.assertRaisesRegex(ValueError, "OUT_OF_RANGE_POLICY"):
                Settings.from_environment()


if __name__ == "__main__":
    unittest.main()
