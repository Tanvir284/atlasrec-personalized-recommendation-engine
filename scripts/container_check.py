"""HTTP acceptance checks against the real Compose stack. Never drop application data."""
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE=os.environ.get("BASE_URL","http://localhost:3000")
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
csrf=None
def call(path,method="GET",body=None):
    global csrf
    headers={}
    if method!="GET":
        if not csrf:
            csrf=call("/auth/csrf")["csrf_token"]
        headers={"Origin":BASE,"x-csrf-token":csrf,"Content-Type":"application/json"}
    request=urllib.request.Request(BASE+"/api/v1"+path,method=method,
                                  data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with opener.open(request,timeout=45) as response:
            result=json.load(response)
    except urllib.error.HTTPError as error:
        print(method,path,error.code,error.read().decode(),flush=True)
        raise
    if isinstance(result,dict):
        csrf=result.get("csrf_token",csrf)
    return result

outcomes={}
shopper=call("/auth/register","POST",{"email":"smoke-"+uuid.uuid4().hex+"@example.com","password":"SmokeTest!2026","name":"Smoke Check"})
call("/me/preferences","PUT",{"categories":["Audio"]})
items=call("/products?limit=3")["items"]
item=items[0]["id"]
call("/favorites/"+item,"PUT")
assert item in [p["id"] for p in call("/favorites")["items"]]
outcomes["persisted_shopper"]=True
rec=call("/recommendations")
event={"id":str(uuid.uuid4()),"item_id":rec["items"][0]["id"],"kind":"impression",
       "surface":"container-smoke","request_id":rec["request_id"],"position":0}
cookie="; ".join(c.name+"="+c.value for c in jar)
def repeat(_):
    req=urllib.request.Request(BASE+"/api/v1/events",method="POST",data=json.dumps(event).encode(),
         headers={"Origin":BASE,"x-csrf-token":csrf,"Content-Type":"application/json","Cookie":cookie})
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.load(response)
with ThreadPoolExecutor(max_workers=5) as pool:
    replies=list(pool.map(repeat,range(5)))
assert all(r["ok"] for r in replies)
assert sum(not r["duplicate"] for r in replies)==1
outcomes["concurrent_event_idempotency"]=True
try:
    call("/admin/models")
    raise AssertionError("Shopper reached admin")
except urllib.error.HTTPError as e:
    assert e.code==403
call("/auth/logout","POST")
csrf=None
call("/auth/login","POST",{"email":"admin@atlasrec.local","password":"AtlasDemo!2026"})
active=next(m["id"] for m in call("/admin/models")["items"] if m["active"])
job=call("/admin/jobs","POST",{"model":"item_cf","epochs":2,"seed":42})
print("Enqueued",job,flush=True)
assert job["status"]=="queued"
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    result=next(j for j in call("/admin/jobs") if j["id"]==job["id"])
    if result["status"] in ("completed","failed"):
        break
    time.sleep(1)
assert result["status"]=="completed",result
assert next(m["id"] for m in call("/admin/models")["items"] if m["active"])==active
candidate=result["result"]["runs"][0]
call("/admin/models/"+candidate+"/promote","POST")
assert next(m["id"] for m in call("/admin/models")["items"] if m["active"])==candidate
call("/admin/models/rollback","POST")
assert next(m["id"] for m in call("/admin/models")["items"] if m["active"])==active
outcomes.update({"queued_job_completed":True,"job":job["id"],"candidate":candidate,
                 "promotion_rollback":True,"profile":call("/admin/overview")["profile"]})
Path("docs/evidence/container-check.json").write_text(json.dumps(outcomes,indent=2),encoding="utf-8")
print(json.dumps(outcomes,indent=2))
