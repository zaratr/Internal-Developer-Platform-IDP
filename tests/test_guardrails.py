import pytest
from fastapi import HTTPException

from app.platform.guardrails import GuardrailEngine
from app.models.models import EnvironmentTier


guardrails = GuardrailEngine()


def test_missing_tags_raises():
    with pytest.raises(HTTPException):
        guardrails.validate_service_tags({"owner": "team"})


def test_invalid_sensitivity():
    with pytest.raises(HTTPException):
        guardrails.validate_service_tags({"owner": "team", "data_sensitivity": "top_secret"})


def test_environment_promotion_blocks_prod_without_staging():
    with pytest.raises(HTTPException):
        guardrails.validate_environment_promotion(["dev"], EnvironmentTier.prod)
