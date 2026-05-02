---
doc_id: TEST-governance-task-link-resilience
title: 測試場景：Governance task link inference resilience
type: TEST
ontology_entity: 語意治理 Pipeline
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 測試場景：Governance task link inference resilience

## P0 Scenarios

### P0-1 Large candidate set is chunked

- AC IDs: AC-GTLR-01
- Given `existing_entities` exceeds the chunk limit
- When `infer_task_links` runs
- Then LLM is called once per chunk
- And no chunk prompt contains more than the allowed number of entity lines

### P0-2 Partial chunk failure keeps successful links

- AC IDs: AC-GTLR-02
- Given one chunk raises during structured parsing
- And another chunk returns valid `entity_ids`
- When inference completes
- Then the valid IDs are returned
- And the failed chunk does not force `[]`

### P0-3 All chunk failure uses deterministic fallback

- AC IDs: AC-GTLR-03
- Given all LLM calls fail
- And task text clearly overlaps candidate names or summaries
- When fallback runs
- Then at most 3 candidate IDs are returned
- And only input candidate IDs are returned

### P0-4 LLM output is sanitized

- AC IDs: AC-GTLR-04
- Given LLM returns duplicate IDs and IDs not present in candidates
- When results are merged
- Then duplicates and unknown IDs are removed while preserving first-seen order

## P1 Scenarios

### P1-1 Audit summary records resilience state

- AC IDs: AC-GTLR-05
- Given chunk failure or fallback occurs
- When audit event is emitted
- Then payload includes model, task_title, candidate_entities_count, chunk_count, failed_chunk_count, fallback_used
