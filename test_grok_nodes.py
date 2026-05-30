#!/usr/bin/env python3
import base64, json, os, subprocess, time
from pathlib import Path

NODES_FILE = Path('/tmp/grok_nodes.txt')
LIMIT = int(os.environ.get('LIMIT','25'))
OFFSET = int(os.environ.get('OFFSET','0'))

REMOTE_SCRIPT = r'''import sys,json,urllib.request,base64
node=base64.b64decode(sys.argv[1]).decode('utf-8')
base="http://127.0.0.1:9090"
req=urllib.request.Request(base+"/proxies/GLOBAL", data=json.dumps({"name":node}).encode(), method="PUT", headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req, timeout=5) as r:
    print(r.status)
'''

def ensure_remote_script():
    b64=base64.b64encode(REMOTE_SCRIPT.encode()).decode()
    cmd=f"echo {b64} | base64 -d | sudo docker exec -i grok-pool sh -lc 'cat > /tmp/set_global_node.py'"
    subprocess.run(['ssh','cloud',cmd], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

def set_node(node):
    arg=base64.b64encode(node.encode()).decode()
    r=subprocess.run(['ssh','cloud','sudo','docker','exec','grok-pool','python3','/tmp/set_global_node.py',arg], text=True, capture_output=True, timeout=15)
    return r.returncode==0 and '204' in r.stdout, (r.stderr or r.stdout).strip()[:160]

def curl_test():
    cmd=['curl','-x','http://10.0.0.2:17912','-o','/dev/null','-sS','-w','%{http_code} %{time_total} %{remote_ip}','-m','15','https://www.tiktok.com/search/video?q=springfestival']
    r=subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def main():
    ensure_remote_script()
    lines=NODES_FILE.read_text(encoding='utf-8').splitlines()
    nodes=[x for x in lines[1:] if x.strip()][OFFSET:OFFSET+LIMIT]
    good=[]
    for i,node in enumerate(nodes,OFFSET+1):
        ok,msg=set_node(node)
        time.sleep(0.5)
        rc,out,err=curl_test() if ok else (999,'',msg or 'set failed')
        rec={'i':i,'node':node,'set':ok,'rc':rc,'curl':out,'err':err[:160]}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        if rc==0 and out.startswith('200 '):
            try: t=float(out.split()[1])
            except Exception: t=99
            if t<10: good.append((t,node,out))
    print('GOOD')
    for t,node,out in sorted(good)[:20]:
        print(json.dumps({'time':t,'node':node,'curl':out}, ensure_ascii=False), flush=True)

if __name__=='__main__': main()
