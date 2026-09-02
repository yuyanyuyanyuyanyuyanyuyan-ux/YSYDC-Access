-- =============================================================
-- 数据中心机房准入系统 v0.6：工单结构自定义（可增删改条款 + 恢复默认）
-- 对库 dc_access_system 执行
-- =============================================================

-- 1. 删除上一版临时表（若有）
DROP TABLE IF EXISTS work_order_custom_fields;

-- 2. 工单字段定义表（默认结构 + 自定义，统一管理）
CREATE TABLE IF NOT EXISTS work_order_fields (
  id INT AUTO_INCREMENT PRIMARY KEY,
  field_key VARCHAR(64) NOT NULL UNIQUE
    COMMENT '内部标识：默认字段映射固定列(company/entry_time...)，自定义字段为 custom_{id}',
  field_name VARCHAR(64) NOT NULL COMMENT '显示名，如「来访单位」',
  input_type VARCHAR(16) NOT NULL DEFAULT 'text'
    COMMENT '输入方式：text/textarea/select/date/time/datetime/visitors(来访人员多人列表)',
  options TEXT COMMENT '选择框选项 JSON 数组（仅 select 使用）',
  required TINYINT NOT NULL DEFAULT 0 COMMENT '是否必填：0否 1是',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序，越小越靠前',
  is_default TINYINT NOT NULL DEFAULT 0 COMMENT '是否默认字段（恢复默认时据此重建）',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单字段定义（默认结构+自定义）';

-- 3. work_orders 增加自定义字段值列（自定义字段的值存这里，JSON key=field_key）
ALTER TABLE work_orders
  ADD COLUMN custom_fields TEXT COMMENT '自定义字段值 JSON，如 {"custom_1":"xxx"}';

-- 4. 默认工单结构（9 个字段）
INSERT INTO work_order_fields (field_key, field_name, input_type, options, required, sort_order, is_default) VALUES
('company',            '来访单位',        'text',     NULL,                                             1, 1, 1),
('visitors',           '来访人员',        'visitors', NULL,                                             0, 2, 1),
('entry_time',         '进入时间',        'datetime', NULL,                                             0, 3, 1),
('exit_time',          '出去时间',        'datetime', NULL,                                             0, 4, 1),
('reason',             '进出原因',        'select',   '["设备维护","施工","参观考察","业务洽谈","其他"]', 0, 5, 1),
('area',               '活动区域',        'text',     NULL,                                             0, 6, 1),
('contact_name',       '来访单位联系人',  'text',     NULL,                                             0, 7, 1),
('contact_phone',      '联系人电话',      'text',     NULL,                                             0, 8, 1),
('accompanying_person','陪同人员',        'text',     NULL,                                             0, 9, 1);
