-- Simplify task creator model:
-- 1) created_by should be partner_id (owner)
-- 2) source_metadata_json keeps only:
--    - created_via_agent (bool)
--    - agent_name (string, optional)
--    - actor_partner_id (owner partner id)
-- 3) legacy actor_* keys are removed

-- Normalize legacy created_by values to owner partner_id when they are not partner IDs.
UPDATE zenos.tasks
SET created_by = partner_id
WHERE created_by IS NOT NULL
  AND created_by !~* '^[0-9a-f]{32}$'
  AND partner_id IS NOT NULL
  AND partner_id ~* '^[0-9a-f]{32}$';

-- Backfill simplified source metadata while preserving other provenance fields.
UPDATE zenos.tasks
SET source_metadata_json =
  (
    COALESCE(source_metadata_json, '{}'::jsonb)
    || jsonb_build_object(
      'created_via_agent',
      COALESCE(
        (source_metadata_json->>'created_via_agent')::boolean,
        CASE
          WHEN source_metadata_json->>'actor_type' = 'human' THEN false
          ELSE true
        END
      ),
      'agent_name',
      COALESCE(
        NULLIF(source_metadata_json->>'agent_name', ''),
        NULLIF(source_metadata_json->>'actor_name', ''),
        CASE
          WHEN lower(COALESCE(created_by, '')) = 'system' THEN 'system-auto'
          WHEN COALESCE(created_by, '') ~* '-agent$' THEN created_by
          ELSE 'agent'
        END
      ),
      'actor_partner_id',
      COALESCE(
        NULLIF(source_metadata_json->>'actor_partner_id', ''),
        NULLIF(created_by, ''),
        NULLIF(partner_id, '')
      )
    )
  )
  - 'actor_type'
  - 'actor_name'
  - 'actor_session';
