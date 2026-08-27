from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import (
    AuthError,
    build_permission_info,
    create_access_token,
    create_business_token,
    get_admin_row,
    get_current_admin,
    get_current_business_member,
    is_top_admin,
)
from config.database import get_connection

app = FastAPI(
    title="数据中心机房准入系统",
    description="用于处理工单、人员登记、考试和审批",
    version="0.3.0",
)

# 允许管理台前端跨域直连（开发环境放开所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    """鉴权异常统一转成 {code, msg}（HTTP 200），与前端 axios 约定一致。"""
    return JSONResponse(status_code=200, content={"code": exc.code, "data": None, "msg": exc.msg})


# =========================
# 响应工具
# =========================

def ok(data=None, msg="操作成功"):
    """管理端统一返回 {code, data, msg}（与前端 axios 约定一致）。"""
    return {"code": 0, "data": data, "msg": msg}


def fail(msg="操作失败", code=1):
    return {"code": code, "data": None, "msg": msg}


# =========================
# 请求数据模型
# =========================

class VisitorRegister(BaseModel):
    name: str
    phone: str
    password: str
    company: str


class VisitorLogin(BaseModel):
    phone: str
    password: str


class ExamSubmit(BaseModel):
    user_id: int
    answers: dict


class BusinessRegister(BaseModel):
    username: str
    password: str
    real_name: str = ""
    phone: str = ""


class BusinessLogin(BaseModel):
    username: str
    password: str


class BusinessMemberUpdate(BaseModel):
    real_name: str = ""
    phone: str = ""
    password: str = ""


class WorkOrderCreate(BaseModel):
    company: str
    visit_time: str = ""
    visit_scale: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    lead_person: str = ""


class ApprovalAction(BaseModel):
    action: str
    comment: str = ""


class AdminLogin(BaseModel):
    username: str
    password: str


class WorkflowNodePosition(BaseModel):
    node_x: int
    node_y: int


class WorkflowNodeUpdate(BaseModel):
    id: int
    node_x: int
    node_y: int


class WorkflowNodeBatchUpdate(BaseModel):
    nodes: list[WorkflowNodeUpdate]


class TransitionCreate(BaseModel):
    from_step_id: int
    to_step_id: int


# =========================
# 工具函数
# =========================

def find_admin_by_role(cursor, role: str):
    """负载均衡：选择该角色下待办最少的管理员（平局按 id）。"""
    cursor.execute(
        """
        SELECT id
        FROM admin_users
        WHERE role = %s
        ORDER BY (
            SELECT COUNT(*)
            FROM approval_tasks t
            WHERE t.admin_id = admin_users.id AND t.status = 'pending'
        ) ASC, id ASC
        LIMIT 1
        """,
        (role,),
    )
    return cursor.fetchone()


def start_approval(cursor, work_order_id: int):
    """为工单启动 BPM 审批：找开始节点 → 分配第一个审批任务。返回错误信息或 None。"""
    cursor.execute("SELECT id, step_name, required_role FROM approval_steps ORDER BY id")
    all_steps = cursor.fetchall()
    if not all_steps:
        return "当前没有配置审批节点"

    cursor.execute("SELECT from_step_id, to_step_id FROM workflow_transitions")
    transitions = cursor.fetchall()
    if not transitions:
        return "当前 BPM 工作流没有配置节点连线"

    all_step_ids = {s["id"] for s in all_steps}
    to_step_ids = {t["to_step_id"] for t in transitions}
    start_step_ids = list(all_step_ids - to_step_ids)
    if len(start_step_ids) != 1:
        return f"当前 BPM 工作流必须只有一个开始节点，当前检测到 {len(start_step_ids)} 个"

    start_step_id = start_step_ids[0]
    cursor.execute(
        "SELECT id, step_name, required_role FROM approval_steps WHERE id = %s",
        (start_step_id,),
    )
    first_step = cursor.fetchone()
    if not first_step:
        return "无法找到 BPM 开始节点"

    first_admin = find_admin_by_role(cursor, first_step["required_role"])
    if not first_admin:
        return f"找不到角色 {first_step['required_role']} 对应的审批管理员"

    cursor.execute(
        "INSERT INTO approval_records (work_order_id, status) VALUES (%s, 'pending')",
        (work_order_id,),
    )
    approval_record_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO approval_tasks (approval_record_id, step_id, admin_id, status) "
        "VALUES (%s, %s, %s, 'pending')",
        (approval_record_id, first_step["id"], first_admin["id"]),
    )
    return None


