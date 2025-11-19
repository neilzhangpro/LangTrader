-- 添加自定义提示词字段
-- 执行: psql -d langtrader -f database/add_custom_prompts.sql

-- 添加自定义系统提示词
ALTER TABLE traders ADD COLUMN IF NOT EXISTS custom_system_prompt TEXT;

-- 添加自定义用户提示词模板
ALTER TABLE traders ADD COLUMN IF NOT EXISTS custom_user_prompt TEXT;

-- 添加注释
COMMENT ON COLUMN traders.custom_system_prompt IS '自定义系统提示词（AI角色定义），如果设置则完全替换默认system_prompt';
COMMENT ON COLUMN traders.custom_user_prompt IS '自定义用户提示词模板（支持变量占位符），如果设置则完全替换默认user_prompt生成逻辑';

-- 查看结果
\d traders;

