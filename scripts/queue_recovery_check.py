"""Exercise real Celery failure/retry using a separately identified smoke job."""
import http.cookiejar
import json
import time
import urllib.request
import uuid
from pathlib import Path

from atlasrec_api.db import Job, ModelVersion, SessionLocal, User
from atlasrec_api.queue import celery
from atlasrec_api.settings import settings
from sqlalchemy import select

if settings.profile != "demo":
    raise SystemExit("This smoke check requires the explicit demo profile")
with SessionLocal() as db:
    active = db.scalar(select(ModelVersion.id).where(ModelVersion.active.is_(True)))
    admin = db.scalar(select(User).where(User.email == settings.demo_admin_email))
    job_id = str(uuid.uuid4())
    db.add(Job(id=job_id,user_id=admin.id,status="queued",progress=0,
        config={"profile":"demo","models":["bpr"],"products":1,"seed":42,
                "threads":2,"epochs":2,"time_budget":60,"cold_item_fraction":0}))
    db.commit()
celery.send_task("atlasrec.train",args=[job_id],task_id=job_id)

def wait():
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        with SessionLocal() as db:
            job=db.get(Job,job_id)
            if job.status in ("completed","failed"):
                return job.status,job.error,job.attempts
        time.sleep(1)
    raise TimeoutError("Worker did not complete the bounded smoke job")
status,error,attempts=wait()
assert status=="failed" and error,(status,error)
with SessionLocal() as db:
    assert db.scalar(select(ModelVersion.id).where(ModelVersion.active.is_(True)))==active
    job=db.get(Job,job_id)
    job.config={**job.config,"models":["popularity"],"products":200,"users":100,"interactions":3000}
    db.commit()
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
base="http://localhost:8000/api/v1"
with opener.open(base+"/auth/csrf",timeout=45) as response:
    token=json.load(response)["csrf_token"]
headers={"Origin":"http://localhost:3000","x-csrf-token":token,"Content-Type":"application/json"}
request=urllib.request.Request(base+"/auth/login",method="POST",headers=headers,
      data=json.dumps({"email":settings.demo_admin_email,"password":settings.demo_admin_password}).encode())
with opener.open(request,timeout=45) as response:
    headers["x-csrf-token"]=json.load(response)["csrf_token"]
request=urllib.request.Request(base+"/admin/jobs/"+job_id+"/retry",method="POST",headers=headers)
with opener.open(request,timeout=45) as response:
    assert response.status==202
status,_,attempts=wait()
assert status=="completed" and attempts==2,(status,attempts)
with SessionLocal() as db:
    assert db.scalar(select(ModelVersion.id).where(ModelVersion.active.is_(True)))==active
result={"profile":"demo","job":job_id,"first_status":"failed","failure":error,
        "retry_status":status,"attempts":attempts,"active_preserved":True,
        "boundary":"real Redis/Celery worker, PostgreSQL, and authenticated HTTP retry"}
Path("docs/evidence").mkdir(parents=True,exist_ok=True)
Path("docs/evidence/queue-recovery.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
