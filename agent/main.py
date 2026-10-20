import os, subprocess, tempfile, shutil, pathlib, threading, json, socket, urllib.request, time, ssl, hashlib
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
app=FastAPI(title='ProxyForge Agent')
TOKEN=open('/run/proxyforge/agent_token').read().strip() if os.path.exists('/run/proxyforge/agent_token') else os.getenv('AGENT_TOKEN','change-agent-token')
ENGINE=os.getenv('PROXY_ENGINE','haproxy')
TARGET=os.getenv('TARGET_PATH','/etc/haproxy/proxyforge.cfg')
APPLY=os.getenv('ENABLE_APPLY','false').lower()=='true'
LOCK=threading.Lock()
class Payload(BaseModel):
 engine:str=Field(pattern='^(haproxy|nginx)$');config:str=Field(min_length=1,max_length=1000000)
def discover_engine():
 found=[]
 for name in ('haproxy','nginx'):
  binary=shutil.which(name)
  host_binary=any(os.path.isfile('/host'+p+'/'+name) for p in ('/usr/sbin','/usr/bin','/sbin','/bin','/usr/local/sbin','/usr/local/bin'))
  if binary or host_binary:found.append(name)
 return found
def inventory():
 engines=discover_engine()
 paths={'haproxy':'/etc/haproxy/haproxy.cfg','nginx':'/etc/nginx/nginx.conf'}
 selected=ENGINE if ENGINE in ('haproxy','nginx') else (engines[0] if len(engines)==1 else None)
 config=paths.get(selected)
 active=None
 if selected and not os.path.isdir('/host') and shutil.which('systemctl'):
  try:active=subprocess.run(['systemctl','is-active',selected],capture_output=True,text=True,timeout=3).stdout.strip()
  except Exception:pass
 return {'hostname':socket.gethostname(),'installed':engines,'selected_engine':selected,'config_path':config,
         'config_exists':bool(config and (os.path.isfile(config) or os.path.isfile('/host'+config))),'service_state':active,
         'apply_enabled':APPLY}
@app.get('/discover')
def discover(x_agent_token:str=Header(default='')):
 if x_agent_token!=TOKEN:raise HTTPException(401,'Unauthorized')
 return inventory()
def enroll_loop():
 endpoint=os.getenv('CONTROLLER_URL','').rstrip('/')
 public_url=os.getenv('AGENT_PUBLIC_URL','').rstrip('/')
 enrollment=os.getenv('ENROLLMENT_TOKEN','')
 if not endpoint or not public_url or len(enrollment)<32:return
 if not endpoint.startswith('https://') or not public_url.startswith('https://'):return
 while True:
  try:
   inv=inventory()
   engine=inv['selected_engine']
   if engine:
    body=json.dumps({'name':os.getenv('NODE_NAME',socket.gethostname()).replace('.','-')[:64],
                     'engine':engine,'url':public_url,'token':TOKEN}).encode()
    req=urllib.request.Request(endpoint+'/agents/enroll',data=body,method='POST',
      headers={'Content-Type':'application/json','X-Enrollment-Token':enrollment})
    with urllib.request.urlopen(req,timeout=10,context=ssl.create_default_context()) as r:r.read()
  except Exception as error:
   print('ProxyForge enrollment failed:',type(error).__name__,flush=True)
  time.sleep(60)
@app.on_event('startup')
def start_enrollment():
 threading.Thread(target=enroll_loop,daemon=True).start()
@app.get('/health')
def health():return {'engine':ENGINE,'apply_enabled':APPLY}
@app.post('/apply')
def apply(p:Payload,x_agent_token:str=Header(default='')):
 if x_agent_token!=TOKEN:raise HTTPException(401,'Unauthorized')
 if p.engine!=ENGINE:raise HTTPException(400,'Engine mismatch')
 if not APPLY:return {'status':'dry-run','message':'ENABLE_APPLY=false; no changes made','bytes':len(p.config)}
 with LOCK:
  target=pathlib.Path(TARGET)
  if not target.parent.is_dir():raise HTTPException(400,'Target directory missing')
  fd,tmp=tempfile.mkstemp(dir=str(target.parent),prefix='.proxyforge-',text=True)
  try:
   with os.fdopen(fd,'w') as f:f.write(p.config)
   # HAProxy fragment validation requires the surrounding global/defaults/listener configuration.
   # NGINX upstream fragment requires an http context. We therefore do not deploy unvalidated fragments.
   raise HTTPException(409,'Safe deployment not yet enabled: configure full-context validation and reload for this host')
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
