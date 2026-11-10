"""Class-based functional tests for the Flask classification flow."""

import unittest
from pathlib import Path
from unittest.mock import patch

from segmenta_rfm_atlas.config import Settings
from segmenta_rfm_atlas.web import (
    AtlasInsertStore,
    ClassificationService,
    FlaskApplicationFactory,
    InputValidationError,
    ModelSegmentPredictor,
    RFMInputValidator,
    SegmentView,
    TrainingRangeError,
)


class FakePredictor:
    def __init__(self, ranges=None):
        self.ranges = ranges or {"recency": (0.0, 30.0), "frequency": (1.0, 10.0), "monetary": (0.0, 100.0)}
        self.prediction_calls = 0

    def find_out_of_range(self, values):
        return [f"{name} is outside the training range" for name, bounds in self.ranges.items() if not bounds[0] <= values[name] <= bounds[1]]

    def predict(self, values):
        self.prediction_calls += 1
        return 2


class FakeInsertStore:
    def __init__(self, error=None):
        self.documents = []
        self.error = error

    def insert_classification(self, values, segment):
        if self.error:
            raise self.error
        self.documents.append((dict(values), segment))


class RFMInputValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = RFMInputValidator()

    def test_accepts_valid_values_and_normalizes_types(self):
        values = self.validator.validate({"recency": "3", "frequency": "2", "monetary": "19.5"})
        self.assertEqual(values, {"recency": 3.0, "frequency": 2, "monetary": 19.5})

    def test_rejects_missing_text_nonfinite_negative_and_fractional_frequency(self):
        invalid = [
            ({"recency": "", "frequency": "2", "monetary": "2"}, "obligatorio"),
            ({"recency": "x", "frequency": "2", "monetary": "2"}, "número"),
            ({"recency": "inf", "frequency": "2", "monetary": "2"}, "finito"),
            ({"recency": "-1", "frequency": "2", "monetary": "2"}, "negativo"),
            ({"recency": "1", "frequency": "1.5", "monetary": "2"}, "entero positivo"),
        ]
        for payload, message in invalid:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(InputValidationError, message):
                    self.validator.validate(payload)


class ClassificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.predictor = FakePredictor()
        self.store = FakeInsertStore()

    def test_valid_submission_predicts_and_inserts_exactly_once(self):
        service = ClassificationService(RFMInputValidator(), self.predictor, self.store)
        result = service.classify({"recency": "5", "frequency": "2", "monetary": "25"})
        self.assertEqual(result.segment, 2)
        self.assertEqual(self.predictor.prediction_calls, 1)
        self.assertEqual(self.store.documents, [({"recency": 5.0, "frequency": 2, "monetary": 25.0}, 2)])

    def test_invalid_values_do_not_predict_or_insert(self):
        service = ClassificationService(RFMInputValidator(), self.predictor, self.store)
        with self.assertRaises(InputValidationError):
            service.classify({"recency": "bad", "frequency": "2", "monetary": "25"})
        self.assertEqual(self.predictor.prediction_calls, 0)
        self.assertEqual(self.store.documents, [])

    def test_default_range_policy_rejects_before_prediction_or_insert(self):
        service = ClassificationService(RFMInputValidator(), self.predictor, self.store)
        with self.assertRaises(TrainingRangeError):
            service.classify({"recency": "31", "frequency": "2", "monetary": "25"})
        self.assertEqual(self.predictor.prediction_calls, 0)
        self.assertEqual(self.store.documents, [])

    def test_warning_policy_returns_warning_and_continues(self):
        service = ClassificationService(RFMInputValidator(), self.predictor, self.store, "warn")
        result = service.classify({"recency": "31", "frequency": "2", "monetary": "25"})
        self.assertEqual(result.segment, 2)
        self.assertTrue(result.warnings)
        self.assertEqual(len(self.store.documents), 1)

    def test_invalid_range_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "out_of_range_policy"):
            ClassificationService(RFMInputValidator(), self.predictor, self.store, "ignore")

    def test_store_failure_propagates_after_one_attempt(self):
        store = FakeInsertStore(RuntimeError("Atlas offline"))
        service = ClassificationService(RFMInputValidator(), self.predictor, store)
        with self.assertRaisesRegex(RuntimeError, "Atlas offline"):
            service.classify({"recency": "5", "frequency": "2", "monetary": "25"})
        self.assertEqual(self.predictor.prediction_calls, 1)


class FlaskViewTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeInsertStore()
        self.predictor = FakePredictor()
        self.service = ClassificationService(RFMInputValidator(), self.predictor, self.store)
        settings = Settings(Path("unused.joblib"), "reject", "", "db", "collection", "test-key")
        self.client = FlaskApplicationFactory(settings=settings, service=self.service).create().test_client()

    def test_get_returns_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="recency"', response.data)
        self.assertIn(b'name="frequency"', response.data)
        self.assertIn(b'name="monetary"', response.data)

    def test_post_valid_submission_displays_segment(self):
        response = self.client.post("/", data={"recency": "5", "frequency": "2", "monetary": "25"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Cliente asignado", response.data)
        self.assertIn(b">2</strong>", response.data)
        self.assertEqual(len(self.store.documents), 1)

    def test_post_invalid_submission_returns_error_without_insert(self):
        response = self.client.post("/", data={"recency": "-1", "frequency": "2", "monetary": "25"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"no puede ser negativo", response.data)
        self.assertEqual(self.store.documents, [])

    def test_atlas_failure_does_not_claim_success(self):
        failing_service = ClassificationService(
            RFMInputValidator(), self.predictor, FakeInsertStore(RuntimeError("offline"))
        )
        settings = Settings(Path("unused.joblib"), "reject", "", "db", "collection", "test-key")
        response = FlaskApplicationFactory(settings=settings, service=failing_service).create().test_client().post(
            "/", data={"recency": "5", "frequency": "2", "monetary": "25"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No se pudo guardar la predicciÃ³n", response.data)
        self.assertNotIn(b"Cliente asignado", response.data)


class ModelLoadingTests(unittest.TestCase):
    def test_application_loads_existing_artifact_without_calling_fit(self):
        import tempfile
        from sklearn.cluster import KMeans
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from segmenta_rfm_atlas.modeling import FEATURES, RFMModelArtifact, RFMModelTrainer

        pipeline = Pipeline([("scaler", StandardScaler()), ("kmeans", KMeans(n_clusters=2))])
        artifact = RFMModelArtifact(
            pipeline=pipeline,
            feature_names=FEATURES,
            training_ranges={"recency": (0, 10), "frequency": (1, 4), "monetary": (0, 20)},
            training_parameters={"n_clusters": 2, "random_state": 42, "n_init": 10},
            cluster_selection=[{"n_clusters": 2, "inertia": 0.0, "silhouette": 0.5}],
            segment_metadata={
                "0": {"segment_id": 0, "customer_count": 1, "centroid": {"recency": 1.0, "frequency": 2.0, "monetary": 3.0}},
                "1": {"segment_id": 1, "customer_count": 1, "centroid": {"recency": 5.0, "frequency": 3.0, "monetary": 8.0}},
            },
            dataset_metadata={"dataset_id": 352, "transaction_count": 541_909, "source": "test fixture"},
            sklearn_version=__import__("sklearn").__version__,
        )
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.joblib"
            model_path.touch()
            settings = Settings(model_path, "reject", "mongodb://test", "db", "collection", "key")
            with patch.object(RFMModelTrainer, "load_artifact", return_value=artifact) as load_artifact:
                with patch("segmenta_rfm_atlas.web.AtlasInsertStore"):
                    FlaskApplicationFactory(settings=settings).create()
            load_artifact.assert_called_once_with(model_path)
            with patch.object(RFMModelTrainer, "fit") as fit:
                with patch.object(RFMModelTrainer, "load_artifact", return_value=artifact):
                    with patch("segmenta_rfm_atlas.web.AtlasInsertStore"):
                        FlaskApplicationFactory(settings=settings).create()
                fit.assert_not_called()


class AtlasInsertStoreTests(unittest.TestCase):
    def test_only_exposes_insert_method_and_writes_minimal_payload_once(self):
        settings = Settings(Path("unused.joblib"), "reject", "mongodb://example", "db", "records", "key")
        collection = type("CollectionDouble", (), {"insert_one": unittest.mock.Mock()})()
        database = {"records": collection}
        client = type("ClientDouble", (), {"__getitem__": lambda self, key: database})()
        with patch("segmenta_rfm_atlas.web.MongoClient", return_value=client):
            store = AtlasInsertStore(settings)
        store.insert_classification({"recency": 1, "frequency": 2, "monetary": 3}, 4)
        collection.insert_one.assert_called_once_with({"recency": 1.0, "frequency": 2, "monetary": 3.0, "segment": 4})
        public_methods = {name for name in dir(AtlasInsertStore) if not name.startswith("_") and callable(getattr(AtlasInsertStore, name))}
        self.assertEqual(public_methods, {"insert_classification"})


if __name__ == "__main__":
    unittest.main()
