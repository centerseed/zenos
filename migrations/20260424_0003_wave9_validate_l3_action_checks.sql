-- Wave 9 Phase D05: validate L3-Action CHECK constraints after parent backfill.

ALTER TABLE zenos.entity_l3_task
    VALIDATE CONSTRAINT entity_l3_task_review_needs_result;
