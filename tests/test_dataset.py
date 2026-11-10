"""Tests for UCI dataset acquisition and strict source-data validation."""

from io import BytesIO
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
import urllib.error
import zipfile
from unittest.mock import patch

import pandas as pd

from segmenta_rfm_atlas.dataset import DatasetLoadError, OnlineRetailDatasetLoader


class OnlineRetailDatasetLoaderTests(unittest.TestCase):
    def _workbook_bytes(self, row_count=3):
        rows = [
            {
                "InvoiceNo": f"I-{index}",
                "InvoiceDate": "2011-01-01",
                "Quantity": 1,
                "UnitPrice": 2.5,
                "CustomerID": index + 1,
            }
            for index in range(row_count)
        ]
        workbook = BytesIO()
        pd.DataFrame(rows).to_excel(workbook, index=False)
        return workbook.getvalue()

    def _zip_bytes(self, workbook_bytes):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("Online Retail.xlsx", workbook_bytes)
        return archive.getvalue()

    def test_downloads_official_uci_archive_and_records_provenance(self):
        loader = OnlineRetailDatasetLoader(expected_transaction_count=3)
        response = BytesIO(self._zip_bytes(self._workbook_bytes(3)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Online Retail.xlsx"
            with patch("segmenta_rfm_atlas.dataset.urllib.request.urlopen", return_value=response) as opener:
                result = loader.load(path)
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, OnlineRetailDatasetLoader.OFFICIAL_DOWNLOAD_URL)
        self.assertEqual(len(result.transactions), 3)
        self.assertEqual(result.metadata["dataset_id"], 352)
        self.assertEqual(result.metadata["transaction_count"], 3)
        self.assertEqual(len(result.metadata["sha256"]), 64)
        self.assertEqual(result.metadata["source"], "uci-official-download")

    def test_rejects_workbook_with_wrong_transaction_count(self):
        loader = OnlineRetailDatasetLoader(expected_transaction_count=4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Online Retail.xlsx"
            pd.DataFrame(
                {
                    "InvoiceNo": ["I-1", "I-2", "I-3"],
                    "InvoiceDate": ["2011-01-01"] * 3,
                    "Quantity": [1] * 3,
                    "UnitPrice": [2.0] * 3,
                    "CustomerID": [1, 2, 3],
                }
            ).to_excel(path, index=False)
            with self.assertRaisesRegex(DatasetLoadError, "expected exactly 4"):
                loader.load(path, auto_download=False)

    def test_download_failure_leaves_no_partial_workbook(self):
        loader = OnlineRetailDatasetLoader(expected_transaction_count=3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Online Retail.xlsx"
            with patch(
                "segmenta_rfm_atlas.dataset.urllib.request.urlopen",
                side_effect=urllib.error.URLError("offline"),
            ):
                with self.assertRaisesRegex(DatasetLoadError, "Could not download"):
                    loader.load(path)
            self.assertFalse(path.exists())

    def test_colab_manual_upload_accepts_official_workbook_name(self):
        loader = OnlineRetailDatasetLoader(expected_transaction_count=3)
        uploaded_bytes = self._workbook_bytes(3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Online Retail.xlsx"
            fake_files = SimpleNamespace(upload=lambda: {"Online Retail.xlsx": uploaded_bytes})
            fake_google = ModuleType("google")
            fake_colab = ModuleType("google.colab")
            fake_colab.files = fake_files
            with (
                patch.object(loader, "is_google_colab", return_value=True),
                patch.dict(sys.modules, {"google": fake_google, "google.colab": fake_colab}),
            ):
                loader.upload_manual_workbook(path)
            self.assertEqual(path.read_bytes(), uploaded_bytes)
            result = loader.load(path, auto_download=False)
            self.assertEqual(len(result.transactions), 3)
            self.assertEqual(result.metadata["source"], "local-uci-workbook")


if __name__ == "__main__":
    unittest.main()
