import os, json, uuid, threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_DIR = Path(os.getenv("NEXDB_DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILE = DATA_DIR / "nexdb.json"
API_KEY = os.getenv("NEXDB_API_KEY", "")
LOCK = threading.RLock()

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def load():
    if not FILE.exists(): return {"databases": {}}
    try: return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception as exc: raise RuntimeError("Database file is unreadable; restore a backup.") from exc

STATE = load()

def save():
    temp = FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(FILE)

def auth(key):
    if not API_KEY:
        raise HTTPException(503, "Set NEXDB_API_KEY before using the API.")
    if key != API_KEY:
        raise HTTPException(401, "Invalid or missing X-API-Key.")

def name_ok(value):
    if not value or len(value) > 64 or not all(c.isalnum() or c in "_-" for c in value):
        raise HTTPException(400, "Names must contain 1-64 letters, numbers, _ or -.")
    return value

def get_db(db):
    if db not in STATE["databases"]: raise HTTPException(404, "Database not found.")
    return STATE["databases"][db]

def get_col(db, col):
    d = get_db(db)
    if col not in d["collections"]: raise HTTPException(404, "Collection not found.")
    return d["collections"][col]

app = FastAPI(title="NexDB", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("NEXDB_CORS_ORIGINS", "*").split(","),
                   allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class NameBody(BaseModel):
    name: str = Field(min_length=1, max_length=64)
class InsertBody(BaseModel):
    database: str
    collection: str
    data: dict[str, Any]
class UpdateBody(BaseModel):
    data: dict[str, Any]

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(HTML)

@app.get("/health")
def health():
    return {"status": "ok", "service": "NexDB", "version": "1.0.0"}

@app.get("/api")
def info():
    return {"name": "NexDB", "docs": "/docs"}

@app.get("/api/databases")
def databases(x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        return {"databases": [{"name": n, "collections": len(v["collections"])} for n,v in STATE["databases"].items()]}

@app.post("/api/databases", status_code=201)
def create_database(body: NameBody, x_api_key: Optional[str] = Header(None)):
    auth(x_api_key); n = name_ok(body.name)
    with LOCK:
        if n in STATE["databases"]: raise HTTPException(409, "Database already exists.")
        STATE["databases"][n] = {"created_at": timestamp(), "collections": {}}
        save()
    return {"success": True, "database": n}

@app.delete("/api/databases/{database}")
def drop_database(database: str, x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        if database not in STATE["databases"]: raise HTTPException(404, "Database not found.")
        del STATE["databases"][database]; save()
    return {"success": True, "deleted": database}

@app.get("/api/collections")
def collections(database: str = Query(...), x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        d = get_db(database)
        return {"collections": [{"name": n, "documents": len(v["documents"])} for n,v in d["collections"].items()]}

@app.post("/api/collections", status_code=201)
def create_collection(body: NameBody, database: str = Query(...), x_api_key: Optional[str] = Header(None)):
    auth(x_api_key); n = name_ok(body.name)
    with LOCK:
        d = get_db(database)
        if n in d["collections"]: raise HTTPException(409, "Collection already exists.")
        d["collections"][n] = {"created_at": timestamp(), "documents": {}}
        save()
    return {"success": True, "collection": n}

@app.delete("/api/collections/{collection}")
def drop_collection(collection: str, database: str = Query(...), x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        d = get_db(database)
        if collection not in d["collections"]: raise HTTPException(404, "Collection not found.")
        del d["collections"][collection]; save()
    return {"success": True, "deleted": collection}

@app.post("/api/data", status_code=201)
def insert(body: InsertBody, x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        col = get_col(body.database, body.collection)
        doc_id = str(uuid.uuid4())
        doc = {"_id": doc_id, **body.data, "_created_at": timestamp(), "_updated_at": timestamp()}
        col["documents"][doc_id] = doc; save()
    return {"success": True, "id": doc_id, "document": doc}

@app.get("/api/data")
def list_data(database: str = Query(...), collection: str = Query(...),
              limit: int = Query(100, ge=1, le=500), x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        docs = list(get_col(database, collection)["documents"].values())[:limit]
        return {"count": len(docs), "documents": docs}

@app.get("/api/data/{document_id}")
def get_data(document_id: str, database: str = Query(...), collection: str = Query(...),
             x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        doc = get_col(database, collection)["documents"].get(document_id)
        if doc is None: raise HTTPException(404, "Document not found.")
        return {"document": doc}

@app.patch("/api/data/{document_id}")
def update_data(document_id: str, body: UpdateBody, database: str = Query(...), collection: str = Query(...),
                x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        docs = get_col(database, collection)["documents"]
        doc = docs.get(document_id)
        if doc is None: raise HTTPException(404, "Document not found.")
        for k,v in body.data.items():
            if k not in ("_id", "_created_at"): doc[k] = v
        doc["_updated_at"] = timestamp(); save()
        return {"success": True, "document": doc}

@app.delete("/api/data/{document_id}")
def delete_data(document_id: str, database: str = Query(...), collection: str = Query(...),
                x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        docs = get_col(database, collection)["documents"]
        if document_id not in docs: raise HTTPException(404, "Document not found.")
        del docs[document_id]; save()
    return {"success": True, "deleted": document_id}

@app.get("/api/stats")
def stats(x_api_key: Optional[str] = Header(None)):
    auth(x_api_key)
    with LOCK:
        dbs = STATE["databases"]
        cols = sum(len(d["collections"]) for d in dbs.values())
        docs = sum(len(c["documents"]) for d in dbs.values() for c in d["collections"].values())
        return {"databases": len(dbs), "collections": cols, "documents": docs,
                "storage_bytes": FILE.stat().st_size if FILE.exists() else 0}

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NexDB Console</title><style>
*{box-sizing:border-box}body{margin:0;background:#08111f;color:#eaf3ff;font:15px system-ui}header{padding:20px 5%;border-bottom:1px solid #263b56;background:#0d1b2d}
main{max-width:1150px;margin:28px auto;padding:0 18px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:#122239;border:1px solid #29405d;border-radius:13px;padding:17px;margin-bottom:14px}
.layout{display:grid;grid-template-columns:330px 1fr;gap:14px;margin-top:14px}input,textarea{width:100%;padding:11px;margin:6px 0 12px;background:#081626;border:1px solid #304967;border-radius:8px;color:white}
button{padding:10px 14px;border:0;border-radius:8px;background:#168fe5;color:white;cursor:pointer;font-weight:650;margin:3px}pre{white-space:pre-wrap;overflow:auto;background:#071321;border:1px solid #29405d;padding:12px;border-radius:9px;min-height:55px}.muted{color:#9db1c9}
@media(max-width:800px){.layout{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}}
</style></head><body><header><b>🔷 NexDB</b> <span class="muted">/ Database Console</span></header><main>
<h2>Overview</h2><div class="grid"><div class="card">Databases<h2 id="dbs">—</h2></div><div class="card">Collections<h2 id="cols">—</h2></div><div class="card">Documents<h2 id="docs">—</h2></div><div class="card">Storage<h2 id="size">—</h2></div></div>
<div class="layout"><section class="card"><h3>Connect</h3><label>API key</label><input id="key" type="password" placeholder="Paste API key"><button onclick="connect()">Connect</button>
<hr><h3>Databases</h3><input id="dbnew" placeholder="database name"><button onclick="createDb()">Create database</button><div id="dblist"></div>
<hr><h3>Collections</h3><input id="colnew" placeholder="collection name"><button onclick="createCol()">Create collection</button><div id="collist"></div></section>
<section class="card"><h3 id="title">Data Explorer</h3><p class="muted">Choose a database and collection. Add a JSON document.</p>
<textarea id="json" rows="6">{ "name": "Alex", "active": true }</textarea><button onclick="insertDoc()">Insert document</button><button onclick="loadDocs()">Refresh</button><h3>Documents</h3><pre id="output">No documents loaded.</pre><h3>Last API response</h3><pre id="status">Not connected.</pre></section></div>
<p class="muted">Starter project for learning and testing. Do not expose publicly with real data until production security, tenant isolation, backups and scalable storage are implemented.</p></main>
<script>
let key=sessionStorage.getItem('nexdb_key')||'',db='',col='';document.getElementById('key').value=key;
async function api(path,method='GET',body){let r=await fetch(path,{method,headers:{'Content-Type':'application/json','X-API-Key':key},body:body?JSON.stringify(body):undefined});let d=await r.json();status.textContent=JSON.stringify(d,null,2);if(!r.ok)throw Error(d.detail||'Request failed');return d}
function fail(e){status.textContent='Error: '+e.message}
async function connect(){key=document.getElementById('key').value;sessionStorage.setItem('nexdb_key',key);refresh()}
async function refresh(){try{let s=await api('/api/stats');dbs.textContent=s.databases;cols.textContent=s.collections;docs.textContent=s.documents;size.textContent=(s.storage_bytes/1024).toFixed(1)+' KB';let d=await api('/api/databases');dblist.innerHTML='';d.databases.forEach(x=>{let b=document.createElement('button');b.textContent=x.name+' ('+x.collections+')';b.onclick=()=>selectDb(x.name);dblist.append(b)})}catch(e){fail(e)}}
async function createDb(){try{await api('/api/databases','POST',{name:dbnew.value});dbnew.value='';refresh()}catch(e){fail(e)}}
async function selectDb(n){db=n;col='';title.textContent='Database: '+db;try{let d=await api('/api/collections?database='+encodeURIComponent(db));collist.innerHTML='';d.collections.forEach(x=>{let b=document.createElement('button');b.textContent=x.name+' ('+x.documents+')';b.onclick=()=>{col=x.name;title.textContent=db+' / '+col;loadDocs()};collist.append(b)})}catch(e){fail(e)}}
async function createCol(){if(!db)return alert('Select a database first');try{await api('/api/collections?database='+encodeURIComponent(db),'POST',{name:colnew.value});colnew.value='';selectDb(db)}catch(e){fail(e)}}
async function insertDoc(){if(!db||!col)return alert('Select a database and collection');try{await api('/api/data','POST',{database:db,collection:col,data:JSON.parse(json.value)});await loadDocs();refresh()}catch(e){fail(e)}}
async function loadDocs(){if(!db||!col)return;try{let d=await api('/api/data?database='+encodeURIComponent(db)+'&collection='+encodeURIComponent(col));output.textContent=JSON.stringify(d.documents,null,2)}catch(e){fail(e)}}
if(key)refresh();
</script></body></html>"""
