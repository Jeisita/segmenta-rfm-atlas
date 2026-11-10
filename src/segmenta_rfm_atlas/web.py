"""Flask web layer and class-based RFM classification services."""

from dataclasses import dataclass
import math
from typing import Mapping

from flask import Flask, current_app, render_template, request, url_for
from flask.views import MethodView
import pandas as pd
from pymongo import MongoClient

from .config import Settings
from .modeling import FEATURES, RFMModelArtifact, RFMModelTrainer


class InputValidationError(ValueError):
    """Raised for a malformed or domain-invalid RFM form submission."""


class TrainingRangeError(ValueError):
    """Raised when the configured policy rejects a value outside training bounds."""


class RFMInputValidator:
    """Parse and validate form values using the RFM domain constraints."""

    def validate(self, values: Mapping[str, str]) -> dict[str, float | int]:
        parsed: dict[str, float | int] = {}
        labels = {
            "recency": "Recencia",
            "frequency": "Frecuencia",
            "monetary": "Valor monetario",
        }
        for feature in FEATURES:
            label = labels[feature]
            raw_value = values.get(feature, "")
            if raw_value is None or not str(raw_value).strip():
                raise InputValidationError(f"{label} es obligatorio.")
            try:
                number = float(raw_value)
            except (TypeError, ValueError) as error:
                raise InputValidationError(f"{label} debe ser un número.") from error
            if not math.isfinite(number):
                raise InputValidationError(f"{label} debe ser un valor finito.")
            if number < 0:
                raise InputValidationError(f"{label} no puede ser negativo.")
            if feature == "frequency":
                if not number.is_integer() or number < 1:
                    raise InputValidationError("La frecuencia debe ser un entero positivo.")
                parsed[feature] = int(number)
            else:
                parsed[feature] = number
        return parsed


class ModelSegmentPredictor:
    """Run inference with a previously trained scaler and K-Means pipeline."""

    def __init__(self, artifact: RFMModelArtifact) -> None:
        self.artifact = artifact

    def predict(self, values: Mapping[str, float | int]) -> int:
        ordered = pd.DataFrame(
            [[float(values[name]) for name in self.artifact.feature_names]],
            columns=list(self.artifact.feature_names),
        )
        return int(self.artifact.pipeline.predict(ordered)[0])

    def find_out_of_range(self, values: Mapping[str, float | int]) -> list[str]:
        outside = []
        labels = {
            "recency": "La recencia",
            "frequency": "La frecuencia",
            "monetary": "El valor monetario",
        }
        for name in self.artifact.feature_names:
            minimum, maximum = self.artifact.training_ranges[name]
            value = float(values[name])
            if value < minimum or value > maximum:
                outside.append(
                    f"{labels[name]} está fuera del rango de entrenamiento "
                    f"[{minimum:g}, {maximum:g}]"
                )
        return outside


class AtlasInsertStore:
    """MongoDB Atlas adapter exposing only one insert operation."""

    def __init__(self, settings: Settings) -> None:
        if not settings.mongo_uri:
            raise ValueError("MONGO_URI must be configured in the runtime environment.")
        self._client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
        self._collection = self._client[settings.mongo_database][settings.mongo_collection]

    def insert_classification(self, values: Mapping[str, float | int], segment: int) -> None:
        document = {
            "recency": float(values["recency"]),
            "frequency": int(values["frequency"]),
            "monetary": float(values["monetary"]),
            "segment": int(segment),
        }
        self._collection.insert_one(document)


@dataclass(frozen=True)
class ClassificationResult:
    values: dict[str, float | int]
    segment: int
    warnings: tuple[str, ...]


class ClassificationService:
    """Coordinate Python validation, range policy, inference, and one insert."""

    def __init__(
        self,
        validator: RFMInputValidator,
        predictor: ModelSegmentPredictor,
        store: AtlasInsertStore,
        out_of_range_policy: str = "reject",
    ) -> None:
        if out_of_range_policy not in {"reject", "warn"}:
            raise ValueError("out_of_range_policy must be 'reject' or 'warn'.")
        self.validator = validator
        self.predictor = predictor
        self.store = store
        self.out_of_range_policy = out_of_range_policy

    def classify(self, raw_values: Mapping[str, str]) -> ClassificationResult:
        values = self.validator.validate(raw_values)
        warnings = self.predictor.find_out_of_range(values)
        if warnings and self.out_of_range_policy == "reject":
            raise TrainingRangeError("Datos fuera del rango de entrenamiento: " + "; ".join(warnings))
        segment = self.predictor.predict(values)
        self.store.insert_classification(values, segment)
        return ClassificationResult(values=values, segment=segment, warnings=tuple(warnings))


class SegmentView(MethodView):
    """Server-rendered class-based form view."""

    def __init__(self, service: ClassificationService) -> None:
        self.service = service

    def get(self):
        return render_template(
            "index.html",
            values={},
            errors=(),
            warnings=(),
            result=None,
        )

    def post(self):
        values = {name: request.form.get(name, "") for name in FEATURES}
        try:
            result = self.service.classify(values)
        except (InputValidationError, TrainingRangeError) as error:
            return render_template(
                "index.html",
                values=values,
                errors=(str(error),),
                warnings=(),
                result=None,
            ), 400
        except Exception:
            current_app.logger.exception(
                "Classification failed during inference or MongoDB persistence."
            )
            return render_template(
                "index.html",
                values=values,
                errors=("No se pudo guardar la predicción. Revisa la conexión e inténtalo de nuevo.",),
                warnings=(),
                result=None,
            ), 503
        return render_template(
            "index.html",
            values=values,
            errors=(),
            warnings=result.warnings,
            result=result.segment,
        )


class FlaskApplicationFactory:
    """Build Flask and its services once from runtime configuration."""

    def __init__(
        self,
        settings: Settings | None = None,
        service: ClassificationService | None = None,
    ) -> None:
        self.settings = settings or Settings.from_environment()
        self.service = service

    def create(self) -> Flask:
        """Create the Flask app and load the existing model without fitting."""
        app = Flask(__name__)
        app.config["SECRET_KEY"] = self.settings.secret_key
        service = self.service
        if service is None:
            self.settings.validate_for_web()
            artifact = RFMModelTrainer.load_artifact(self.settings.model_path)
            service = ClassificationService(
                validator=RFMInputValidator(),
                predictor=ModelSegmentPredictor(artifact),
                store=AtlasInsertStore(self.settings),
                out_of_range_policy=self.settings.out_of_range_policy,
            )
        app.add_url_rule(
            "/", view_func=SegmentView.as_view("segment", service), methods=["GET", "POST"]
        )
        return app
