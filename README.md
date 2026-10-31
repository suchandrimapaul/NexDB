# NexDB

A small self-hostable document database starter built with FastAPI.

## Included
- Multiple databases and collections
- Insert, list, get, update and delete JSON documents
- Persistent JSON-file storage
- API-key-protected API
- Browser dashboard at `/`
- Interactive API documentation at `/docs`
- Health check at `/health`
- Basic storage statistics

## Run in GitHub Codespaces

1. Upload this folder to a private GitHub repository.
2. Open Code > Codespaces > Create codespace.
3. In the terminal run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

4. Edit `.env`. Replace `NEXDB_API_KEY` with a long random secret.
5. Load the variables and start the server:

```bash
set -a
source .env
set +a
uvicorn main:app --host 0.0.0.0 --port 8000
```

6. Open the Ports tab, open port 8000, then visit `/` for the dashboard or `/docs` for API testing.

Codespaces is a development environment, not permanent production hosting. Use a dedicated server with persistent disk and tested backups for production.

## API authentication

Send this header to all `/api/*` endpoints:

`X-API-Key: YOUR_NEXDB_API_KEY`

## Create a database

```bash
curl -X POST "$NEXDB_URL/api/databases" \
  -H "X-API-Key: $NEXDB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"myapp"}'
```

## Create a collection

```bash
curl -X POST "$NEXDB_URL/api/collections?database=myapp" \
  -H "X-API-Key: $NEXDB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"users"}'
```

## Insert a document

```bash
curl -X POST "$NEXDB_URL/api/data" \
  -H "X-API-Key: $NEXDB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"database":"myapp","collection":"users","data":{"name":"Alex","active":true}}'
```

## Read documents

```bash
curl "$NEXDB_URL/api/data?database=myapp&collection=users" \
  -H "X-API-Key: $NEXDB_API_KEY"
```

## JavaScript from a trusted backend

```js
const response = await fetch(`${NEXDB_URL}/api/data`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": process.env.NEXDB_API_KEY
  },
  body: JSON.stringify({
    database: "myapp",
    collection: "users",
    data: { name: "Alex", active: true }
  })
});
const result = await response.json();
```

Never put the master API key in public frontend JavaScript. For browser apps, call your own backend proxy and keep the NexDB secret server-side.

## Limitations and safety

This is a learning prototype, not a production database replacement. It stores all records in one JSON file and rewrites that file on each write. It is not suitable for large datasets, high traffic, multi-process deployment, critical data, or public multi-tenant use. It currently has one global API key, no per-user authorization, no tenant isolation, no transactions, no indexes, and no automated backup scheduler. Add those and conduct security testing before storing real user data.

For a manual backup, stop the server and copy `data/nexdb.json` to a secure location. Test restore before relying on backups.
