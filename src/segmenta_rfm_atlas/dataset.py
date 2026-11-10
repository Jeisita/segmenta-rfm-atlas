"""Acquisition and validation of the official UCI Online Retail workbook."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Any
import urllib.error
import urllib.request
import zipfile

import pandas as pd


class DatasetLoadError(RuntimeError):
    """Raised when the official workbook cannot be downloaded or validated."""


@dataclass(frozen=True)
class DatasetLoadResult:
    transactions: pd.DataFrame
    metadata: dict[str, Any]


class OnlineRetailDatasetLoader:
    """Download or load UCI dataset 352 and validate its transaction count."""

    OFFICIAL_DATASET_ID = 352
    OFFICIAL_DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
    EXPECTED_TRANSACTION_COUNT = 541_909
    REQUIRED_COLUMNS = ("InvoiceNo", "InvoiceDate", "Quantity", "UnitPrice", "CustomerID")

    def __init__(self, timeout_seconds: int = 90, expected_transaction_count: int | None = None):
        self.timeout_seconds = timeout_seconds
        self.expected_transaction_count = (
            expected_transaction_count
            if expected_transaction_count is not None
            else self.EXPECTED_TRANSACTION_COUNT
        )

    def load(self, workbook_path: Path, auto_download: bool = True) -> DatasetLoadResult:
        """Load the configured workbook, optionally downloading it from UCI."""
        workbook_path = Path(workbook_path)
        downloaded = False
        if not workbook_path.is_file():
            if not auto_download:
                raise DatasetLoadError(
                    f"Workbook not found at {workbook_path}. Upload the official "
                    "Online Retail.xlsx workbook and retry."
                )
            self.download_from_uci(workbook_path)
            downloaded = True
        try:
            transactions = pd.read_excel(workbook_path)
        except Exception as error:
            raise DatasetLoadError(f"Could not read Online Retail workbook: {error}") from error
        missing = [column for column in self.REQUIRED_COLUMNS if column not in transactions.columns]
        if missing:
            raise DatasetLoadError(f"Workbook is missing required UCI columns: {', '.join(missing)}")
        actual_count = len(transactions)
        if actual_count != self.expected_transaction_count:
            raise DatasetLoadError(
                "Rejected Online Retail workbook: expected exactly "
                f"{self.expected_transaction_count:,} transactions, found {actual_count:,}."
            )
        metadata = {
            "dataset_id": self.OFFICIAL_DATASET_ID,
            "dataset_name": "Online Retail",
            "source": "uci-official-download" if downloaded else "local-uci-workbook",
            "source_url": self.OFFICIAL_DOWNLOAD_URL,
            "transaction_count": actual_count,
            "sha256": self._sha256(workbook_path),
        }
        return DatasetLoadResult(transactions=transactions, metadata=metadata)

    def download_from_uci(self, workbook_path: Path) -> Path:
        """Fetch the official UCI ZIP and atomically extract its workbook."""
        workbook_path = Path(workbook_path)
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        extracted_path = workbook_path.with_name(workbook_path.name + ".part")
        try:
            with tempfile.TemporaryDirectory(dir=workbook_path.parent) as temporary_directory:
                archive_path = Path(temporary_directory) / "uci-online-retail.zip"
                request = urllib.request.Request(
                    self.OFFICIAL_DOWNLOAD_URL,
                    headers={"User-Agent": "Segmenta-RFM-Atlas/0.1 dataset loader"},
                )
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    with archive_path.open("wb") as archive_file:
                        shutil.copyfileobj(response, archive_file)
                with zipfile.ZipFile(archive_path) as archive:
                    workbook_member = next(
                        (
                            member
                            for member in archive.namelist()
                            if Path(member).name.casefold() == "online retail.xlsx"
                        ),
                        None,
                    )
                    if workbook_member is None:
                        raise DatasetLoadError("The official UCI archive did not contain Online Retail.xlsx.")
                    with archive.open(workbook_member) as source, extracted_path.open("wb") as target:
                        shutil.copyfileobj(source, target)
            extracted_path.replace(workbook_path)
        except (urllib.error.URLError, TimeoutError, zipfile.BadZipFile, OSError, StopIteration) as error:
            extracted_path.unlink(missing_ok=True)
            raise DatasetLoadError(f"Could not download/extract the official UCI workbook: {error}") from error
        except Exception:
            extracted_path.unlink(missing_ok=True)
            raise
        return workbook_path

    def upload_manual_workbook(self, workbook_path: Path) -> Path:
        """In Colab, upload the fallback workbook and save it at workbook_path."""
        if not self.is_google_colab():
            raise DatasetLoadError("Manual browser upload is available only in Google Colab.")
        from google.colab import files

        uploaded = files.upload()
        matching = [
            (filename, content)
            for filename, content in uploaded.items()
            if Path(filename).name.casefold() == "online retail.xlsx"
        ]
        if not matching:
            raise DatasetLoadError("Upload a file named exactly Online Retail.xlsx.")
        workbook_path = Path(workbook_path)
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        workbook_path.write_bytes(matching[0][1])
        return workbook_path

    @staticmethod
    def is_google_colab() -> bool:
        """Return whether this Python process is running in Google Colab."""
        import os

        return "COLAB_RELEASE_TAG" in os.environ

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as file_handle:
            for block in iter(lambda: file_handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
