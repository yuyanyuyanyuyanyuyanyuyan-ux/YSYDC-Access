-- =============================================================
-- 数据中心机房准入系统 v0.3 迁移脚本
-- 新增：业务部成员、工单、准入凭证；调整 users 与 approval_records
-- 用 Navicat / MySQL 客户端对库 dc_access_system 执行
-- =============================================================

-- 1. 业务部成员表
CREATE TABLE IF NOT EXISTS business_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password VARCHAR(128) NOT NULL,
  real_name VARCHAR(64) DEFAULT '',
  phone VARCHAR(20) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 工单表（业务部成员提交的来访申请）
CREATE TABLE IF NOT EXISTS work_orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  business_member_id INT NOT NULL,
  company VARCHAR(128) NOT NULL COMMENT '访客公司名称',
  visit_time VARCHAR(64) DEFAULT '' COMMENT '访问时间',
  visit_scale VARCHAR(64) DEFAULT '' COMMENT '访问规模',
  contact_name VARCHAR(64) DEFAULT '' COMMENT '访问方联络人姓名',
  contact_phone VARCHAR(20) DEFAULT '' COMMENT '访问方联络人电话',
  lead_person VARCHAR(64) DEFAULT '' COMMENT '数据中心带领人',
  status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/approved/rejected',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 准入凭证表（访客考试通过后生成）
CREATE TABLE IF NOT EXISTS credentials (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '访客 users.id',
  work_order_id INT NOT NULL COMMENT '匹配的工单 work_orders.id',
  exam_record_id INT NOT NULL COMMENT '考试记录 exam_records.id',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. users（访客）加一列：匹配到的工单
ALTER TABLE users ADD COLUMN work_order_id INT DEFAULT NULL;

-- 5. approval_records：审批对象从「访客+考试」改为「工单」
ALTER TABLE approval_records ADD COLUMN work_order_id INT DEFAULT NULL;
-- 删除旧列（会丢旧审批数据；开发期直接执行）
ALTER TABLE approval_records DROP COLUMN user_id;
ALTER TABLE approval_records DROP COLUMN exam_record_id;

-- 6. 测试业务部成员
INSERT INTO business_members (username, password, real_name, phone) VALUES
('biz001', '123456', '业务部测试员', '13900000001')
ON DUPLICATE KEY UPDATE username = username;
