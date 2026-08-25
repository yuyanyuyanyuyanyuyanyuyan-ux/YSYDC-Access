from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from database import get_connection
import pymysql

app = FastAPI(
    title="数据中心机房准入系统",
    description="用于处理人员登记、考试和审批",
    version="0.1.0"
)


def get_db_connection():
    connection = pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="20060306",
        database="dc_access_system",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection


# =========================
# 请求数据模型
# =========================

class RegisterRequest(BaseModel):
    name: str
    phone: str
    company: str
    identity_type: str
    visit_purpose: str

class ExamSubmit(BaseModel):
    user_id: int
    answers: dict

class ApprovalAction(BaseModel):
    admin_id: int
    action: str
    comment: str = ""

class AdminLogin(BaseModel):
    username: str
    password: str

# =========================
# 首页测试
# =========================

@app.get("/")
def root():
    return {"message": "数据中心机房准入系统后端运行成功"}

# =========================
# API 测试
# =========================

@app.get("/api/test")
def test():
    return {"success": True, "message": "后端 API 测试成功"}

# =========================
# 数据库连接测试
# =========================

@app.get("/api/test-db")
def test_database():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS database_name")
            result = cursor.fetchone()
        return {"success": True, "message": "MySQL 数据库连接成功", "database": result}
    finally:
        connection.close()

# =========================
# 用户登记接口
# =========================

@app.post("/api/register")
def register_user(user: RegisterRequest):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO users (name, phone, company, identity_type, visit_purpose)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (user.name, user.phone, user.company, user.identity_type, user.visit_purpose))
            connection.commit()
            user_id = cursor.lastrowid
        return {"success": True, "message": "用户登记成功", "user_id": user_id}
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

# =========================
# 获取考试题目
# =========================