# =========================
# 访客端接口（保持 {success} 结构，供小程序调用）
# =========================

@app.get("/")
def root():
    return {"message": "数据中心机房准入系统后端运行成功"}


@app.get("/api/test")
def test():
    return {"success": True, "message": "后端 API 测试成功"}


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


@app.post("/api/visitor/register")
def visitor_register(data: VisitorRegister):
    """访客登记：按公司名匹配已审批通过的工单，命中则绑定。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM work_orders WHERE company = %s AND status = 'approved' "
                "ORDER BY id DESC LIMIT 1",
                (data.company,),
            )
            wo = cursor.fetchone()
            if not wo:
                return {"success": False, "message": "未找到匹配的已审批工单，请联系业务部先提交工单"}

            cursor.execute(
                "INSERT INTO users (name, phone, password, company, identity_type, visit_purpose, work_order_id) "
                "VALUES (%s, %s, %s, %s, '', '', %s)",
                (data.name, data.phone, data.password, data.company, wo["id"]),
            )
            connection.commit()
            user_id = cursor.lastrowid
        return {"success": True, "user_id": user_id, "work_order_id": wo["id"]}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.get("/api/questions")
def get_questions():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, question, option_a, option_b, option_c, option_d, score
                FROM questions
                WHERE is_active = TRUE
                ORDER BY id
                """
            )
            questions = cursor.fetchall()
        return {"success": True, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()


@app.post("/api/submit-exam")
def submit_exam(data: ExamSubmit):
    """访客考试：判分；通过且已绑定工单时生成准入凭证。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            # 1. 查询考试题目
            cursor.execute("SELECT id, correct_answer FROM questions")
            questions = cursor.fetchall()

            # 2. 计算考试成绩（每题 10 分）
            answer_map = {0: "A", 1: "B", 2: "C", 3: "D"}
            score = 0
            for question in questions:
                qid = question["id"]
                idx = data.answers.get(str(qid))
                if idx is not None and answer_map.get(idx) == question["correct_answer"]:
                    score += 10

            passed = score >= 70

            # 3. 保存考试记录
            cursor.execute(
                "INSERT INTO exam_records (user_id, score, passed) VALUES (%s, %s, %s)",
                (data.user_id, score, passed),
            )
            exam_id = cursor.lastrowid

            # 4. 通过且绑定工单 → 生成准入凭证
            credential = None
            if passed:
                cursor.execute(
                    "SELECT work_order_id FROM users WHERE id = %s",
                    (data.user_id,),
                )
                user_row = cursor.fetchone()
                work_order_id = user_row.get("work_order_id") if user_row else None
                if work_order_id:
                    cursor.execute(
                        "INSERT INTO credentials (user_id, work_order_id, exam_record_id) "
                        "VALUES (%s, %s, %s)",
                        (data.user_id, work_order_id, exam_id),
                    )
                    credential = {"work_order_id": work_order_id, "exam_record_id": exam_id}

            connection.commit()

            if credential:
                message = "考试通过，已生成准入凭证"
            elif passed:
                message = "考试通过"
            else:
                message = "考试未通过"

            return {
                "success": True,
                "score": score,
                "passed": passed,
                "credential": credential,
                "message": message,
            }
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.get("/api/credential/{user_id}")
def get_credential(user_id: int):
    """访客的准入凭证状态。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.created_at AS issued_at,
                       u.name, u.phone, u.company,
                       w.company AS work_order_company, w.visit_time, w.lead_person,
                       e.score
                FROM credentials c
                JOIN users u ON c.user_id = u.id
                JOIN work_orders w ON c.work_order_id = w.id
                JOIN exam_records e ON c.exam_record_id = e.id
                WHERE c.user_id = %s
                ORDER BY c.id DESC LIMIT 1
                """,
                (user_id,),
            )
            credential = cursor.fetchone()
        if not credential:
            return {"success": False, "message": "暂无准入凭证"}
        return {"success": True, "credential": credential}
    finally:
        connection.close()


@app.post("/api/visitor/login")
def visitor_login(data: VisitorLogin):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, phone, company, password, work_order_id FROM users WHERE phone = %s",
                (data.phone,),
            )
            user = cursor.fetchone()
        if not user:
            return {"success": False, "message": "手机号未注册"}
        if user["password"] != data.password:
            return {"success": False, "message": "密码错误"}
        return {
            "success": True,
            "user_id": user["id"],
            "user": {
                "id": user["id"],
                "name": user["name"],
                "phone": user["phone"],
                "company": user["company"],
                "work_order_id": user["work_order_id"],
            },
        }
    finally:
        connection.close()


@app.get("/api/visitor/info/{user_id}")
def visitor_info(user_id: int):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT u.id, u.name, u.phone, u.company, u.work_order_id, "
                "w.company AS work_order_company, w.visit_time, w.lead_person, w.status AS work_order_status "
                "FROM users u LEFT JOIN work_orders w ON u.work_order_id = w.id WHERE u.id = %s",
                (user_id,),
            )
            info = cursor.fetchone()
        if not info:
            return {"success": False, "message": "用户不存在"}
        return {"success": True, "info": info}
    finally:
        connection.close()


@app.get("/api/visitor/exams/{user_id}")
def visitor_exams(user_id: int):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, score, passed FROM exam_records WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            exams = cursor.fetchall()
        return {"success": True, "list": exams}
    finally:
        connection.close()


@app.get("/api/visitor/credentials/{user_id}")
def visitor_credentials(user_id: int):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.id, c.created_at AS issued_at, w.company, w.visit_time, w.lead_person, e.score "
                "FROM credentials c JOIN work_orders w ON c.work_order_id = w.id "
                "JOIN exam_records e ON c.exam_record_id = e.id "
                "WHERE c.user_id = %s ORDER BY c.id DESC",
                (user_id,),
            )
            credentials = cursor.fetchall()
        return {"success": True, "list": credentials}
    finally:
        connection.close()


# =========================
# 业务部成员接口（小程序）
# =========================

@app.post("/api/business/register")
def business_register(data: BusinessRegister):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM business_members WHERE username = %s", (data.username,))
            if cursor.fetchone():
                return {"success": False, "message": "账号已存在"}
            cursor.execute(
                "INSERT INTO business_members (username, password, real_name, phone) "
                "VALUES (%s, %s, %s, %s)",
                (data.username, data.password, data.real_name, data.phone),
            )
            connection.commit()
        return {"success": True, "message": "注册成功"}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.post("/api/business/login")
def business_login(data: BusinessLogin):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password, real_name, phone FROM business_members WHERE username = %s",
                (data.username,),
            )
            member = cursor.fetchone()
        if not member:
            return {"success": False, "message": "账号不存在"}
        if member["password"] != data.password:
            return {"success": False, "message": "密码错误"}
        token = create_business_token(member["id"], member["username"])
        return {
            "success": True,
            "token": token,
            "member": {
                "id": member["id"],
                "username": member["username"],
                "real_name": member["real_name"],
                "phone": member["phone"],
            },
        }
    finally:
        connection.close()


# =========================
# 工单接口（业务部成员提交）
# =========================

@app.post("/api/work-orders")
def create_work_order(data: WorkOrderCreate, member: dict = Depends(get_current_business_member)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO work_orders
                (business_member_id, company, visit_time, visit_scale, contact_name, contact_phone, lead_person, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                """,
                (member["id"], data.company, data.visit_time, data.visit_scale,
                 data.contact_name, data.contact_phone, data.lead_person),
            )
            work_order_id = cursor.lastrowid

            err = start_approval(cursor, work_order_id)
            if err:
                connection.rollback()
                return {"success": False, "message": err}

            connection.commit()
        return {"success": True, "work_order_id": work_order_id, "message": "工单已提交，进入审批流程"}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.get("/api/work-orders/mine")
