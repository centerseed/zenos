# ZenOS Shared Cloud SQL Deployment Playbook

Last updated: 2026-03-25 (JST)
Owner: ZenOS Engineering

## 1) Deployment model (cost-optimized)

Use one shared Cloud SQL instance and isolate each system/customer by:

- dedicated database (e.g. `zenos`)
- dedicated DB user (e.g. `zenos_api`)
- dedicated Secret Manager secret per system
- least-privilege IAM (Cloud SQL Client + Secret Accessor)

Current shared instance:

- Project: `zentropy-4f7a5`
- Instance: `zentropy-db`
- Connection name: `zentropy-4f7a5:asia-east1:zentropy-db`
- Engine: PostgreSQL 16

## 2) Current status snapshot

### Shared SQL side (`zentropy-4f7a5`)

- Databases include: `postgres`, `neondb`, `zenos`
- Users include: `postgres`, `naruvia_api`, `zenos_api`

### ZenOS project side (`zenos-naruvia`)

- Cloud Run service: `zenos-mcp` (region `asia-east1`)
- Service account: `165893875709-compute@developer.gserviceaccount.com`
- Secret exists: `database-url`
- `zenos-mcp` is configured with:
  - `DATABASE_URL` from Secret Manager (`database-url`)
  - Cloud SQL binding: `zentropy-4f7a5:asia-east1:zentropy-db`

## 3) One-time bootstrap (new environment)

### 3.1 Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  --project=<ZENOS_PROJECT>
```

### 3.2 Prepare DB isolation in shared SQL project

```bash
# In shared SQL project (e.g. zentropy-4f7a5)
gcloud sql users create <SYSTEM_DB_USER> \
  --instance=<SHARED_SQL_INSTANCE> \
  --project=<SHARED_SQL_PROJECT> \
  --password='<DB_SECRET_VALUE>'

gcloud sql databases create <SYSTEM_DB_NAME> \
  --instance=<SHARED_SQL_INSTANCE> \
  --project=<SHARED_SQL_PROJECT>
```

### 3.3 Create DB URL secret in target project

Use Cloud Run + Cloud SQL socket format:

```text
postgresql://<SYSTEM_DB_USER>:<DB_SECRET_VALUE>@localhost/<SYSTEM_DB_NAME>?host=/cloudsql/<SHARED_PROJECT>:<REGION>:<INSTANCE>
```

```bash
printf '%s' '<DATABASE_URL>' | gcloud secrets create database-url \
  --replication-policy=automatic \
  --data-file=- \
  --project=<ZENOS_PROJECT>
```

If secret already exists, add a new version instead:

```bash
printf '%s' '<DATABASE_URL>' | gcloud secrets versions add database-url \
  --data-file=- \
  --project=<ZENOS_PROJECT>
```

### 3.4 IAM grants

```bash
# runtime SA in target project
gcloud secrets add-iam-policy-binding database-url \
  --project=<ZENOS_PROJECT> \
  --member='serviceAccount:<ZENOS_RUNTIME_SA>' \
  --role='roles/secretmanager.secretAccessor'

# allow cross-project Cloud SQL connect
gcloud projects add-iam-policy-binding <SHARED_SQL_PROJECT> \
  --member='serviceAccount:<ZENOS_RUNTIME_SA>' \
  --role='roles/cloudsql.client'
```

### 3.5 Update Cloud Run service

```bash
gcloud run services update zenos-mcp \
  --project=<ZENOS_PROJECT> \
  --region=<REGION> \
  --update-secrets='DATABASE_URL=database-url:latest' \ # pragma: allowlist secret
  --add-cloudsql-instances='<SHARED_PROJECT>:<REGION>:<INSTANCE>'
```

## 4) Schema rollout (ZenOS SQL cutover)

Migration file in repo:

- `migrations/20260325_0001_sql_cutover_init.sql`

Run migration through Cloud SQL Proxy:

```bash
cloud-sql-proxy <SHARED_PROJECT>:<REGION>:<INSTANCE> --port 55433

# In another shell
psql "postgresql://<SYSTEM_DB_USER>:<DB_SECRET_VALUE>@127.0.0.1:55433/<SYSTEM_DB_NAME>" \
  -v ON_ERROR_STOP=1 \
  -f migrations/20260325_0001_sql_cutover_init.sql
```

Expected: `zenos` schema with 12 tables.

## 5) Validation checklist

```bash
# A) Service revision has Cloud SQL binding
gcloud run services describe zenos-mcp \
  --project=<ZENOS_PROJECT> --region=<REGION> \
  --format='value(spec.template.metadata.annotations.run.googleapis.com/cloudsql-instances)'

# B) DATABASE_URL is secret-backed
gcloud run services describe zenos-mcp \
  --project=<ZENOS_PROJECT> --region=<REGION> \
  --format='yaml(spec.template.spec.containers[0].env)'

# C) Tables exist
psql "postgresql://<SYSTEM_DB_USER>:<DB_SECRET_VALUE>@127.0.0.1:55433/<SYSTEM_DB_NAME>" \
  -c "select table_name from information_schema.tables where table_schema='zenos' order by table_name;"
```

## 6) Rollback

If SQL rollout causes runtime issue:

1. Re-point Cloud Run `DATABASE_URL` to previous secret version.
2. Deploy previous stable Cloud Run revision (`gcloud run services update-traffic`).
3. Keep shared instance unchanged; rollback is config-first, data rollback by DB backup/restore runbook.

## 7) Customer onboarding template (shared instance)

For each new customer/system, repeat:

1. Create DB user + DB name in shared SQL project.
2. Create dedicated secret in customer project (e.g. `customer-a-database-url`).
3. Grant runtime SA to read only that secret.
4. Grant runtime SA `roles/cloudsql.client` on shared SQL project.
5. Bind Cloud Run service to shared SQL instance and that secret.
6. Apply migration to that dedicated DB.

This keeps cost low (one instance) while preserving tenant/system isolation.
