ALTER TABLE patient_imaging
ADD COLUMN available_modalities text[] DEFAULT '{}'::text[];