def get_my_work_orders(member: dict = Depends(get_current_business_member)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, company, visit_time, visit_scale, contact_name, contact_phone,
                       lead_person, status, created_at
                FROM work_orders
                WHERE business_member_id = %s
                ORDER BY id DESC
                """,
                (member["id"],),
            )
            rows = cursor.fetchall()
        return {"success": True, "list": rows}
    finally:
        connection.close()


# =========================
# 管理端鉴权接口
# =========================

@app.post("/api/auth/login")
def admin_login(data: AdminLogin):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password, real_name, phone, role, parent_admin_id "
                "FROM admin_users WHERE username = %s",
                (data.username,),
            )
            admin = cursor.fetchone()
        if not admin:
            return fail("管理员账号不存在")
        if admin["password"] != data.password:
            return fail("密码错误")
        token = create_access_token(admin["id"], admin["username"], admin["role"])
        return ok(
            {
                "accessToken": token,
                "refreshToken": token,
                "expiresTime": 86400,
            },
            "登录成功",
        )
    finally:
        connection.close()


@app.get("/api/auth/get-permission-info")
def get_permission_info(current_admin: dict = Depends(get_current_admin)):
    return ok(build_permission_info(current_admin))


@app.post("/api/auth/logout")
def logout(current_admin: dict = Depends(get_current_admin)):
    return ok(True, "退出成功")


# =========================
# 布局兼容接口（站内信铃铛/个人中心等，管理台布局自动调用）
# =========================

@app.get("/system/notify-message/get-unread-count")
def get_unread_count(current_admin: dict = Depends(get_current_admin)):
    return ok(0)


@app.get("/system/notify-message/get-unread-list")
def get_unread_list(current_admin: dict = Depends(get_current_admin)):
    return ok([])


@app.get("/system/user/profile/get")
def get_user_profile(current_admin: dict = Depends(get_current_admin)):
    row = get_admin_row(current_admin["id"])
    if not row:
        return fail("管理员不存在", code=404)
    profile = {
        "id": row["id"],
        "username": row["username"],
        "nickname": row.get("real_name") or row["username"],
        "dept": {"id": 0, "name": row.get("role") or ""},
        "roles": [{"id": 0, "name": row.get("role") or ""}],
        "posts": [],
        "email": "",
        "mobile": row.get("phone") or "",
        "sex": 0,
        "avatar": "",
        "status": 0,
        "remark": "",
        "loginIp": "",
        "loginDate": None,
        "createTime": None,
    }
    return ok(profile)


@app.get("/system/social-user/get-bind-list")
def get_bind_social_user_list(current_admin: dict = Depends(get_current_admin)):
    return ok([])


# =========================
# 管理端：待办 / 已办
# =========================

@app.get("/api/tasks/pending")
def get_pending_tasks(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    approval_tasks.id AS task_id,
                    approval_records.id AS approval_record_id,
                    approval_tasks.status,
                    approval_tasks.created_at,
                    work_orders.company, work_orders.visit_time, work_orders.visit_scale,
                    work_orders.contact_name, work_orders.contact_phone, work_orders.lead_person,
                    approval_steps.step_name
                FROM approval_tasks
                JOIN approval_records ON approval_tasks.approval_record_id = approval_records.id
                JOIN work_orders ON approval_records.work_order_id = work_orders.id
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                WHERE approval_tasks.admin_id = %s AND approval_tasks.status = 'pending'
                ORDER BY approval_tasks.created_at ASC
                """,
                (current_admin["id"],),
            )
            tasks = cursor.fetchall()
        return ok({"list": tasks, "total": len(tasks)})
    finally:
        connection.close()


