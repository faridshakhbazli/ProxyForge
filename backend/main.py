import os, sqlite3, json, urllib.request, urllib.error, urllib.parse, hmac, secrets, time, ipaddress
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

DB=os.getenv('DB_PATH','/data/proxyforge.db')
# ADMIN_TOKEN in .env is authoritative. Never silently use a different token.
def load_admin_token():
 configured=os.getenv('ADMIN_TOKEN','').strip()
 if configured:
  if len(configured)<8:
   raise RuntimeError('ADMIN_TOKEN from .env must contain at least 8 characters; update .env and recreate the API container')
  return configured
 for path in ('/run/proxyforge/admin_token','/data/admin_token'):
  try:
   with open(path,encoding='utf-8') as stream:
    candidate=stream.read().strip()
   if len(candidate)>=32:
    return candidate
  except FileNotFoundError:
   pass
 # No explicit .env token: initialize a persistent secret as a fallback.
 path='/data/admin_token'
 os.makedirs(os.path.dirname(path),exist_ok=True)
 try:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except FileExistsError:
  with open(path,encoding='utf-8') as stream:
   candidate=stream.read().strip()
  if len(candidate)<32:
   raise RuntimeError('Persistent admin token is invalid; check /data/admin_token')
  return candidate
 with os.fdopen(fd,'w',encoding='utf-8') as stream:
  candidate=secrets.token_urlsafe(48)
  stream.write(candidate)
 return candidate

TOKEN=load_admin_token()
app=FastAPI(title='ProxyForge API',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('UI_ORIGIN','http://localhost:8080')],allow_methods=['*'],allow_headers=['*'])
@contextmanager
def conn():
 os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 try: yield c; c.commit()
 finally:c.close()
@app.on_event('startup')
def init():
 with conn() as c:
  c.execute('CREATE TABLE IF NOT EXISTS nodes(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, engine TEXT NOT NULL, url TEXT NOT NULL, token TEXT NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS upstreams(id INTEGER PRIMARY KEY, node_id INTEGER NOT NULL, name TEXT NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL, algorithm TEXT NOT NULL, UNIQUE(node_id,name))')
def auth(x_admin_token:str=Header(default='')):
 if not hmac.compare_digest(x_admin_token,TOKEN): raise HTTPException(401,'Invalid admin token')
class Enrollment(BaseModel):
 name:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
 engine:str=Field(pattern=r'^(haproxy|nginx)$')
 url:str
 token:str=Field(min_length=8,max_length=512)
class Node(BaseModel):
 name:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
 engine:str=Field(pattern=r'^(haproxy|nginx)$')
 url:str
 token:str=Field(min_length=1,max_length=512)
class Upstream(BaseModel):
 node_id:int;name:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$');host:str=Field(pattern=r'^[a-zA-Z0-9.:-]{1,253}$');port:int=Field(ge=1,le=65535);algorithm:str=Field(pattern=r'^(roundrobin|leastconn)$')
@app.get('/health')
def health():return {'status':'ok'}
@app.get('/nodes')
def nodes(x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 with conn() as c:return [dict(id=r['id'],name=r['name'],engine=r['engine'],url=r['url']) for r in c.execute('SELECT * FROM nodes')]
def allowed_agent_url(url:str)->bool:
 try:
  parsed=urllib.parse.urlsplit(url)
  if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):return False
  host=parsed.hostname
  if not host or not parsed.port or parsed.port<1 or parsed.port>65535:return False
  if parsed.scheme=='https':return True
  if parsed.scheme!='http':return False
  if host in ('agent','127.0.0.1','localhost'):return True
  if os.getenv('ALLOW_HTTP_AGENTS','false').lower()!='true':return False
  # Only explicit private IPv4/IPv6 addresses are allowed in insecure dev mode.
  ip=ipaddress.ip_address(host)
  return ip.is_private and not ip.is_loopback and not ip.is_link_local
 except (ValueError,AttributeError):
  return False
