-- =============================================================
-- 数据中心机房准入系统 v0.5：工单扩展 + 快速预约 + 两级审批
-- 对库 dc_access_system 执行
-- =============================================================

-- 1. work_orders 扩展字段（来访人员 JSON、进出时间、原因、区域、陪同人员）
ALTER TABLE work_orders
  ADD COLUMN visitors TEXT COMMENT '来访人员JSON [{name,id_card,phone,unit}]',
  ADD COLUMN entry_time VARCHAR(32) DEFAULT '' COMMENT '进入时间(精确到分钟)',
  ADD COLUMN exit_time VARCHAR(32) DEFAULT '' COMMENT '出去时间',
  ADD COLUMN reason VARCHAR(32) DEFAULT '' COMMENT '进出原因',
  ADD COLUMN area VARCHAR(128) DEFAULT '' COMMENT '活动区域',
  ADD COLUMN accompanying_person VARCHAR(64) DEFAULT '' COMMENT '陪同人员';

-- 2. 删旧字段（visit_time/visit_scale/lead_person 不再使用）
ALTER TABLE work_orders
  DROP COLUMN visit_time,
  DROP COLUMN visit_scale,
  DROP COLUMN lead_person;

-- 3. 快速预约表（内容同工单 + 访客 id）
CREATE TABLE IF NOT EXISTS reservations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  visitor_id INT NOT NULL COMMENT '访客 users.id',
  company VARCHAR(128) NOT NULL COMMENT '来访单位',
  visitors TEXT COMMENT '来访人员JSON',
  entry_time VARCHAR(32) DEFAULT '',
  exit_time VARCHAR(32) DEFAULT '',
  reason VARCHAR(32) DEFAULT '',
  area VARCHAR(128) DEFAULT '',
  contact_name VARCHAR(64) DEFAULT '',
  contact_phone VARCHAR(20) DEFAULT '',
  accompanying_person VARCHAR(64) DEFAULT '',
  status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/approved/rejected',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. approval_records 加 reservation_id（预约审批用）
ALTER TABLE approval_records ADD COLUMN reservation_id INT DEFAULT NULL;

-- 5. credentials 加 reservation_id，work_order_id 改可空（凭证可来自工单或预约）
ALTER TABLE credentials ADD COLUMN reservation_id INT DEFAULT NULL;
ALTER TABLE credentials MODIFY COLUMN work_order_id INT DEFAULT NULL;

-- 6. 两级审批：清空旧审批数据 + 重建节点和连线（机房主管 → 部门主管）
DELETE FROM approval_history;
DELETE FROM approval_tasks;
DELETE FROM approval_records;
DELETE FROM workflow_transitions;
DELETE FROM approval_steps;
INSERT INTO approval_steps (step_name, step_order, required_role, node_x, node_y) VALUES
('机房主管审批', 1, '机房主管', 100, 100),
('部门主管审批', 2, '部门主管', 300, 100);
INSERT INTO workflow_transitions (from_step_id, to_step_id)
SELECT a.id, b.id FROM approval_steps a, approval_steps b
WHERE a.required_role = '机房主管' AND b.required_role = '部门主管';

-- 7. 管理员角色改两级（按你实际角色名调整）
UPDATE admin_users SET role='机房主管' WHERE role='机房管理员';
UPDATE admin_users SET role='部门主管' WHERE role='中心负责人';
-- 若有其它角色（如"安全管理员"），请手动改成"机房主管"或"部门主管"