@app.get("/api/tasks/completed")
def get_completed_tasks(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    approval_tasks.id AS task_id,
                    approval_records.id AS approval_record_id,
                    approval_tasks.status,
                    approval_tasks.comment,
                    approval_tasks.approved_at,
                    approval_tasks.created_at,
                    work_orders.company, work_orders.visit_time, work_orders.visit_scale,
                    work_orders.contact_name, work_orders.contact_phone, work_orders.lead_person,
                    approval_steps.step_name
                FROM approval_tasks
                JOIN approval_records ON approval_tasks.approval_record_id = approval_records.id
                JOIN work_orders ON approval_records.work_order_id = work_orders.id
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                WHERE approval_tasks.admin_id = %s
                AND approval_tasks.status IN ('approved', 'rejected')
                ORDER BY approval_tasks.approved_at DESC
                """,
                (current_admin["id"],),
            )
            tasks = cursor.fetchall()
        return ok({"list": tasks, "total": len(tasks)})
    finally:
        connection.close()


# =========================
# 管理端：审批动作（BPM 核心）
# =========================

@app.post("/api/approval-task/{task_id}/action")
def handle_approval(
    task_id: int,
    data: ApprovalAction,
    current_admin: dict = Depends(get_current_admin),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            # 1. 查询当前审批任务
            cursor.execute(
                "SELECT id, approval_record_id, step_id, admin_id, status "
                "FROM approval_tasks WHERE id = %s",
                (task_id,),
            )
            task = cursor.fetchone()
            if not task:
                return fail("审批任务不存在")

            # 2. 权限检查
            if task["admin_id"] != current_admin["id"]:
                return fail("无权审批该任务", code=403)

            # 3. 防止重复审批
            if task["status"] != "pending":
                return fail("该任务已经处理")

            # 4. 检查审批操作
            if data.action not in ["approved", "rejected"]:
                return fail("审批操作错误")

            # 5. 拒绝必须填写意见
            if data.action == "rejected" and (not data.comment or not data.comment.strip()):
                return fail("拒绝审批时必须填写拒绝原因")

            # 6. 更新当前审批任务
            cursor.execute(
                "UPDATE approval_tasks SET status = %s, comment = %s, approved_at = NOW() WHERE id = %s",
                (data.action, data.comment, task_id),
            )

            # 7. 写入审批历史
            cursor.execute(
                """
                INSERT INTO approval_history
                (approval_record_id, task_id, step_id, admin_id, action, comment)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (task["approval_record_id"], task_id, task["step_id"],
                 current_admin["id"], data.action, data.comment),
            )

            # 8. 如果拒绝，整个流程结束
            if data.action == "rejected":
                cursor.execute(
                    "UPDATE approval_records SET status = 'rejected' WHERE id = %s",
                    (task["approval_record_id"],),
                )
                cursor.execute(
                    "UPDATE work_orders SET status = 'rejected' "
                    "WHERE id = (SELECT work_order_id FROM approval_records WHERE id = %s)",
                    (task["approval_record_id"],),
                )
                connection.commit()
                return ok({"status": "rejected"}, "审批已拒绝，流程结束")

            # 9. 根据 workflow_transitions 查询下一节点
            cursor.execute(
                "SELECT to_step_id FROM workflow_transitions WHERE from_step_id = %s",
                (task["step_id"],),
            )
            next_transitions = cursor.fetchall()

            # 当前节点没有下一节点 → 流程完成
            if len(next_transitions) == 0:
                cursor.execute(
                    "UPDATE approval_records SET status = 'approved' WHERE id = %s",
                    (task["approval_record_id"],),
                )
                cursor.execute(
                    "UPDATE work_orders SET status = 'approved' "
                    "WHERE id = (SELECT work_order_id FROM approval_records WHERE id = %s)",
                    (task["approval_record_id"],),
                )
                connection.commit()
                return ok({"status": "approved"}, "审批全部完成，流程结束")

            if len(next_transitions) > 1:
                connection.rollback()
                return fail("当前 BPM 节点配置了多个下一节点，当前版本暂不支持并行或条件分支审批")

            next_step_id = next_transitions[0]["to_step_id"]
            cursor.execute(
                "SELECT id, step_name, required_role FROM approval_steps WHERE id = %s",
                (next_step_id,),
            )
            next_step = cursor.fetchone()
            if not next_step:
                connection.rollback()
                return fail("下一审批节点不存在")

            next_admin = find_admin_by_role(cursor, next_step["required_role"])
            if not next_admin:
                connection.rollback()
                return fail(f"找不到角色 {next_step['required_role']} 对应的审批管理员")

            cursor.execute(
                """
                SELECT id FROM approval_tasks
                WHERE approval_record_id = %s AND step_id = %s AND status = 'pending'
                LIMIT 1
                """,
                (task["approval_record_id"], next_step_id),
            )
            if cursor.fetchone():
                connection.rollback()
                return fail("下一审批任务已经存在")

            cursor.execute(
                """
                INSERT INTO approval_tasks (approval_record_id, step_id, admin_id, status)
                VALUES (%s, %s, %s, 'pending')
                """,
                (task["approval_record_id"], next_step_id, next_admin["id"]),
            )

            cursor.execute(
                "UPDATE approval_records SET status = 'pending' WHERE id = %s",
                (task["approval_record_id"],),
            )

            connection.commit()

            return ok(
                {
                    "status": "pending",
                    "next_admin_id": next_admin["id"],
                    "next_step_id": next_step["id"],
                    "next_step_name": next_step["step_name"],
                },
                "当前审批已通过，已提交至下一审批节点",
            )
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