@app.get("/api/questions")
def get_questions():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT id, question, option_a, option_b, option_c, option_d, score
                FROM questions
                WHERE is_active = TRUE
                ORDER BY id
            """
            cursor.execute(sql)
            questions = cursor.fetchall()
        return {"success": True, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

@app.post("/api/submit-exam")
def submit_exam(data: ExamSubmit):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id, correct_answer FROM questions"
            cursor.execute(sql)
            questions = cursor.fetchall()
            score = 0
            answer_map = {0: "A", 1: "B", 2: "C", 3: "D"}
            for question in questions:
                question_id = question["id"]
                correct_answer = question["correct_answer"]
                user_answer_index = data.answers.get(str(question_id))
                if user_answer_index is not None:
                    user_answer = answer_map.get(user_answer_index)
                    if user_answer == correct_answer:
                        score += 10
            passed = score >= 70

            insert_exam_sql = """
                INSERT INTO exam_records (user_id, score, passed)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_exam_sql, (data.user_id, score, passed))
            exam_id = cursor.lastrowid

            if passed:
                insert_approval_sql = """
                    INSERT INTO approval_records (user_id, exam_record_id, status)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(insert_approval_sql, (data.user_id, exam_id, "pending"))
                approval_record_id = cursor.lastrowid

                cursor.execute("""
                    SELECT id, required_role
                    FROM approval_steps
                    ORDER BY step_order ASC
                    LIMIT 1
                """)
                first_step = cursor.fetchone()
                if first_step:
                    step_id = first_step["id"]
                    required_role = first_step["required_role"]
                    cursor.execute("""
                        SELECT id FROM admin_users
                        WHERE role = %s
                        LIMIT 1
                    """, (required_role,))
                    admin = cursor.fetchone()
                    if admin:
                        admin_id = admin["id"]
                        cursor.execute("""
                            INSERT INTO approval_tasks (approval_record_id, step_id, admin_id, status)
                            VALUES (%s, %s, %s, 'pending')
                        """, (approval_record_id, step_id, admin_id))

            connection.commit()
            return {
                "success": True,
                "score": score,
                "passed": passed,
                "message": "考试通过，已提交管理员审批" if passed else "考试未通过"
            }
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()

@app.get("/api/admin/{admin_id}/pending-tasks")
def get_pending_tasks(admin_id: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        sql = """
        SELECT
            approval_tasks.id AS task_id,
            approval_records.id AS approval_record_id,
            approval_tasks.status,
            approval_tasks.created_at,
            users.name,
            users.phone,
            users.company,
            users.identity_type,
            users.visit_purpose,
            exam_records.score,
            approval_steps.step_name
        FROM approval_tasks
        JOIN approval_records ON approval_tasks.approval_record_id = approval_records.id
        JOIN users ON approval_records.user_id = users.id
        JOIN exam_records ON approval_records.exam_record_id = exam_records.id
        JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
        WHERE approval_tasks.admin_id = %s
        AND approval_tasks.status = 'pending'
        ORDER BY approval_tasks.created_at ASC
        """
        cursor.execute(sql, (admin_id,))
        tasks = cursor.fetchall()
        return {"success": True, "tasks": tasks}
    finally:
        cursor.close()
        connection.close()

@app.post("/api/approval-task/{task_id}/action")
def handle_approval(task_id: int, data: ApprovalAction):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        # 1. 查询当前审批任务
        cursor.execute("""
            SELECT id, approval_record_id, step_id, admin_id, status
            FROM approval_tasks
            WHERE id = %s
        """, (task_id,))
        task = cursor.fetchone()

        if not task:
            return {"success": False, "message": "审批任务不存在"}

        if task["admin_id"] != data.admin_id:
            return {"success": False, "message": "无权审批该任务"}

        if task["status"] != "pending":
            return {"success": False, "message": "该任务已经处理"}

        if data.action not in ["approved", "rejected"]:
            return {"success": False, "message": "审批操作错误"}

        # 校验审批意见（拒绝必填）
        if data.action == "rejected" and (not data.comment or not data.comment.strip()):
            return {"success": False, "message": "拒绝审批时必须填写拒绝原因"}

        # 2. 更新当前审批任务
        cursor.execute("""
            UPDATE approval_tasks
            SET status = %s, comment = %s, approved_at = NOW()
            WHERE id = %s
        """, (data.action, data.comment, task_id))

        # 3. 写入审批历史（仅一次）
        cursor.execute("""
            INSERT INTO approval_history (approval_record_id, task_id, step_id, admin_id, action, comment)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            task["approval_record_id"],
            task_id,
            task["step_id"],
            data.admin_id,
            data.action,
            data.comment
        ))

        # 4. 如果拒绝
        if data.action == "rejected":
            cursor.execute("""
                UPDATE approval_records
                SET status = 'rejected'
                WHERE id = %s
            """, (task["approval_record_id"],))
            connection.commit()
            return {"success": True, "message": "审批已拒绝，流程结束", "status": "rejected"}

        # 5. 查询当前步骤
        cursor.execute("""
            SELECT step_order
            FROM approval_steps
            WHERE id = %s
        """, (task["step_id"],))
        current_step = cursor.fetchone()

        if not current_step:
            connection.rollback()
            return {"success": False, "message": "当前审批步骤不存在"}

        current_order = current_step["step_order"]

        # 6. 查询下一审批步骤
        cursor.execute("""
            SELECT id, step_order, required_role, approver_type
            FROM approval_steps
            WHERE step_order > %s
            ORDER BY step_order ASC
            LIMIT 1
        """, (current_order,))
        next_step = cursor.fetchone()

        # 7. 没有下一步
        if not next_step:
            cursor.execute("""
                UPDATE approval_records
                SET status = 'approved'
                WHERE id = %s
            """, (task["approval_record_id"],))
            connection.commit()
            return {"success": True, "message": "审批全部完成", "status": "approved"}

        # 8. 查询下一审批管理员
        approver_type = next_step.get("approver_type", "role")

        if approver_type == "role":
            required_role = next_step["required_role"]
            cursor.execute("""
                SELECT id, real_name, role, parent_admin_id
                FROM admin_users
                WHERE role = %s
                LIMIT 1
            """, (required_role,))
            next_admin = cursor.fetchone()

        elif approver_type == "parent":
            cursor.execute("""
                SELECT parent_admin_id
                FROM admin_users
                WHERE id = %s
            """, (task["admin_id"],))
            current_admin = cursor.fetchone()

            if not current_admin:
                connection.rollback()
                return {"success": False, "message": "当前审批管理员不存在"}

            parent_admin_id = current_admin["parent_admin_id"]
            if not parent_admin_id:
                connection.rollback()
                return {"success": False, "message": "当前审批管理员没有设置直属上级"}

            cursor.execute("""
                SELECT id, real_name, role, parent_admin_id
                FROM admin_users
                WHERE id = %s
            """, (parent_admin_id,))
            next_admin = cursor.fetchone()

        else:
            connection.rollback()
            return {"success": False, "message": "未知的审批人类型：" + str(approver_type)}

        if not next_admin:
            connection.rollback()
            return {"success": False, "message": "找不到下一审批管理员"}

        # 9. 创建下一审批任务
        cursor.execute("""
            INSERT INTO approval_tasks (approval_record_id, step_id, admin_id, status)
            VALUES (%s, %s, %s, 'pending')
        """, (
            task["approval_record_id"],
            next_step["id"],
            next_admin["id"]
        ))

        # 10. 提交事务
        connection.commit()

        # 11. 返回结果
        return {
            "success": True,
            "message": "当前审批已通过，已提交至下一审批人",
            "status": "pending",
            "next_admin": {
                "id": next_admin["id"],
                "real_name": next_admin["real_name"],
                "role": next_admin["role"]
            },
            "next_step": next_step["step_order"]
        }

    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        cursor.close()
        connection.close()

