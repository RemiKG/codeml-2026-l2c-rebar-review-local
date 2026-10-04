"""Run meaningful synthetic tests and save a compact verification receipt."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,contextlib,json,sys,time,unittest
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
parser=argparse.ArgumentParser()
parser.add_argument("--receipt",required=True)
args=parser.parse_args()
receipt=Path(args.receipt).resolve(); receipt.parent.mkdir(parents=True,exist_ok=True)
suite=unittest.defaultTestLoader.discover(str(REPO/"tests"))
start=time.perf_counter()
with receipt.with_suffix(".log").open("w",encoding="utf-8") as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
record={"checked_at":datetime.now(timezone.utc).isoformat(),"synthetic_only":True,"real_source_files_opened":0,
        "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
        "skipped":len(result.skipped),"passed":result.wasSuccessful(),"elapsed_seconds":round(time.perf_counter()-start,3),
        "python":sys.executable,"failure_test_ids":[test.id() for test,_ in result.failures+result.errors]}
receipt.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
print(json.dumps(record))
sys.exit(0 if result.wasSuccessful() else 1)