# =========================
# 管理端：工单列表 / 详情 / 流程图
# =========================

@app.get("/api/work-orders")
def get_work_orders(
    status: str | None = Query(default=None),
    company: str | None = Query(default=None),
    current_admin: dict = Depends(get_current_admin),
):
    """工单列表（全部工单）。仅顶层管理员可见。"""
    if not is_top_admin(current_admin["id"]):
        return fail("无权查看全部工单", code=403)

    connection = get_connection()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("work_orders.status = %s")
            params.append(status)
        if company:
            conditions.append("work_orders.company LIKE %s")
            params.append(f"%{company}%")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    work_orders.id AS work_order_id,
                    approval_records.id AS approval_record_id,
                    work_orders.company, work_orders.visit_time, work_orders.visit_scale,
                    work_orders.contact_name, work_orders.contact_phone, work_orders.lead_person,
                    work_orders.status AS approval_status,
                    work_orders.created_at AS application_time,
                    (SELECT s.step_name FROM approval_tasks t
                     JOIN approval_steps s ON t.step_id = s.id
                     WHERE t.approval_record_id = approval_records.id AND t.status = 'pending'
                     LIMIT 1) AS current_step_name
                FROM work_orders
                LEFT JOIN approval_records ON approval_records.work_order_id = work_orders.id
                {where}
                ORDER BY work_orders.created_at DESC
                """,
                params,
            )
            rows = cursor.fetchall()
        return ok({"list": rows, "total": len(rows)})
    finally:
        connection.close()


@app.get("/api/approval-detail/{record_id}")
def get_approval_detail(record_id: int, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            # 1. 基本信息（工单 + 审批状态）
            cursor.execute(
                """
                SELECT
                    work_orders.company, work_orders.visit_time, work_orders.visit_scale,
                    work_orders.contact_name, work_orders.contact_phone, work_orders.lead_person,
                    approval_records.status AS approval_status,
                    approval_records.created_at AS application_time
                FROM approval_records
                JOIN work_orders ON approval_records.work_order_id = work_orders.id
                WHERE approval_records.id = %s
                """,
                (record_id,),
            )
            detail = cursor.fetchone()
            if not detail:
                return fail("审批记录不存在")

            # 2. 只要还有 pending 任务，状态强制为 pending
            cursor.execute(
                "SELECT id FROM approval_tasks WHERE approval_record_id = %s AND status = 'pending' LIMIT 1",
                (record_id,),
            )
            if cursor.fetchone():
                detail["approval_status"] = "pending"

            # 3. 当前待办任务
            cursor.execute(
                """
                SELECT approval_tasks.id AS task_id,
                       approval_steps.step_name AS current_step_name,
                       admin_users.real_name AS approver_name
                FROM approval_tasks
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                JOIN admin_users ON approval_tasks.admin_id = admin_users.id
                WHERE approval_tasks.approval_record_id = %s AND approval_tasks.status = 'pending'
                LIMIT 1
                """,
                (record_id,),
            )
            current_task = cursor.fetchone()

            # 4. 完整审批历史
            cursor.execute(
                """
                SELECT
                    approval_history.action, approval_history.comment, approval_history.created_at,
                    approval_steps.step_name, approval_steps.step_order,
                    admin_users.real_name AS approver_name, admin_users.role
                FROM approval_history
                JOIN approval_steps ON approval_history.step_id = approval_steps.id
                JOIN admin_users ON approval_history.admin_id = admin_users.id
                WHERE approval_history.approval_record_id = %s
                ORDER BY approval_history.created_at ASC
                """,
                (record_id,),
            )
            history = cursor.fetchall()

            return ok({"detail": detail, "current_task": current_task, "history": history})
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.get("/api/work-orders/{record_id}/flow")
def get_work_order_flow(record_id: int, current_admin: dict = Depends(get_current_admin)):
    """审批流程图数据：节点、连线、当前节点、已完成节点。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, step_name, step_order, required_role, node_x, node_y "
                "FROM approval_steps ORDER BY step_order ASC"
            )
            nodes = cursor.fetchall()

            cursor.execute(
                "SELECT id, from_step_id, to_step_id FROM workflow_transitions ORDER BY id ASC"
            )
            transitions = cursor.fetchall()

            cursor.execute(
                "SELECT DISTINCT step_id FROM approval_history WHERE approval_record_id = %s",
                (record_id,),
            )
            completed_step_ids = {row["step_id"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT step_id FROM approval_tasks WHERE approval_record_id = %s AND status = 'pending' LIMIT 1",
                (record_id,),
            )
            current = cursor.fetchone()
            current_step_id = current["step_id"] if current else None

        for node in nodes:
            sid = node["id"]
            if sid == current_step_id:
                node["flow_status"] = "current"
            elif sid in completed_step_ids:
                node["flow_status"] = "completed"
            else:
                node["flow_status"] = "pending"

        return ok({"nodes": nodes, "transitions": transitions, "current_step_id": current_step_id})
    finally:
        connection.close()


# =========================
# 管理端：业务部成员管理
# =========================

@app.get("/api/business-members")
def list_business_members(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, real_name, phone, created_at FROM business_members ORDER BY id ASC"
            )
            rows = cursor.fetchall()
        return ok({"list": rows, "total": len(rows)})
    finally:
        connection.close()


@app.post("/api/business-members")
def create_business_member(data: BusinessRegister, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM business_members WHERE username = %s", (data.username,))
            if cursor.fetchone():
                return fail("账号已存在")
            cursor.execute(
                "INSERT INTO business_members (username, password, real_name, phone) VALUES (%s, %s, %s, %s)",
                (data.username, data.password, data.real_name, data.phone),
            )
            connection.commit()
            return ok({"id": cursor.lastrowid}, "创建成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.put("/api/business-members/{member_id}")
def update_business_member(member_id: int, data: BusinessMemberUpdate, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if data.password:
                cursor.execute(
                    "UPDATE business_members SET real_name = %s, phone = %s, password = %s WHERE id = %s",
                    (data.real_name, data.phone, data.password, member_id),
                )
            else:
                cursor.execute(
                    "UPDATE business_members SET real_name = %s, phone = %s WHERE id = %s",
                    (data.real_name, data.phone, member_id),
                )
            connection.commit()
        return ok(None, "更新成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.delete("/api/business-members/{member_id}")
def delete_business_member(member_id: int, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM business_members WHERE id = %s", (member_id,))
            connection.commit()
        return ok(None, "删除成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


# =========================
# 管理端：BPM 工作流配置
# =========================

@app.get("/api/workflow/nodes")
def get_workflow_nodes(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, step_name, step_order, required_role, node_x, node_y "
                "FROM approval_steps ORDER BY step_order ASC"
            )
            nodes = cursor.fetchall()
        return ok({"list": nodes})
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.put("/api/workflow/nodes/{node_id}/position")
def update_workflow_node_position(node_id: int, data: WorkflowNodePosition, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE approval_steps SET node_x = %s, node_y = %s WHERE id = %s",
                (data.node_x, data.node_y, node_id),
            )
            if cursor.rowcount == 0:
                return fail("审批节点不存在")
        connection.commit()
        return ok({"node_id": node_id}, "节点位置更新成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.put("/api/workflow/nodes/positions")
def update_workflow_node_positions(data: WorkflowNodeBatchUpdate, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for node in data.nodes:
                cursor.execute(
                    "UPDATE approval_steps SET node_x = %s, node_y = %s WHERE id = %s",
                    (node.node_x, node.node_y, node.id),
                )
        connection.commit()
        return ok(None, "所有节点位置保存成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.get("/api/workflow/transitions")
def get_workflow_transitions(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    workflow_transitions.id,
                    workflow_transitions.from_step_id,
                    workflow_transitions.to_step_id,
                    approval_steps.step_name AS from_step_name,
                    next_step.step_name AS to_step_name
                FROM workflow_transitions
                JOIN approval_steps ON workflow_transitions.from_step_id = approval_steps.id
                JOIN approval_steps AS next_step ON workflow_transitions.to_step_id = next_step.id
                ORDER BY workflow_transitions.id ASC
                """
            )
            transitions = cursor.fetchall()
        return ok({"list": transitions})
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.post("/api/workflow/transitions")
def create_transition(data: TransitionCreate, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        if data.from_step_id == data.to_step_id:
            return fail("不能连接到自身节点")

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM approval_steps WHERE id = %s", (data.from_step_id,))
            if not cursor.fetchone():
                return fail("起始节点不存在")
            cursor.execute("SELECT id FROM approval_steps WHERE id = %s", (data.to_step_id,))
            if not cursor.fetchone():
                return fail("目标节点不存在")
            cursor.execute(
                "SELECT id FROM workflow_transitions WHERE from_step_id = %s AND to_step_id = %s",
                (data.from_step_id, data.to_step_id),
            )
            if cursor.fetchone():
                return fail("该连线已经存在")
            cursor.execute(
                "SELECT id FROM workflow_transitions WHERE from_step_id = %s LIMIT 1",
                (data.from_step_id,),
            )
            if cursor.fetchone():
                return fail("该节点已经配置下一节点，请先删除旧连线")
            cursor.execute(
                "SELECT id FROM workflow_transitions WHERE from_step_id = %s AND to_step_id = %s LIMIT 1",
                (data.to_step_id, data.from_step_id),
            )
            if cursor.fetchone():
                return fail("不能形成循环审批流程")
            cursor.execute(
                "INSERT INTO workflow_transitions (from_step_id, to_step_id) VALUES (%s, %s)",
                (data.from_step_id, data.to_step_id),
            )
            transition_id = cursor.lastrowid

        connection.commit()
        return ok({"transition_id": transition_id}, "BPM 连线创建成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.delete("/api/workflow/transitions/{transition_id}")
def delete_transition(transition_id: int, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM workflow_transitions WHERE id = %s", (transition_id,))
            if cursor.rowcount == 0:
                return fail("连线不存在")
        connection.commit()
        return ok(None, "连线删除成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.delete("/api/workflow/transitions")
def clear_transitions(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM workflow_transitions")
        connection.commit()
        return ok(None, "连线已全部重置")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()
