# Manual smoke test

1. Start NexDB with `NEXDB_API_KEY` set.
2. `GET /health` should return status `ok`.
3. `POST /api/databases` with `{"name":"testdb"}`.
4. `POST /api/collections?database=testdb` with `{"name":"items"}`.
5. `POST /api/data` with database `testdb`, collection `items`, data `{"x":1}`.
6. `GET /api/data?database=testdb&collection=items`.
7. Restart the server and repeat step 6 to check persistence.