@app.post('/nodes')
def add_node(n:Node,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 if not allowed_agent_url(n.url):raise HTTPException(400,'Use HTTPS for remote agents; set ALLOW_HTTP_AGENTS=true for private IP HTTP agents')
 try:
  with conn() as c:c.execute('INSERT INTO nodes(name,engine,url,token) VALUES(?,?,?,?)',(n.name,n.engine,n.url.rstrip('/'),n.token))
 except sqlite3.IntegrityError:raise HTTPException(409,'Node already exists')
 return {'ok':True}
@app.get('/nodes/{node_id}/discovery')
def discovery(node_id:int,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 with conn() as c:n=c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
 if not n:raise HTTPException(404,'Node not found')
 req=urllib.request.Request(n['url']+'/discover',headers={'X-Agent-Token':n['token']})
 try:
  with urllib.request.urlopen(req,timeout=8) as r:return json.load(r)
 except urllib.error.HTTPError as e:
  # Do not forward response bodies: remote services may echo secrets.
  if e.code in (401,403):
   raise HTTPException(502,'Agent rejected credentials (HTTP '+str(e.code)+'); check the saved node Agent Token and agent .env')
  raise HTTPException(502,'Agent discovery returned HTTP '+str(e.code))
 except urllib.error.URLError as e:
  reason=e.reason
  import ssl
  if isinstance(reason,ssl.SSLError):
   detail='Agent TLS certificate verification failed'
  elif isinstance(reason,(ConnectionRefusedError,TimeoutError)):
   detail='Agent connection refused or timed out'
  else:
   detail='Agent connection failed ('+type(reason).__name__+')'
  raise HTTPException(502,detail)
 except (TimeoutError,ConnectionError):
  raise HTTPException(502,'Agent discovery timed out or connection failed')
 except (ValueError,json.JSONDecodeError):
  raise HTTPException(502,'Agent returned invalid JSON')
 except Exception as e:
  raise HTTPException(502,'Agent discovery failed ('+type(e).__name__+')')
@app.get('/upstreams')
def upstreams(node_id:int,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM upstreams WHERE node_id=?',(node_id,))]
@app.post('/upstreams')
def add_upstream(u:Upstream,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 try:
  with conn() as c:
   if not c.execute('SELECT 1 FROM nodes WHERE id=?',(u.node_id,)).fetchone():raise HTTPException(404,'Node not found')
   c.execute('INSERT INTO upstreams(node_id,name,host,port,algorithm) VALUES(?,?,?,?,?)',(u.node_id,u.name,u.host,u.port,u.algorithm))
 except sqlite3.IntegrityError:raise HTTPException(409,'Upstream already exists')
 return {'ok':True}
def render(node_id):
 with conn() as c:
  n=c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
  if not n:raise HTTPException(404,'Node not found')
  ups=c.execute('SELECT * FROM upstreams WHERE node_id=?',(node_id,)).fetchall()
  if n['engine']=='haproxy':
   config='\n'.join(f"backend {u['name']}\n    mode http\n    balance {u['algorithm']}\n    server app1 {u['host']}:{u['port']} check\n" for u in ups)
  else:
   config='\n'.join(f"upstream {u['name']} {{\n    {'least_conn;' if u['algorithm']=='leastconn' else ''}\n    server {u['host']}:{u['port']};\n}}\n" for u in ups)
  return dict(n),config
@app.get('/preview/{node_id}')
def preview(node_id:int,x_admin_token:str=Header(default='')):
 auth(x_admin_token);n,c=render(node_id);return {'engine':n['engine'],'config':c}
@app.post('/deploy/{node_id}')
def deploy(node_id:int,x_admin_token:str=Header(default='')):
 auth(x_admin_token);n,config=render(node_id)
 if not config.strip():raise HTTPException(400,'No upstreams')
 data=json.dumps({'engine':n['engine'],'config':config}).encode()
 req=urllib.request.Request(n['url']+'/apply',data=data,headers={'Content-Type':'application/json','X-Agent-Token':n['token']},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)
 except urllib.error.HTTPError as e:raise HTTPException(502,e.read().decode()[:1000])
 except Exception as e:raise HTTPException(502,str(e))
@app.post('/agents/enroll')
def enroll(n:Enrollment,x_enrollment_token:str=Header(default='')):
 secret=open('/run/proxyforge/enrollment_token').read().strip() if os.path.exists('/run/proxyforge/enrollment_token') else os.getenv('ENROLLMENT_TOKEN','')
 if len(secret)<32 or not hmac.compare_digest(x_enrollment_token,secret):raise HTTPException(401,'Invalid enrollment token')
 if not n.url.startswith('https://') or n.url.rstrip('/') not in set(os.getenv('AGENT_ALLOWED_URLS','').split(',')):
  raise HTTPException(400,'Agent URL must use HTTPS and be listed in AGENT_ALLOWED_URLS')
 with conn() as c:
  existing=c.execute('SELECT id,url,engine FROM nodes WHERE name=?',(n.name,)).fetchone()
  if existing:
   if existing['url']!=n.url.rstrip('/') or existing['engine']!=n.engine:raise HTTPException(409,'Node identity conflict')
   c.execute('UPDATE nodes SET token=? WHERE id=?',(n.token,existing['id']))
   return {'id':existing['id'],'status':'registered'}
  cur=c.execute('INSERT INTO nodes(name,engine,url,token) VALUES(?,?,?,?)',(n.name,n.engine,n.url.rstrip('/'),n.token))
  return {'id':cur.lastrowid,'status':'registered'}
