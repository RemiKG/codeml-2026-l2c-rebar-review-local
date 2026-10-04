"""Run the CLI with outbound Python socket attempts blocked and aggregate output."""
import sys,socket,json,runpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
attempts=0
def denied(*args,**kwargs):
    global attempts
    attempts+=1
    raise OSError('Network disabled within the local processing worker')
socket.socket.connect=denied
socket.socket.connect_ex=denied
socket.create_connection=denied
try:
    sys.argv=[str(ROOT/'l2c_pipeline.py'),*sys.argv[1:]]
    runpy.run_path(str(ROOT/'l2c_pipeline.py'),run_name='__main__')
finally:
    print(json.dumps({'python_network_attempts_blocked':attempts}),file=sys.stderr)
