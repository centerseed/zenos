-- Add invite_expires_at to partners table
ALTER TABLE zenos.partners
  ADD COLUMN IF NOT EXISTS invite_expires_at timestamptz NULL;

COMMENT ON COLUMN zenos.partners.invite_expires_at IS
  'When the invite link expires. NULL = no expiry (internal members). '
  'Set to now() + 7 days on invite; validated on /api/partners/activate.';
