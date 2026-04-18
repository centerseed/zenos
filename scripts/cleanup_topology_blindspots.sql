-- Cleanup topology blindspots that have no UI consumer and produce 89% false positives.
-- Executed manually by Architect on 2026-04-18 as part of verb+topology removal.
DELETE FROM zenos.blindspots
WHERE description ILIKE '%沒有任何關聯%'
   OR description ILIKE '%出邊%'
   OR description ILIKE '%循環依賴%';
