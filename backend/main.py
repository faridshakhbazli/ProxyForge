import os, sqlite3, json, urllib.request, urllib.error, hmac, secrets, time
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

DB=os.getenv('DB_PATH','/data/proxyforge.db')
TOKEN=os.getenv('ADMIN_TOKEN','change-me')
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
 if x_admin_token!=TOKEN: raise HTTPException(401,'Invalid admin token')
class Enrollment(BaseModel):
 name:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,64}
 name:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$');engine:str=Field(pattern=r'^(haproxy|nginx)$');url:str;token:str
class Upstream(BaseModel):
 node_id:int;name:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$');host:str=Field(pattern=r'^[a-zA-Z0-9.:-]{1,253}$');port:int=Field(ge=1,le=65535);algorithm:str=Field(pattern=r'^(roundrobin|leastconn)$')
@app.get('/health')
def health():return {'status':'ok'}
@app.get('/nodes')
def nodes(x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 with conn() as c:return [dict(id=r['id'],name=r['name'],engine=r['engine'],url=r['url']) for r in c.execute('SELECT * FROM nodes')]
@app.post('/nodes')
def add_node(n:Node,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 if not (n.url.startswith('http://agent:') or n.url.startswith('http://127.0.0.1:') or n.url.startswith('https://')):raise HTTPException(400,'Use HTTPS for remote agents')
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
 except Exception:raise HTTPException(502,'Agent discovery unavailable; check HTTPS, certificate trust and network access')
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
)
 engine:str=Field(pattern=r'^(haproxy|nginx)
 name:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$');engine:str=Field(pattern=r'^(haproxy|nginx)$');url:str;token:str
class Upstream(BaseModel):
 node_id:int;name:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$');host:str=Field(pattern=r'^[a-zA-Z0-9.:-]{1,253}$');port:int=Field(ge=1,le=65535);algorithm:str=Field(pattern=r'^(roundrobin|leastconn)$')
@app.get('/health')
def health():return {'status':'ok'}
@app.get('/nodes')
def nodes(x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 with conn() as c:return [dict(id=r['id'],name=r['name'],engine=r['engine'],url=r['url']) for r in c.execute('SELECT * FROM nodes')]
@app.post('/nodes')
def add_node(n:Node,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 if not (n.url.startswith('http://agent:') or n.url.startswith('http://127.0.0.1:') or n.url.startswith('https://')):raise HTTPException(400,'Use HTTPS for remote agents')
 try:
  with conn() as c:c.execute('INSERT INTO nodes(name,engine,url,token) VALUES(?,?,?,?)',(n.name,n.engine,n.url.rstrip('/'),n.token))
 except sqlite3.IntegrityError:raise HTTPException(409,'Node already exists')
 return {'ok':True}
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
)
 url:str
 token:str=Field(min_length=32,max_length=512)
@app.post('/agents/enroll')
def enroll(n:Enrollment,x_enrollment_token:str=Header(default='')):
 secret=os.getenv('ENROLLMENT_TOKEN','')
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
class Node(BaseModel):
 name:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$');engine:str=Field(pattern=r'^(haproxy|nginx)$');url:str;token:str
class Upstream(BaseModel):
 node_id:int;name:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$');host:str=Field(pattern=r'^[a-zA-Z0-9.:-]{1,253}$');port:int=Field(ge=1,le=65535);algorithm:str=Field(pattern=r'^(roundrobin|leastconn)$')
@app.get('/health')
def health():return {'status':'ok'}
@app.get('/nodes')
def nodes(x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 with conn() as c:return [dict(id=r['id'],name=r['name'],engine=r['engine'],url=r['url']) for r in c.execute('SELECT * FROM nodes')]
@app.post('/nodes')
def add_node(n:Node,x_admin_token:str=Header(default='')):
 auth(x_admin_token)
 if not (n.url.startswith('http://agent:') or n.url.startswith('http://127.0.0.1:') or n.url.startswith('https://')):raise HTTPException(400,'Use HTTPS for remote agents')
 try:
  with conn() as c:c.execute('INSERT INTO nodes(name,engine,url,token) VALUES(?,?,?,?)',(n.name,n.engine,n.url.rstrip('/'),n.token))
 except sqlite3.IntegrityError:raise HTTPException(409,'Node already exists')
 return {'ok':True}
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
