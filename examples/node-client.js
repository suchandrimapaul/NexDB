// Use only in a trusted Node.js backend. Never expose this secret in browser code.
const base = process.env.NEXDB_URL;
const key = process.env.NEXDB_API_KEY;

async function nexdb(path, method = "GET", body) {
  const response = await fetch(base + path, {
    method,
    headers: { "Content-Type": "application/json", "X-API-Key": key },
    body: body ? JSON.stringify(body) : undefined
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "NexDB request failed");
  return result;
}

async function main() {
  const inserted = await nexdb("/api/data", "POST", {
    database: "myapp",
    collection: "users",
    data: { username: "alex", active: true }
  });
  console.log(inserted);
  const rows = await nexdb("/api/data?database=myapp&collection=users");
  console.log(rows.documents);
}
main().catch(console.error);
