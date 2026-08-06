-- ==================== Supabase 医学影像表创建脚本 ====================
-- 针对 patient_info.id 为 BIGINT 的情况
-- 执行环境：Supabase Dashboard SQL Editor
-- 权限设置：anon_public（允许匿名用户和认证用户访问）

-- ==================== 1. 创建医学影像记录表 ====================

CREATE TABLE IF NOT EXISTS patient_imaging (
    id BIGSERIAL PRIMARY KEY,
    
    -- 关键字段
    patient_id BIGINT REFERENCES patient_info(id) ON DELETE CASCADE,
    case_id VARCHAR(50) UNIQUE NOT NULL,  -- 对应 file_id，用于追踪一个病例的所有图像
    
    -- 原始图像（NIfTI格式）
    mcta_raw_url VARCHAR(500),
    ncct_raw_url VARCHAR(500),
    
    -- 处理后的切片图像 (JSON格式)
    -- 结构：{"slice_000": [{"filename": "slice_000_mcta.png", "url": "https://..."}, ...], ...}
    processed_image_urls JSONB DEFAULT '{}'::JSONB,
    
    -- 脑卒中分析结果（JSON格式）
    -- 结构：{"penumbra": [...urls...], "core": [...urls...], "combined": [...urls...]}
    stroke_analysis_urls JSONB DEFAULT '{}'::JSONB,
    
    -- 分析指标（JSON格式）
    analysis_result JSONB DEFAULT '{}'::JSONB,
    
    -- 其他信息
    hemisphere VARCHAR(50),  -- 'left', 'right', 'both'
    notes TEXT,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ==================== 2. 创建索引 ====================

CREATE INDEX IF NOT EXISTS idx_patient_imaging_case_id ON patient_imaging(case_id);
CREATE INDEX IF NOT EXISTS idx_patient_imaging_patient_id ON patient_imaging(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_imaging_created_at ON patient_imaging(created_at);

-- ==================== 3. 行级安全策略 (RLS) ====================

-- 启用 RLS
ALTER TABLE patient_imaging ENABLE ROW LEVEL SECURITY;

-- 创建策略：允许匿名用户和认证用户读取
CREATE POLICY "Allow anon_public read" ON patient_imaging
FOR SELECT 
USING (auth.role() = 'anon' OR auth.role() = 'authenticated');

-- 创建策略：允许匿名用户和认证用户插入
CREATE POLICY "Allow anon_public insert" ON patient_imaging
FOR INSERT 
WITH CHECK (auth.role() = 'anon' OR auth.role() = 'authenticated');

-- 创建策略：允许匿名用户和认证用户更新
CREATE POLICY "Allow anon_public update" ON patient_imaging
FOR UPDATE 
USING (auth.role() = 'anon' OR auth.role() = 'authenticated');

-- 创建策略：允许匿名用户和认证用户删除（可选）
CREATE POLICY "Allow anon_public delete" ON patient_imaging
FOR DELETE 
USING (auth.role() = 'anon' OR auth.role() = 'authenticated');

-- ==================== 4. 创建视图 ====================

-- 删除旧视图（如果存在 SECURITY DEFINER 版本）
DROP VIEW IF EXISTS imaging_analysis_summary;

-- 创建视图（使用默认 SECURITY INVOKER，确保 RLS 策略生效）
-- SECURITY INVOKER 模式：视图使用调用者的权限执行，遵守 RLS 策略
CREATE VIEW imaging_analysis_summary 
WITH (security_invoker = true)
AS
SELECT
    pi.id,
    pi.case_id,
    pi.patient_id,
    pinfo.patient_name,
    pinfo.patient_age,
    pinfo.patient_sex,
    pi.hemisphere,
    pi.analysis_result->>'total_slices' AS total_slices,
    (pi.analysis_result->>'penumbra_volume_ml')::float AS penumbra_volume_ml,
    (pi.analysis_result->>'core_volume_ml')::float AS core_volume_ml,
    (pi.analysis_result->>'mismatch_ratio')::float AS mismatch_ratio,
    (pi.analysis_result->>'has_mismatch')::boolean AS has_mismatch,
    pi.analysis_result->>'analyzed_at' AS analyzed_at,
    pi.created_at,
    pi.updated_at
FROM patient_imaging pi
LEFT JOIN patient_info pinfo ON pi.patient_id = pinfo.id
WHERE pi.analysis_result IS NOT NULL AND pi.analysis_result != '{}'::JSONB;

-- 添加视图说明
COMMENT ON VIEW imaging_analysis_summary IS 
'医学影像分析汇总视图 - 使用 SECURITY INVOKER 模式确保 RLS 策略生效，防止权限提升风险';

-- ==================== 5. 视图权限配置 ====================

-- 为视图授予 anon 和 authenticated 角色的查询权限
GRANT SELECT ON imaging_analysis_summary TO anon;
GRANT SELECT ON imaging_analysis_summary TO authenticated;

-- 如果需要允许服务角色（service_role）访问（用于后端管理操作）
GRANT SELECT ON imaging_analysis_summary TO service_role;

-- ==================== 完成 ====================
-- 表和视图创建成功！权限已正确配置。
-- 现在可以在后端使用 supabase_storage 模块了
