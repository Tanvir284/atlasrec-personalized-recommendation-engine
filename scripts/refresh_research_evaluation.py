"""Re-evaluate immutable research bundles with added diagnostics; retain original training hashes."""
import json
from pathlib import Path

import numpy as np
from atlasrec_ml.bundle import load_bundle
from atlasrec_ml.data import Dataset, temporal_split
from atlasrec_ml.evaluate import evaluate
from atlasrec_ml.models import Recommender
from atlasrec_ml.pipeline import source_hash
from atlasrec_ml.resources import observed_memory

p=Path("docs/evidence/research-benchmark.json")
report=json.loads(p.read_text(encoding="utf-8"))
data=Dataset.load(Path("data")/(report["manifest"]["dataset_id"]+".json"))
split=temporal_split(data)
for run in report["runs"]:
    if run["status"] == "completed":
        model,_=load_bundle(run["bundle"])
        run["validation"]=evaluate(model,split["validation"])
        run["metrics"]=evaluate(model,split["test"])
        run["diversity_metrics"]=evaluate(model,split["test"],diversity=0.1)
        run["evaluation_source_hash"]=source_hash()
base=report["runs"][0]
config=base["config"]
eligible=sorted({e["item"] for e in split["train"]})
rng=np.random.default_rng(config["seed"])
withheld=rng.choice(eligible,max(1,int(len(eligible)*config["cold_item_fraction"])),replace=False).tolist()
cold_train=[{**e,"rating":1} if e["item"] in withheld else e for e in split["train"]]
with observed_memory() as memory:
    model=Recommender("two_tower",{**config,"content_only_ids":withheld,"epochs":min(6,config["epochs"])}).fit(data.products,cold_train)
report["cold_item"]={"method":"eligible-item collaborative interaction withholding","withheld_count":len(withheld),"withheld_ids":withheld,
                    "id_embedding":"masked to zero; item vectors use only permitted content",
                    "fit_status":model.fit_status,"training_seconds":model.training_seconds,
                    **memory,"metrics":evaluate(model,split["test"],positives_only=withheld),
                    "reference_run":base["id"],"evaluation_source_hash":source_hash()}
p.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("Re-evaluated immutable bundles; cold stress:",model.fit_status)
