# Development deployment order

1. Provision PostgreSQL.
2. Apply `migrations/0001` through `0008`.
3. `pip install -r requirements.txt`.
4. Set `DATABASE_URL`.
5. Run `python seeds/seed_taxonomy.py`.
6. Apply `0009` through `0012`.
7. Validate ingest examples.
8. Ingest synthetic fixtures in a development database.
9. Implement read API endpoints against the OpenAPI contract.
10. Only then connect genuine historical datasets and digitized materials.

For production, wrap these files in the migration framework chosen by the web application rather than executing ad hoc SQL from request handlers.
