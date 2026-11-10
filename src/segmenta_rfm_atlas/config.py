"""Environment-backed application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    model_path: Path
    out_of_range_policy: str
    mongo_uri: str
    mongo_database: str
    mongo_collection: str
    secret_key: str

    @classmethod
    def from_environment(cls) -> "Settings":
        policy = os.getenv("OUT_OF_RANGE_POLICY", "reject").strip().lower()
        if policy not in {"reject", "warn"}:
            raise ValueError("OUT_OF_RANGE_POLICY must be 'reject' or 'warn'.")
        return cls(
            model_path=Path(os.getenv("MODEL_PATH", "artifacts/rfm_kmeans.joblib")),
            out_of_range_policy=policy,
            mongo_uri=os.getenv("MONGO_URI", ""),
            mongo_database=os.getenv("MONGO_DATABASE", "segmenta_rfm"),
            mongo_collection=os.getenv("MONGO_COLLECTION", "predicciones"),
            secret_key=os.getenv("FLASK_SECRET_KEY", ""),
        )

    def validate_for_web(self) -> None:
        if not self.mongo_uri:
            raise ValueError("MONGO_URI must be configured in the runtime environment.")
        if not self.secret_key:
            raise ValueError("FLASK_SECRET_KEY must be configured in the runtime environment.")
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {self.model_path}")
