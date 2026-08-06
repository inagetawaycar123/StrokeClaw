-- Minimal migration required by the 90-day mRS MVP router.
-- Safe to run repeatedly against an existing StrokeClaw patient_info table.
ALTER TABLE patient_info
  ADD COLUMN IF NOT EXISTS nihss_24h int
    CHECK (nihss_24h >= 0 AND nihss_24h <= 42),
  ADD COLUMN IF NOT EXISTS onset_to_ct_hours FLOAT8
    CHECK (onset_to_ct_hours >= 0);
