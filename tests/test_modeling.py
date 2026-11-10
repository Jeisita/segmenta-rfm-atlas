"""Functional tests for RFM preparation and the reusable model pipeline."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import numpy as np

from segmenta_rfm_atlas.modeling import (
    FEATURES,
    RFMDataPreparer,
    RFMModelArtifact,
    RFMModelTrainer,
)
from segmenta_rfm_atlas.web import (
    ClassificationService,
    ModelSegmentPredictor,
    RFMInputValidator,
)


class RFMDataPreparerTests(unittest.TestCase):
    def setUp(self):
        self.transactions = pd.DataFrame(
            [
                {"CustomerID": 1001, "InvoiceDate": "2011-01-01 10:00", "InvoiceNo": "A1", "Quantity": 2, "UnitPrice": 5},
                {"CustomerID": 1001, "InvoiceDate": "2011-01-02 10:00", "InvoiceNo": "A1", "Quantity": 1, "UnitPrice": 5},
                {"CustomerID": 1001, "InvoiceDate": "2011-01-02 11:00", "InvoiceNo": "A2", "Quantity": 1, "UnitPrice": 10},
                {"CustomerID": 1002, "InvoiceDate": "2011-01-01 10:00", "InvoiceNo": "A3", "Quantity": 3, "UnitPrice": 2},
                {"CustomerID": 1002, "InvoiceDate": "2011-01-03 10:00", "InvoiceNo": "C4", "Quantity": 1, "UnitPrice": 2},
                {"CustomerID": 1002, "InvoiceDate": "2011-01-03 10:00", "InvoiceNo": "A5", "Quantity": -1, "UnitPrice": 2},
            ]
        )

    def test_aggregates_recency_distinct_invoices_and_spend(self):
        rfm = RFMDataPreparer().prepare(self.transactions)
        self.assertEqual(tuple(rfm.columns), FEATURES)
        self.assertEqual(rfm.loc[1001, "recency"], 1)
        self.assertEqual(rfm.loc[1001, "frequency"], 2)
        self.assertEqual(rfm.loc[1001, "monetary"], 25)
        self.assertEqual(list(rfm.index), [1001, 1002])
        self.assertEqual(rfm.loc[1002, "frequency"], 1)

    def test_missing_source_columns_raise_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            RFMDataPreparer().prepare(pd.DataFrame({"CustomerID": [1]}))


class RFMModelTrainerTests(unittest.TestCase):
    def setUp(self):
        self.rfm = pd.DataFrame(
            {
                "recency": [1, 2, 10, 11, 30, 31],
                "frequency": [10, 9, 5, 4, 1, 2],
                "monetary": [100.0, 90.0, 50.0, 45.0, 10.0, 12.0],
            }
        )

    def test_pipeline_contains_scaler_then_kmeans_and_evaluates(self):
        trainer = RFMModelTrainer(n_clusters=2, random_state=7)
        pipeline = trainer.fit(self.rfm)
        metrics = trainer.evaluate(self.rfm)
        self.assertEqual(list(pipeline.named_steps), ["scaler", "kmeans"])
        self.assertIn("inertia", metrics)
        self.assertIn("silhouette", metrics)
        self.assertEqual(metrics["n_clusters"], 2)

    def test_saved_artifact_round_trip_preserves_predictions_and_ranges(self):
        trainer = RFMModelTrainer(n_clusters=2, random_state=7)
        trainer.select_n_clusters(self.rfm, candidates=[2])
        trainer.fit(self.rfm)
        artifact = trainer.create_artifact(self.rfm)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            trainer.save_artifact(artifact, path, allow_test_artifact=True)
            loaded = trainer.load_artifact(path, allow_test_artifact=True)
        self.assertIsInstance(loaded, RFMModelArtifact)
        self.assertEqual(loaded.feature_names, FEATURES)
        self.assertEqual(loaded.training_ranges["recency"], (1.0, 31.0))
        self.assertEqual(loaded.training_parameters["n_clusters"], 2)
        self.assertEqual(sum(item["customer_count"] for item in loaded.segment_metadata.values()), len(self.rfm))
        self.assertTrue(all(set(item["centroid"]) == set(FEATURES) for item in loaded.segment_metadata.values()))
        self.assertEqual(loaded.cluster_selection[0]["n_clusters"], 2)
        np.testing.assert_array_equal(
            trainer.pipeline.predict(self.rfm),
            loaded.pipeline.predict(self.rfm),
        )
        predictor = ModelSegmentPredictor(loaded)
        self.assertEqual(
            predictor.predict({"recency": 1, "frequency": 10, "monetary": 100}),
            int(loaded.pipeline.predict(self.rfm.iloc[[0]])[0]),
        )

    def test_malformed_artifact_is_rejected(self):
        trainer = RFMModelTrainer(n_clusters=2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.joblib"
            trainer.save_artifact("not-an-artifact", path, allow_test_artifact=True)
            with self.assertRaisesRegex(ValueError, "supported RFMModelArtifact"):
                trainer.load_artifact(path, allow_test_artifact=True)

    def test_wrong_feature_order_is_rejected(self):
        trainer = RFMModelTrainer(n_clusters=2)
        with self.assertRaisesRegex(ValueError, "ordered"):
            trainer.fit(self.rfm[["frequency", "recency", "monetary"]])

    def test_loaded_artifact_drives_inference_and_same_training_ranges(self):
        trainer = RFMModelTrainer(n_clusters=2, random_state=7)
        trainer.select_n_clusters(self.rfm, candidates=[2])
        trainer.fit(self.rfm)
        artifact = trainer.create_artifact(self.rfm)

        class InsertDouble:
            def __init__(self):
                self.calls = []

            def insert_classification(self, values, segment):
                self.calls.append((dict(values), segment))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            trainer.save_artifact(artifact, path, allow_test_artifact=True)
            loaded = RFMModelTrainer.load_artifact(path, allow_test_artifact=True)
        insert_double = InsertDouble()
        service = ClassificationService(
            RFMInputValidator(), ModelSegmentPredictor(loaded), insert_double
        )
        first = self.rfm.iloc[0]
        result = service.classify({name: str(first[name]) for name in FEATURES})
        self.assertEqual(result.segment, int(loaded.pipeline.predict(self.rfm.iloc[[0]])[0]))
        self.assertFalse(result.warnings)
        self.assertEqual(len(insert_double.calls), 1)
        self.assertEqual(loaded.training_ranges, artifact.training_ranges)

    def test_final_artifact_export_rejects_non_uci_training_metadata(self):
        trainer = RFMModelTrainer(n_clusters=2, random_state=7)
        trainer.select_n_clusters(self.rfm, candidates=[2])
        trainer.fit(self.rfm)
        artifact = trainer.create_artifact(self.rfm, dataset_metadata={"source": "unit-test-fixture"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "final-model.joblib"
            with self.assertRaisesRegex(ValueError, "must record UCI Online Retail"):
                trainer.save_artifact(artifact, path)
            self.assertFalse(path.exists())

    def test_cluster_selection_uses_computed_silhouette_and_smallest_k_tie_break(self):
        trainer = RFMModelTrainer(random_state=7)
        selection = trainer.evaluate_cluster_candidates(self.rfm, candidates=[2, 3])
        chosen = trainer.select_n_clusters(self.rfm, candidates=[2, 3])
        best_score = selection["silhouette"].max()
        expected = int(selection.loc[selection["silhouette"] == best_score, "n_clusters"].min())
        self.assertEqual(chosen, expected)
        self.assertEqual(trainer.cluster_selection[0]["n_clusters"], 2)


if __name__ == "__main__":
    unittest.main()
