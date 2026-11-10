"""Structural validation only; never train a final model with fixture data."""

import json
from pathlib import Path
import unittest

import nbformat


class TrainingNotebookTests(unittest.TestCase):
    def test_notebook_format_and_python_cell_syntax_are_valid(self):
        notebook_path = Path(__file__).parents[1] / "notebooks" / "train_rfm_kmeans.ipynb"
        notebook = nbformat.read(notebook_path, as_version=4)
        nbformat.validate(notebook)
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type == "code":
                compile(cell.source, f"{notebook_path}:cell-{index}", "exec")
                self.assertEqual(cell.execution_count, None)
                self.assertEqual(cell.outputs, [])

    def test_notebook_requires_uci_count_download_fallback_selection_and_artifact(self):
        notebook_path = Path(__file__).parents[1] / "notebooks" / "train_rfm_kmeans.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )
        self.assertIn("OnlineRetailDatasetLoader()", source)
        self.assertIn("auto_download=True", source)
        self.assertIn("upload_manual_workbook", source)
        self.assertIn("EXPECTED_TRANSACTION_COUNT", source)
        self.assertIn("select_n_clusters", source)
        self.assertIn("dataset_metadata=dataset_metadata", source)
        self.assertIn("save_artifact", source)


if __name__ == "__main__":
    unittest.main()
