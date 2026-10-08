import os, subprocess, tempfile, shutil, pathlib, threading
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
app=FastAPI(title='ProxyForge Agent')
TOKEN=os.getenv('AGENT_TOKEN','change-agent-token')
ENGINE=os.getenv('PROXY_ENGINE','haproxy')
TARGET=os.getenv('TARGET_PATH','/etc/haproxy/proxyforge.cfg')
APPLY=os.getenv('ENABLE_APPLY','false').lower()=='true'
LOCK=threading.Lock()
class Payload(BaseModel):
 engine:str=Field(pattern='^(haproxy|nginx)$');config:str=Field(min_length=1,max_length=1000000)
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
