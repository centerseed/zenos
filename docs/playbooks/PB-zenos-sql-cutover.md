# ZenOS SQL Cutover Runbook

Last updated: 2026-03-25
Owner: ZenOS Engineering
Status: Ready for rehearsal / production cutover

This runbook covers the one-time cutover from Firestore (runtime) to PostgreSQL as the sole source of truth for ZenOS. Follow each step in order. Do not skip sections.

---

## 0. Pre-flight checklist

Complete all items before scheduling a cutover window.

- [ ] Cloud SQL Proxy can connect on port 55433
  ```bash
  cloud-sql-proxy zentropy-4f7a5:asia-east1:zentropy-db --port 55433
  psql "postgresql://zenos_api:<password>@127.0.0.1:55433/zenos" -c "SELECT 1;"
  ```
- [ ] Integration tests all pass
  ```bash
  cd /Users/wubaizong/接案/ZenOS/src
  ../.venv/bin/python -m pytest ../tests/integration/ -v
  ```
- [ ] Firestore residual audit clean (no runtime Firestore imports in non-backup code)
  ```bash
  grep -r "firestore_repo" src/zenos/ --include="*.py" | grep -v "__pycache__"
  # Expected: only firestore_repo.py itself (cold backup, not imported at runtime)
  ```
- [ ] Dashboard build succeeds
  ```bash
  cd /Users/wubaizong/接案/ZenOS/dashboard && npm run build
  ```
- [ ] `scripts/import_firestore_to_sql.py` is executable and dry-run passes
  ```bash
  python scripts/import_firestore_to_sql.py --dry-run
  ```

---

## 1. Freeze (stop writes)

**Estimated window: 5 minutes**

1. Notify all users (Slack / email): "ZenOS will be in read-only mode for ~5 minutes for a planned migration. Please pause all writes."
2. How to confirm freeze is effective: check Cloud Run logs for absence of new write requests.
   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" AND resource.labels.service_name="zenos-mcp" AND textPayload=~"(POST|PUT|PATCH|write|upsert|create_task)"' \
     --project=zenos-naruvia \
     --limit=20 \
     --freshness=5m
   ```
   Expected: no new write-path log lines after the announcement.

---

## 2. Final sync (last Firestore → SQL import)

1. Run the import script for a final full sync:
   ```bash
   python /Users/wubaizong/接案/ZenOS/scripts/import_firestore_to_sql.py
   ```
2. Verify row counts match between Firestore and SQL:
   ```bash
   # SQL row counts
   psql "postgresql://zenos_api:<password>@127.0.0.1:55433/zenos" \
     -c "SELECT 'entities' as tbl, count(*) FROM zenos.entities
         UNION ALL SELECT 'tasks', count(*) FROM zenos.tasks
         UNION ALL SELECT 'documents', count(*) FROM zenos.documents
         UNION ALL SELECT 'relationships', count(*) FROM zenos.relationships;"
   ```
   Compare against Firestore collection sizes from Firebase Console. Counts must match within acceptable delta (zero delta preferred; document-level drift < 1% acceptable only if known-stale records).

---

## 3. Switch (deploy SQL-backed code)

Deploy the backend (MCP server) and Dashboard in sequence.

**3.1 Deploy Cloud Run (MCP server)**
```bash
./scripts/deploy_mcp.sh
```
Wait for the new revision to become healthy:
```bash
gcloud run revisions list \
  --service=zenos-mcp \
  --project=zenos-naruvia \
  --region=asia-east1 \
  --limit=3
```
Confirm the latest revision shows `ACTIVE` and traffic is routed to it.

**3.2 Deploy Dashboard + Firestore rules**
```bash
cd /Users/wubaizong/接案/ZenOS/dashboard && npm run build && firebase deploy --only hosting
firebase deploy --only firestore:rules
```

---

## 4. Smoke test

Run each check in order. All must pass before declaring Go.

**4.1 REST endpoints (replace `<TOKEN>` with a valid partner API key)**
```bash
BASE="https://zenos-mcp-<hash>-de.a.run.app"
TOKEN="<partner_api_key>"

# Partner info
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/api/partner/me" | jq .

# Entities by type
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/api/data/entities?type=product" | jq 'length'