@app.post("/api/admin/login")
def admin_login(data: AdminLogin):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, username, password, real_name, phone, role, parent_admin_id
            FROM admin_users
            WHERE username = %s
        """, (data.username,))
        admin = cursor.fetchone()
        if not admin:
            return {"success": False, "message": "管理员账号不存在"}
        if admin["password"] != data.password:
            return {"success": False, "message": "密码错误"}
        return {
            "success": True,
            "message": "登录成功",
            "admin": {
                "id": admin["id"],
                "username": admin["username"],
                "real_name": admin["real_name"],
                "phone": admin["phone"],
                "role": admin["role"],
                "parent_admin_id": admin["parent_admin_id"]
            }
        }
    finally:
        cursor.close()
        connection.close()

# =========================
# 查询审批历史
# =========================

@app.get("/api/approval/{approval_record_id}/history")
def get_approval_history(approval_record_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                    approval_history.id,
                    approval_history.action,
                    approval_history.comment,
                    approval_history.created_at,
                    approval_steps.step_name,
                    approval_steps.step_order,
                    admin_users.real_name,
                    admin_users.role
                FROM approval_history
                JOIN approval_steps ON approval_history.step_id = approval_steps.id
                JOIN admin_users ON approval_history.admin_id = admin_users.id
                WHERE approval_history.approval_record_id = %s
                ORDER BY approval_history.created_at ASC, approval_steps.step_order ASC
            """
            cursor.execute(sql, (approval_record_id,))
            history = cursor.fetchall()
            return {"success": True, "history": history}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cursor.close()
        connection.close()

# =========================
# 查询完整工单详情（含审批历史）
# =========================

