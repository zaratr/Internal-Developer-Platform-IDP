from typing import Dict, List

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.models import Deployment, EnvironmentTier, Service


class GuardrailEngine:
    def __init__(self):
        self.settings = get_settings()

    def validate_service_tags(self, tags: Dict[str, str]) -> None:
        missing = [tag for tag in self.settings.mandatory_tags if tag not in tags]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing mandatory tags: {', '.join(missing)}",
            )
        sensitivity = tags.get("data_sensitivity")
        if sensitivity and sensitivity not in self.settings.allowed_data_sensitivity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data_sensitivity tag value",
            )

    def validate_environment_promotion(self, environments: List[str], target: EnvironmentTier):
        order = [EnvironmentTier.dev, EnvironmentTier.staging, EnvironmentTier.prod]
        existing_set = {env.lower() for env in environments}
        for idx, tier in enumerate(order):
            if target == tier:
                required_previous = order[:idx]
                for prev in required_previous:
                    if prev.value not in existing_set:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Environment {prev.value} must exist before provisioning {target.value}",
                        )
                break

    def validate_production_deployment(self, deployment: Deployment, approvals: List[str]):
        if deployment.environment.tier == EnvironmentTier.prod and not approvals:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Production deployments require approvals",
            )

    def validate_config(self, config: Dict[str, str]) -> None:
        banned_keys = {"password", "secret", "token"}
        for key in config.keys():
            if key.lower() in banned_keys:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Restricted configuration key: {key}",
                )

    def enforce_service(self, service: Service) -> None:
        self.validate_service_tags(service.tags)
        self.validate_config(service.config or {})
