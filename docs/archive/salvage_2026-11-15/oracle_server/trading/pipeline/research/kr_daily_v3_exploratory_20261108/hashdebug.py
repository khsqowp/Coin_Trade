from pathlib import Path
import hashlib, subprocess
root='/home/opc/trading/pipeline'
cmd="cd /home/opc/trading/pipeline && find research/kr_daily_v2/data -maxdepth 1 -type f -name '*.parquet' -print0 | sort -z | xargs -0 sha256sum"
out=subprocess.check_output(cmd,shell=True)
print('shell raw',len(out),hashlib.sha256(out).hexdigest(),repr(out[:180]))
files=sorted((Path(root)/'research/kr_daily_v2/data').glob('*.parquet'))
lines=[]
for f in files: lines.append(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  research/kr_daily_v2/data/{f.name}\n')
raw=''.join(lines).encode()
print('python raw',len(raw),hashlib.sha256(raw).hexdigest(),repr(raw[:180]), 'same',raw==out)
for i,(a,b) in enumerate(zip(raw.splitlines(),out.splitlines())):
 if a!=b: print('firstdiff',i,repr(a),repr(b)); break
