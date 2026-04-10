-- Add preferences JSONB column to partners table for onboarding state and user preferences.
-- ADR-023: Dashboard Onboarding

ALTER TABLE zenos.partners
ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}';

COMMENT ON COLUMN zenos.partners.preferences IS 'User preferences JSONB: onboarding state, platform type, UI settings';
