"""Execute a notebook with this interpreter, loopback only, and local output."""
from pathlib import Path
import argparse,json,os,sys,time
from datetime import datetime,timezone
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpec,KernelSpecManager
parser=argparse.ArgumentParser()
parser.add_argument("--output",required=True)
parser.add_argument("--work",required=True)
parser.add_argument("--input")
parser.add_argument("--ocr",choices=["off","auto"],default="off")
parser.add_argument("--ocr-max-pages",type=int,default=8)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
work=Path(args.work).resolve(); work.mkdir(parents=True,exist_ok=True)
output=Path(args.output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
if output.is_relative_to(repo): raise SystemExit("Executed notebook must be outside the public repository.")
os.environ["JUPYTER_RUNTIME_DIR"]=str(work/"jupyter-runtime")
os.environ["JUPYTER_CONFIG_DIR"]=str(work/"jupyter-config")
os.environ["IPYTHONDIR"]=str(work/"ipython")
env={"L2C_NOTEBOOK_WORK":str(work),"L2C_OUTPUT":str(work/"outputs"),"L2C_OCR":args.ocr,
     "L2C_OCR_MAX_PAGES":str(args.ocr_max_pages),"OMP_NUM_THREADS":"2","OPENBLAS_NUM_THREADS":"2","MKL_NUM_THREADS":"2"}
if args.input: env["L2C_INPUT"]=str(Path(args.input).resolve())
else: env["L2C_INPUT"]=""
class LocalSpec(KernelSpecManager):
    def get_kernel_spec(self,name):
        return KernelSpec(argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],display_name="L2C isolated",language="python",env=env)
manager=KernelManager(kernel_name="l2c-isolated",kernel_spec_manager=LocalSpec(),ip="127.0.0.1")
nb=nbformat.read(repo/"notebooks/l2c_pipeline.ipynb",as_version=4)
start=time.perf_counter()
try:
    NotebookClient(nb,km=manager,timeout=1800,resources={"metadata":{"path":str(repo)}}).execute()
    nbformat.write(nb,output)
finally:
    if manager.has_kernel: manager.shutdown_kernel(now=True)
    manager.cleanup_resources()
receipt={"checked_at":datetime.now(timezone.utc).isoformat(),"synthetic":not bool(args.input),
         "executed_cells":sum(c.cell_type=="code" and c.execution_count is not None for c in nb.cells),
         "elapsed_seconds":round(time.perf_counter()-start,3),"kernel_stopped":not manager.has_kernel,
         "loopback":"127.0.0.1","python":sys.executable}
output.with_suffix(".receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt))
