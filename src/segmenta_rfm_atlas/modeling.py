"""Class-based RFM preparation, training, evaluation, and artifact handling."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = ("recency", "frequency", "monetary")


class RFMDataPreparer:
    """Aggregate Online Retail transactions to one customer-level RFM row."""

    REQUIRED_COLUMNS = ("CustomerID", "InvoiceDate", "InvoiceNo", "Quantity", "UnitPrice")

    def prepare(self, transactions: pd.DataFrame) -> pd.DataFrame:
        missing = [name for name in self.REQUIRED_COLUMNS if name not in transactions.columns]
        if missing:
            raise ValueError(f"Missing required Online Retail columns: {', '.join(missing)}")
        frame = transactions.loc[:, list(self.REQUIRED_COLUMNS)].copy()
        frame = frame.dropna(subset=self.REQUIRED_COLUMNS)
        frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"], errors="coerce", utc=True)
        frame["CustomerID"] = pd.to_numeric(frame["CustomerID"], errors="coerce")
        frame["Quantity"] = pd.to_numeric(frame["Quantity"], errors="coerce")
        frame["UnitPrice"] = pd.to_numeric(frame["UnitPrice"], errors="coerce")
        frame = frame.dropna(subset=["InvoiceDate", "CustomerID", "Quantity", "UnitPrice"])
        # UCI UnitPrice is in GBP; exclude cancellations and non-positive quantities.
        frame = frame.loc[
            ~frame["InvoiceNo"].astype(str).str.upper().str.startswith("C")
            & (frame["Quantity"] > 0)
            & (frame["UnitPrice"] >= 0)
        ]
        if frame.empty:
            raise ValueError("No valid transactions remain after cleaning.")
        frame["line_value"] = frame["Quantity"] * frame["UnitPrice"]
        snapshot = frame["InvoiceDate"].max().normalize() + pd.DateOffset(days=1)
        grouped = frame.groupby("CustomerID", sort=True).agg(
            last_purchase=("InvoiceDate", "max"),
            frequency=("InvoiceNo", "nunique"),
            monetary=("line_value", "sum"),
        )
        result = pd.DataFrame(index=grouped.index)
        result["recency"] = (snapshot - grouped["last_purchase"].dt.normalize()).dt.days
        result["frequency"] = grouped["frequency"].astype(float)
        result["monetary"] = grouped["monetary"].astype(float)
        result.index.name = "CustomerID"
        if (result[list(FEATURES)] < 0).any().any() or not np.isfinite(result[list(FEATURES)]).all().all():
            raise ValueError("Prepared RFM features must be finite and non-negative.")
        return result.loc[:, list(FEATURES)]


@dataclass
class RFMModelArtifact:
    pipeline: Pipeline
    feature_names: tuple[str, ...]
    training_ranges: dict[str, tuple[float, float]]
    training_parameters: dict[str, Any]
    cluster_selection: list[dict[str, float | int | None]]
    segment_metadata: dict[str, dict[str, Any]]
    dataset_metadata: dict[str, Any]
    sklearn_version: str


class RFMModelTrainer:
    """Fit and evaluate a scaler-plus-K-Means pipeline."""

    def __init__(
        self,
        n_clusters: int | None = None,
        random_state: int = 42,
        n_init: int = 10,
    ) -> None:
        if n_clusters is not None and n_clusters < 2:
            raise ValueError("n_clusters must be at least 2.")
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.n_init = n_init
        self.pipeline: Pipeline | None = None
        self.cluster_selection: list[dict[str, float | int | None]] = []
        self.selected_n_clusters: int | None = None

    def evaluate_cluster_candidates(
        self,
        rfm: pd.DataFrame,
        candidates: Iterable[int] = range(2, 11),
    ) -> pd.DataFrame:
        """Calculate inertia and silhouette for each valid candidate k."""
        self._validate_frame(rfm)
        scaled = StandardScaler().fit_transform(rfm.loc[:, list(FEATURES)])
        rows: list[dict[str, float | int | None]] = []
        for candidate in candidates:
            if candidate < 2 or candidate >= len(rfm):
                continue
            estimator = KMeans(
                n_clusters=int(candidate),
                random_state=self.random_state,
                n_init=self.n_init,
            )
            labels = estimator.fit_predict(scaled)
            silhouette = None
            if 1 < len(set(labels)) < len(labels):
                silhouette = float(silhouette_score(scaled, labels))
            rows.append(
                {
                    "n_clusters": int(candidate),
                    "inertia": float(estimator.inertia_),
                    "silhouette": silhouette,
                }
            )
        if not rows:
            raise ValueError("At least one valid cluster candidate is required.")
        self.cluster_selection = rows
        return pd.DataFrame(rows)

    def select_n_clusters(
        self,
        rfm: pd.DataFrame,
        candidates: Iterable[int] = range(2, 11),
    ) -> int:
        """Choose the highest-silhouette candidate, breaking ties by lower k."""
        selection = self.evaluate_cluster_candidates(rfm, candidates)
        measurable = selection.dropna(subset=["silhouette"])
        if measurable.empty:
            raise ValueError("No candidate produced a valid silhouette score.")
        best = measurable.sort_values(
            ["silhouette", "n_clusters"], ascending=[False, True], kind="stable"
        ).iloc[0]
        self.n_clusters = int(best["n_clusters"])
        self.selected_n_clusters = self.n_clusters
        return self.n_clusters

    def fit(self, rfm: pd.DataFrame) -> Pipeline:
        self._validate_frame(rfm)
        if self.n_clusters is None:
            raise RuntimeError("Call select_n_clusters before fitting the final model.")
        if len(rfm) < self.n_clusters:
            raise ValueError("Training rows must be at least the number of clusters.")
        self.pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("kmeans", KMeans(
                    n_clusters=self.n_clusters,
                    random_state=self.random_state,
                    n_init=self.n_init,
                )),
            ]
        )
        self.pipeline.fit(rfm.loc[:, list(FEATURES)])
        return self.pipeline

    def evaluate(self, rfm: pd.DataFrame) -> dict[str, Any]:
        if self.pipeline is None:
            raise RuntimeError("Call fit before evaluate.")
        labels = self.pipeline.predict(rfm.loc[:, list(FEATURES)])
        model = self.pipeline.named_steps["kmeans"]
        result: dict[str, Any] = {
            "inertia": float(model.inertia_),
            "n_clusters": int(model.n_clusters),
            "cluster_counts": pd.Series(labels).value_counts().sort_index().to_dict(),
        }
        if len(set(labels)) > 1 and len(set(labels)) < len(labels):
            scaled = self.pipeline.named_steps["scaler"].transform(rfm.loc[:, list(FEATURES)])
            result["silhouette"] = float(silhouette_score(scaled, labels))
        else:
            result["silhouette"] = None
        return result

    def create_artifact(
        self,
        rfm: pd.DataFrame,
        dataset_metadata: dict[str, Any] | None = None,
    ) -> RFMModelArtifact:
        if self.pipeline is None:
            raise RuntimeError("Call fit before creating an artifact.")
        if self.selected_n_clusters != self.n_clusters or not self.cluster_selection:
            raise RuntimeError("Select the cluster count before creating the final artifact.")
        self._validate_frame(rfm)
        ranges = {
            feature: (float(rfm[feature].min()), float(rfm[feature].max()))
            for feature in FEATURES
        }
        model = self.pipeline.named_steps["kmeans"]
        centers = self.pipeline.named_steps["scaler"].inverse_transform(model.cluster_centers_)
        labels = self.pipeline.predict(rfm.loc[:, list(FEATURES)])
        segment_metadata: dict[str, dict[str, Any]] = {}
        for label in range(model.n_clusters):
            segment_metadata[str(label)] = {
                "segment_id": int(label),
                "customer_count": int(np.count_nonzero(labels == label)),
                "centroid": {
                    feature: float(centers[label, column_index])
                    for column_index, feature in enumerate(FEATURES)
                },
            }
        return RFMModelArtifact(
            pipeline=self.pipeline,
            feature_names=FEATURES,
            training_ranges=ranges,
            training_parameters={
                "n_clusters": self.n_clusters,
                "random_state": self.random_state,
                "n_init": self.n_init,
                "selection_criterion": "maximum_silhouette_then_smallest_k",
            },
            cluster_selection=list(self.cluster_selection),
            segment_metadata=segment_metadata,
            dataset_metadata=dict(dataset_metadata or {"dataset_name": "unspecified"}),
            sklearn_version=sklearn.__version__,
        )

    @staticmethod
    def save_artifact(
        artifact: RFMModelArtifact,
        path: Path,
        allow_test_artifact: bool = False,
    ) -> None:
        if not allow_test_artifact:
            RFMModelTrainer._validate_official_dataset_metadata(artifact.dataset_metadata)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, path)

    @staticmethod
    def load_artifact(path: Path, allow_test_artifact: bool = False) -> RFMModelArtifact:
        artifact = joblib.load(path)
        if not isinstance(artifact, RFMModelArtifact):
            raise ValueError("Model file does not contain a supported RFMModelArtifact.")
        if artifact.feature_names != FEATURES:
            raise ValueError("Model artifact has an incompatible RFM feature order.")
        if not isinstance(artifact.pipeline, Pipeline) or not {"scaler", "kmeans"}.issubset(artifact.pipeline.named_steps):
            raise ValueError("Model artifact must include scaler and K-Means steps.")
        if artifact.sklearn_version.split(".")[:2] != sklearn.__version__.split(".")[:2]:
            raise ValueError(
                "Model artifact scikit-learn version is incompatible with the runtime "
                f"({artifact.sklearn_version} vs {sklearn.__version__})."
            )
        if set(artifact.training_ranges) != set(FEATURES):
            raise ValueError("Model artifact is missing training ranges for RFM features.")
        if not artifact.segment_metadata or set(artifact.segment_metadata) != {
            str(index) for index in range(artifact.training_parameters["n_clusters"])
        }:
            raise ValueError("Model artifact is missing per-segment metadata.")
        if not allow_test_artifact:
            RFMModelTrainer._validate_official_dataset_metadata(artifact.dataset_metadata)
        return artifact

    @staticmethod
    def _validate_official_dataset_metadata(metadata: dict[str, Any]) -> None:
        digest = str(metadata.get("sha256", ""))
        if (
            metadata.get("dataset_id") != 352
            or metadata.get("dataset_name") != "Online Retail"
            or metadata.get("transaction_count") != 541_909
            or metadata.get("source") not in {"uci-official-download", "local-uci-workbook"}
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise ValueError(
                "Final model artifacts must record UCI Online Retail dataset 352, "
                "541,909 transactions, an accepted UCI acquisition method, and the workbook SHA-256."
            )

    @staticmethod
    def _validate_frame(rfm: pd.DataFrame) -> None:
        if tuple(rfm.columns) != FEATURES:
            raise ValueError(f"RFM columns must be ordered as {FEATURES}.")
        if rfm.empty or not np.isfinite(rfm.to_numpy(dtype=float)).all():
            raise ValueError("RFM data must be non-empty and finite.")
        if (rfm < 0).any().any():
            raise ValueError("RFM values must be non-negative.")
