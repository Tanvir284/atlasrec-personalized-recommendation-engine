from atlasrec_api.db import ModelVersion, SessionLocal, User
from atlasrec_api.lifecycle import promote, register_report, seed_catalog
from atlasrec_api.settings import settings
from atlasrec_ml.data import demo
from atlasrec_ml.pipeline import run
from sqlalchemy import select

if settings.profile != "demo":
    raise SystemExit("Bootstrap is restricted to the explicit demo profile")
data = demo()
with SessionLocal() as db:
    seed_catalog(db, data)
    active = db.scalar(select(ModelVersion).where(ModelVersion.profile == "demo", ModelVersion.active.is_(True)))
    if active:
        print("Reused active model", active.id)
    else:
        candidate = db.scalar(select(ModelVersion).where(ModelVersion.profile == "demo", ModelVersion.validated.is_(True)))
        if not candidate:
            report = run({"profile": "demo", "models": ["popularity"], "seed": 42, "cold_item_fraction": 0}, data)
            register_report(db, report)
            candidate = db.get(ModelVersion, report["runs"][0]["id"])
        if not candidate:
            raise SystemExit("Training did not produce a valid candidate")
        admin = db.scalar(select(User).where(User.email == settings.demo_admin_email))
        promote(db, candidate.id, admin.id)
        print("Promoted initial demo bundle", candidate.id)