@app.get("/api/approval-detail/{approval_record_id}")
def get_approval_detail(approval_record_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. 获取基本信息
            cursor.execute("""
                SELECT
                    users.name, users.phone, users.company, users.identity_type, users.visit_purpose,
                    exam_records.score, exam_records.submitted_at AS exam_submitted_at,
                    approval_records.status AS approval_status,
                    approval_records.created_at AS application_time
                FROM approval_records
                JOIN users ON approval_records.user_id = users.id
                JOIN exam_records ON approval_records.exam_record_id = exam_records.id
                WHERE approval_records.id = %s
            """, (approval_record_id,))
            detail = cursor.fetchone()

            if not detail:
                return {"success": False, "message": "审批记录不存在"}

            # 2. 逻辑判断（不依赖数字）：查询是否存在待办任务
            cursor.execute("""
                SELECT id FROM approval_tasks
                WHERE approval_record_id = %s AND status = 'pending'
                LIMIT 1
            """, (approval_record_id,))
            pending_task = cursor.fetchone()

            if pending_task:
                # 存在待办任务，必定是“待审批”
                detail["approval_status"] = "pending"
            else:
                # 无待办任务，根据 final status 字符串判断（如果是字符串类型）
                # 注意：如果数据库是数字且无映射，这里返回的是数字。
                # 建议在前端配合使用：只要存在 current_task 就显示“待审批”
                detail["approval_status"] = detail["approval_status"]

            # 3. 查询当前待办任务
            cursor.execute("""
                SELECT approval_tasks.id AS task_id, approval_steps.step_name AS current_step_name
                FROM approval_tasks
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                WHERE approval_tasks.approval_record_id = %s
                AND approval_tasks.status = 'pending'
                LIMIT 1
            """, (approval_record_id,))
            current_task = cursor.fetchone()

            # 4. 获取完整审批历史
            cursor.execute("""
                SELECT
                    approval_history.action, approval_history.comment, approval_history.created_at,
                    approval_steps.step_name, approval_steps.step_order,
                    admin_users.real_name AS approver_name, admin_users.role
                FROM approval_history
                JOIN approval_steps ON approval_history.step_id = approval_steps.id
                JOIN admin_users ON approval_history.admin_id = admin_users.id
                WHERE approval_history.approval_record_id = %s
                ORDER BY approval_history.created_at ASC
            """, (approval_record_id,))
            history = cursor.fetchall()

            return {
                "success": True,
                "detail": detail,
                "current_task": current_task,
                "history": history
            }

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cursor.close()
        connection.close()

@app.get("/api/admin/{admin_id}/completed-tasks")
def get_completed_tasks(admin_id: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        sql = """
        SELECT
            approval_tasks.id AS task_id,
            approval_records.id AS approval_record_id,
            approval_tasks.status,
            approval_tasks.comment,
            approval_tasks.approved_at,
            approval_tasks.created_at,
            users.name, users.phone, users.company,
            users.identity_type, users.visit_purpose,
            exam_records.score, approval_steps.step_name
        FROM approval_tasks
        JOIN approval_records ON approval_tasks.approval_record_id = approval_records.id
        JOIN users ON approval_records.user_id = users.id
        JOIN exam_records ON approval_records.exam_record_id = exam_records.id
        JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
        WHERE approval_tasks.admin_id = %s
        AND approval_tasks.status IN ('approved', 'rejected')
        ORDER BY approval_tasks.approved_at DESC
        """
        cursor.execute(sql, (admin_id,))
        tasks = cursor.fetchall()
        return {"success": True, "tasks": tasks}
    finally:
        cursor.close()
        connection.close()


# =========================
# 修改：查询完整工单详情（彻底删除数字映射，直接使用字符串）
# =========================
@app.get("/api/approval-detail/{approval_record_id}")
def get_approval_detail(approval_record_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. 获取基本信息（人员 + 考试 + 审批状态）
            cursor.execute("""
                SELECT
                    users.name, users.phone, users.company, users.identity_type, users.visit_purpose,
                    exam_records.score, exam_records.submitted_at AS exam_submitted_at,
                    approval_records.status AS approval_status,  # 直接取 ENUM 字符串
                    approval_records.created_at AS application_time
                FROM approval_records
                JOIN users ON approval_records.user_id = users.id
                JOIN exam_records ON approval_records.exam_record_id = exam_records.id
                WHERE approval_records.id = %s
            """, (approval_record_id,))
            detail = cursor.fetchone()
            if not detail:
                return {"success": False, "message": "审批记录不存在"}

            # 2. 核心逻辑：只要下面还有 pending 任务，状态强制为 pending
            cursor.execute("""
                SELECT id FROM approval_tasks
                WHERE approval_record_id = %s AND status = 'pending'
                LIMIT 1
            """, (approval_record_id,))
            pending_task = cursor.fetchone()

            # 如果存在待办，则强制为 pending；否则，直接用数据库的 ENUM 字符串
            if pending_task:
                detail["approval_status"] = "pending"
            else:
                detail["approval_status"] = detail["approval_status"]  # 直接使用原值（approved/rejected）

            # 3. 查询当前待办任务（若流程未完成）
            cursor.execute("""
                SELECT approval_tasks.id AS task_id, approval_steps.step_name AS current_step_name
                FROM approval_tasks
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                WHERE approval_tasks.approval_record_id = %s
                AND approval_tasks.status = 'pending'
                LIMIT 1
            """, (approval_record_id,))
            current_task = cursor.fetchone()

            # 4. 获取完整审批历史
            cursor.execute("""
                SELECT
                    approval_history.action, approval_history.comment, approval_history.created_at,
                    approval_steps.step_name, approval_steps.step_order,
                    admin_users.real_name AS approver_name, admin_users.role
                FROM approval_history
                JOIN approval_steps ON approval_history.step_id = approval_steps.id
                JOIN admin_users ON approval_history.admin_id = admin_users.id
                WHERE approval_history.approval_record_id = %s
                ORDER BY approval_history.created_at ASC
            """, (approval_record_id,))
            history = cursor.fetchall()

            return {
                "success": True,
                "detail": detail,
                "current_task": current_task,
                "history": history
            }

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        cursor.close()
        connection.close()