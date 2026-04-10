-- Plans table
CREATE TABLE IF NOT EXISTS zenos.plans (
    id          TEXT        NOT NULL,
    partner_id  TEXT        NOT NULL REFERENCES zenos.partners(id),
    goal        TEXT        NOT NULL,
    owner       TEXT,
    status      TEXT        NOT NULL DEFAULT 'draft',
    entry_criteria TEXT,
    exit_criteria  TEXT,
    project     TEXT        NOT NULL DEFAULT '',
    project_id  TEXT,
    created_by  TEXT        NOT NULL,
    updated_by  TEXT,
    result      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (partner_id, id)
);

CREATE INDEX IF NOT EXISTS idx_plans_partner_status ON zenos.plans(partner_id, status);
CREATE INDEX IF NOT EXISTS idx_plans_partner_project ON zenos.plans(partner_id, project) WHERE project != '';

-- Auto-create placeholder plans from existing task.plan_id
INSERT INTO zenos.plans (id, partner_id, goal, owner, status, entry_criteria, exit_criteria, created_by, project)
SELECT DISTINCT
    t.plan_id, t.partner_id,
    '（自動遷移）' || t.plan_id, 'system:migration', 'draft',
    'Legacy plan grouping imported from existing tasks.',
    'Owner defines explicit completion boundary after reviewing imported tasks.',
    COALESCE((SELECT created_by FROM zenos.tasks t2 WHERE t2.partner_id = t.partner_id AND t2.plan_id = t.plan_id ORDER BY t2.created_at LIMIT 1), 'system'),
    COALESCE((SELECT project FROM zenos.tasks t2 WHERE t2.partner_id = t.partner_id AND t2.plan_id = t.plan_id AND t2.project != '' ORDER BY t2.created_at LIMIT 1), '')
FROM zenos.tasks t WHERE t.plan_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- FK constraint
ALTER TABLE zenos.tasks ADD CONSTRAINT fk_tasks_plan_id FOREIGN KEY (partner_id, plan_id) REFERENCES zenos.plans(partner_id, id);
