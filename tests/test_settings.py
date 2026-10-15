import pytest
from atlasrec_api.settings import Settings
from pydantic import ValidationError


def test_production_rejects_documented_demo_identity():
    config = dict(_env_file=None, ATLASREC_PROFILE="research", ATLASREC_ENV="production",
                  database_url="postgresql+psycopg://ops:fresh-secret@db/atlasrec",
                  cookie_secure=True, allowed_origins="https://atlasrec.example")
    with pytest.raises(ValidationError, match="demo admin credentials"):
        Settings(**config)
    valid = Settings(**config, demo_admin_email="ops@atlasrec.example",
                     demo_admin_password="DistinctDeploymentSecret!2026")
    assert valid.environment == "production"