# Tasks list
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/api/data/tasks" | jq 'length'
```
Expected: all three return HTTP 200 with non-empty JSON.

**4.2 MCP tool calls (via MCP client or CLI)**
```bash
# Search entities
mcp call search '{"collection": "entities"}' --partner-key="<key>"

# Create a smoke-test task
mcp call task '{"action": "create", "title": "smoke test", "created_by": "cutover"}' --partner-key="<key>"
```
Expected: `search` returns entity list; `task create` returns new task with `id`.

**4.3 Dashboard manual checks**
- Open https://zenos-naruvia.web.app in a browser
- Log in with a valid account
- Verify the Projects view loads (non-empty or empty-state, no error banner)
- Verify the Tasks view loads
- Verify the Knowledge Map view loads
- Click one entity to open the detail sheet

All checks must pass.

---

## 5. Go / No-go gate

**Decision maker:** ZenOS Engineering lead
**Decision window:** 30 minutes after switch deployment
**Slack channel:** #zenos-engineering

### Go conditions (all must be true)
- All smoke tests in section 4 passed
- Dashboard login, projects, tasks, and knowledge map load without error
- MCP write operation (task create) succeeded

### No-go trigger conditions (any one is sufficient)
- Any smoke test returned non-200 or unexpected empty response
- Dashboard login failed or showed blank/error page
- MCP write operation (task create) failed or returned no `id`
- Any endpoint response time consistently > 5 seconds

---

## 6. Rollback

**Trigger:** Any no-go condition in section 5.
**Maximum decision time:** 30 minutes. If unresolved, rollback immediately — do not attempt live fixes.

**Step 1 — Roll back Cloud Run to the previous revision**

Find the previous stable revision:
```bash
gcloud run revisions list \
  --service=zenos-mcp \
  --project=zenos-naruvia \
  --region=asia-east1 \
  --limit=5
```

Route 100% traffic back to it (replace `PREVIOUS_REVISION` with the actual revision name):
```bash
gcloud run services update-traffic zenos-mcp \
  --to-revisions=PREVIOUS_REVISION=100 \
  --project=zenos-naruvia \
  --region=asia-east1
```

**Step 2 — Roll back Dashboard to the previous Firebase Hosting release**
```bash
firebase hosting:channel:deploy rollback --project=zenos-naruvia
```

**Step 3 — Confirm service recovery**

Re-run the smoke tests from section 4. All must pass before declaring rollback complete.

**Escalation path:** If rollback itself fails, page the on-call engineer and do not make further changes until a human is on the line.

---

## 7. Post-cutover cleanup

Only after Go is confirmed and the service is stable for at least 24 hours:

- [ ] Remove `src/zenos/infrastructure/firestore_repo.py` (cold backup no longer needed)
- [ ] Audit and remove `firebase` / `google-cloud-firestore` from `pyproject.toml` if no other code imports it
  ```bash
  grep -r "from google.cloud import firestore\|import firestore" src/ --include="*.py"
  ```
- [ ] Update `CLAUDE.md` technology stack section:
  - Change "DB: Firestore" to "DB: PostgreSQL (Cloud SQL)"
  - Remove Firestore-related deploy instructions
- [ ] Archive Firestore backup (export via Firebase Console → Cloud Storage) before any cleanup
- [ ] Remove this runbook's pre-flight reference to `import_firestore_to_sql.py` and mark it archived

---

## Rehearsal Log

### Rehearsal #1 — 2026-03-25

**EXPLAIN ANALYZE results:**
- All 10 major queries use Index Scan, zero Seq Scan
- Slowest query: tasks_list_by_partner_status (planning 2ms + execution 0.2ms)
- No full table scans, no N+1

**Firestore residual audit:**
- Backend: `governance_ai.py` had Firestore residual in `_write_usage_log` → fixed (switched to SQL usage_logs)
- `firestore_repo.py` retained as cold backup; not imported at runtime
- `admin_api.py` retains `firebase_admin` for ID Token verification only, no Firestore SDK
- Dashboard: zero `firebase/firestore` imports

**Integration tests:** 18/18 pass (real DB)

**Issues found:**
1. `governance_ai.py` `_write_usage_log` was still writing to Firestore → fixed in this runbook prep cycle
2. `task_entities` join table missing FK constraint to `entities` → does not affect functionality, recorded as known issue
