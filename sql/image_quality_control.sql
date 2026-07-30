-- Image Quality Control (图像质控) table
-- Persists QC results per imaging case so they survive restarts
-- and can be reviewed / overridden by doctors.

CREATE TABLE IF NOT EXISTS image_quality_control (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id      TEXT NOT NULL DEFAULT '',
    case_id         TEXT NOT NULL DEFAULT '',
    run_id          TEXT NOT NULL DEFAULT '',

    -- QC agent output fields (mirroring image_qc.py run_full_qc return)
    qc_status               TEXT NOT NULL DEFAULT 'unknown',        -- passed | warning | failed
    qc_score                NUMERIC(6,4) NOT NULL DEFAULT 0.0,
    qc_file_readable        BOOLEAN NOT NULL DEFAULT FALSE,
    qc_modality_complete    BOOLEAN NOT NULL DEFAULT FALSE,
    qc_scan_coverage        TEXT NOT NULL DEFAULT 'unknown',        -- complete | incomplete | unknown
    qc_slice_thickness_status TEXT NOT NULL DEFAULT 'unknown',      -- normal | abnormal | unknown
    qc_brain_area_variation TEXT NOT NULL DEFAULT 'unknown',        -- normal | abnormal | unknown
    qc_motion_artifact_level TEXT NOT NULL DEFAULT 'unknown',       -- none | mild | moderate | severe | unknown
    qc_metal_artifact_level  TEXT NOT NULL DEFAULT 'unknown',
    qc_noise_level           TEXT NOT NULL DEFAULT 'unknown',       -- normal | moderate | severe | unknown
    qc_contrast_phase_status TEXT NOT NULL DEFAULT 'unknown',       -- complete | incomplete | unknown
    qc_enhancement_quality   TEXT NOT NULL DEFAULT 'unknown',       -- good | weak | failed | unknown
    qc_missing_phase         TEXT[] DEFAULT '{}',
    qc_warning_message       TEXT NOT NULL DEFAULT '',
    qc_affected_nodes        TEXT[] DEFAULT '{}',
    qc_blocking_required     BOOLEAN NOT NULL DEFAULT FALSE,
    qc_review_required       BOOLEAN NOT NULL DEFAULT FALSE,
    qc_review_reason         TEXT NOT NULL DEFAULT '',

    -- Doctor review fields
    qc_review_action         TEXT DEFAULT NULL,        -- accept | reject
    qc_review_comment        TEXT DEFAULT NULL,
    qc_reviewed_by           TEXT DEFAULT NULL,
    qc_reviewed_at           TIMESTAMPTZ DEFAULT NULL,

    -- Raw snapshot of the full QC result dict (JSON)
    qc_raw_payload           JSONB DEFAULT '{}',

    -- Available modalities at time of QC
    available_modalities     TEXT[] DEFAULT '{}',

    -- Metadata
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Uniqueness: one QC record per (case_id, run_id)
    CONSTRAINT uq_qc_case_run UNIQUE (case_id, run_id)
);

-- Index for lookup by case_id
CREATE INDEX IF NOT EXISTS idx_image_quality_control_case
    ON image_quality_control (case_id);

-- Index for lookup by run_id
CREATE INDEX IF NOT EXISTS idx_image_quality_control_run
    ON image_quality_control (run_id);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_image_quality_control_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_image_quality_control_updated_at
    ON image_quality_control;
CREATE TRIGGER trg_image_quality_control_updated_at
    BEFORE UPDATE ON image_quality_control
    FOR EACH ROW
    EXECUTE FUNCTION update_image_quality_control_updated_at();
