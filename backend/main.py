import json

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
    company: str = ""
    id_card: str = ""


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
    visitors: list = []
    entry_time: str = ""
    exit_time: str = ""
    reason: str = ""
    area: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    accompanying_person: str = ""
    is_draft: bool = False
    custom_fields: dict = {}


class ReservationCreate(BaseModel):
    visitor_id: int
    company: str
    visitors: list = []
    entry_time: str = ""
    exit_time: str = ""
    reason: str = ""
    area: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    accompanying_person: str = ""


class QuestionCreate(BaseModel):
    question: str
    option_a: str = ""
    option_b: str = ""
    option_c: str = ""
    option_d: str = ""
    score: int = 10
    correct_answer: str = "A"
    is_active: bool = True


class WorkOrderFieldItem(BaseModel):
    """工单结构中的一个字段条目。"""
    field_key: str = ""          # 默认字段=固定列名；自定义字段=custom_{id}
    field_name: str              # 显示名
    input_type: str = "text"     # text/textarea/select/date/time/datetime/visitors
    options: list = []           # select 的选项
    required: bool = False
    sort_order: int = 0


class WorkOrderFieldsSave(BaseModel):
    """批量保存整个工单结构。"""
    fields: list[WorkOrderFieldItem]


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


def build_display_fields(cursor, wo: dict):
    """按工单字段定义，把工单值组装成有序的 display_fields（前端直接遍历展示）。

    wo 需要含固定列 + custom_fields(已解析为 dict)。visitors 列已解析为 list。
    """
    cursor.execute(
        "SELECT field_key, field_name, input_type, options FROM work_order_fields ORDER BY sort_order ASC, id ASC"
    )
    fields = cursor.fetchall()

    fixed_keys = {"company", "visitors", "entry_time", "exit_time", "reason", "area",
                  "contact_name", "contact_phone", "accompanying_person"}
    custom = wo.get("custom_fields") or {}

    result = []
    for f in fields:
        key = f["field_key"]
        if key in fixed_keys:
            value = wo.get(key, "")
        else:
            value = custom.get(key, "")
        result.append({
            "field_key": key,
            "field_name": f["field_name"],
            "input_type": f["input_type"],
            "value": value,
        })
    return result


def build_credential_display(cursor, cred: dict):
    """根据凭证关联的工单或预约，按字段定义组装 display_fields（跟随工单结构更新）。"""
    work_order_id = cred.get("work_order_id")
    reservation_id = cred.get("reservation_id")
    if work_order_id:
        cursor.execute("SELECT * FROM work_orders WHERE id = %s", (work_order_id,))
        wo = cursor.fetchone()
        if wo:
            wo["visitors"] = json.loads(wo["visitors"]) if wo.get("visitors") else []
            wo["custom_fields"] = json.loads(wo["custom_fields"]) if wo.get("custom_fields") else {}
            return build_display_fields(cursor, wo)
    if reservation_id:
        cursor.execute("SELECT * FROM reservations WHERE id = %s", (reservation_id,))
        rv = cursor.fetchone()
        if rv:
            rv["visitors"] = json.loads(rv["visitors"]) if rv.get("visitors") else []
            rv["custom_fields"] = {}
            return build_display_fields(cursor, rv)
    return []


def sync_biz_status(cursor, approval_record_id: int, status: str):
    """根据审批记录回写工单或预约的状态。"""
    cursor.execute(
        "SELECT work_order_id, reservation_id FROM approval_records WHERE id = %s",
        (approval_record_id,),
    )
    ar = cursor.fetchone()
    if not ar:
        return
    if ar.get("work_order_id"):
        cursor.execute("UPDATE work_orders SET status = %s WHERE id = %s", (status, ar["work_order_id"]))
    elif ar.get("reservation_id"):
        cursor.execute("UPDATE reservations SET status = %s WHERE id = %s", (status, ar["reservation_id"]))


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
    """访客注册：任意访客都可注册，无需匹配工单。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE phone = %s", (data.phone,))
            if cursor.fetchone():
                return {"success": False, "message": "该手机号已注册"}
            cursor.execute(
                "INSERT INTO users (name, phone, password, company, id_card, identity_type, visit_purpose) "
                "VALUES (%s, %s, %s, %s, %s, '', '')",
                (data.name, data.phone, data.password, data.company, data.id_card),
            )
            connection.commit()
            user_id = cursor.lastrowid
        return {"success": True, "user_id": user_id}
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

            # 4. 通过且（有已通过工单 或 已通过预约）→ 生成准入凭证
            credential = None
            if passed:
                cursor.execute("SELECT id_card FROM users WHERE id = %s", (data.user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    id_card = user_row["id_card"] or ""
                    # 按身份证号匹配审批通过的工单（来访人员 JSON 中含该身份证号）
                    wo = None
                    if id_card:
                        cursor.execute(
                            "SELECT id FROM work_orders WHERE status = 'approved' "
                            "AND visitors LIKE %s ORDER BY id DESC LIMIT 1",
                            (f"%{id_card}%",),
                        )
                        wo = cursor.fetchone()
                    cursor.execute(
                        "SELECT id FROM reservations WHERE visitor_id = %s AND status = 'approved' "
                        "ORDER BY id DESC LIMIT 1",
                        (data.user_id,),
                    )
                    rv = cursor.fetchone()
                    work_order_id = wo["id"] if wo else None
                    reservation_id = rv["id"] if rv else None
                    if work_order_id or reservation_id:
                        cursor.execute(
                            "INSERT INTO credentials (user_id, work_order_id, reservation_id, exam_record_id) "
                            "VALUES (%s, %s, %s, %s)",
                            (data.user_id, work_order_id, reservation_id, exam_id),
                        )
                        credential = {
                            "work_order_id": work_order_id,
                            "reservation_id": reservation_id,
                            "exam_record_id": exam_id,
                        }

            connection.commit()

            if credential:
                message = "考试通过，已生成准入凭证"
            elif passed:
                message = "考试通过，但尚未获得准入资格（工单或预约未通过）"
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
                SELECT c.id, c.work_order_id, c.reservation_id, c.exam_record_id,
                       c.created_at AS issued_at, u.name, u.phone, e.score
                FROM credentials c
                JOIN users u ON c.user_id = u.id
                JOIN exam_records e ON c.exam_record_id = e.id
                WHERE c.user_id = %s
                ORDER BY c.id DESC LIMIT 1
                """,
                (user_id,),
            )
            credential = cursor.fetchone()
        if not credential:
            return {"success": False, "message": "暂无准入凭证"}
        # 工单/预约字段按当前结构动态组装（跟随工单更新）
        credential["display_fields"] = build_credential_display(cursor, credential)
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


@app.get("/api/visitor/status/{user_id}")
def visitor_status(user_id: int):
    """访客六态：未预约/预约审批中/预约成功/工单审批中/审批通过/审批未通过。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_card FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return {"success": False, "message": "用户不存在"}
            id_card = user["id_card"] or ""

            wo = None
            if id_card:
                cursor.execute(
                    "SELECT status FROM work_orders WHERE visitors LIKE %s AND status != 'draft' "
                    "ORDER BY id DESC LIMIT 1",
                    (f"%{id_card}%",),
                )
                wo = cursor.fetchone()
            cursor.execute(
                "SELECT status FROM reservations WHERE visitor_id = %s ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            rv = cursor.fetchone()

            status = "未预约"
            if wo and wo["status"] == 'approved':
                status = "审批通过"
            elif rv and rv["status"] == 'approved':
                status = "预约成功"
            elif wo and wo["status"] == 'pending':
                status = "工单审批中"
            elif rv and rv["status"] == 'pending':
                status = "预约审批中"
            elif wo and wo["status"] == 'rejected':
                status = "审批未通过"

        return {"success": True, "status": status}
    finally:
        connection.close()


@app.get("/api/visitor/info/{user_id}")
def visitor_info(user_id: int):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, phone, company FROM users WHERE id = %s",
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
                "SELECT c.id, c.work_order_id, c.reservation_id, c.exam_record_id, "
                "c.created_at AS issued_at, e.score "
                "FROM credentials c "
                "JOIN exam_records e ON c.exam_record_id = e.id "
                "WHERE c.user_id = %s ORDER BY c.id DESC",
                (user_id,),
            )
            credentials = cursor.fetchall()
        for c in credentials:
            c["display_fields"] = build_credential_display(cursor, c)
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
            visitors_json = json.dumps(data.visitors, ensure_ascii=False)
            custom_json = json.dumps(data.custom_fields, ensure_ascii=False)
            status = 'draft' if data.is_draft else 'pending'
            cursor.execute(
                """
                INSERT INTO work_orders
                (business_member_id, company, visitors, entry_time, exit_time, reason, area,
                 contact_name, contact_phone, accompanying_person, custom_fields, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (member["id"], data.company, visitors_json, data.entry_time, data.exit_time,
                 data.reason, data.area, data.contact_name, data.contact_phone,
                 data.accompanying_person, custom_json, status),
            )
            work_order_id = cursor.lastrowid

            if not data.is_draft:
                err = start_approval(cursor, work_order_id)
                if err:
                    connection.rollback()
                    return {"success": False, "message": err}

            connection.commit()
        msg = "草稿已保存" if data.is_draft else "工单已提交，进入审批流程"
        return {"success": True, "work_order_id": work_order_id, "message": msg}
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
                SELECT id, company, visitors, entry_time, exit_time, reason, area,
                       contact_name, contact_phone, accompanying_person, custom_fields, status, created_at
                FROM work_orders
                WHERE business_member_id = %s
                ORDER BY id DESC
                """,
                (member["id"],),
            )
            rows = cursor.fetchall()
        for row in rows:
            row["visitors"] = json.loads(row["visitors"]) if row.get("visitors") else []
            row["custom_fields"] = json.loads(row["custom_fields"]) if row.get("custom_fields") else {}
        return {"success": True, "list": rows}
    finally:
        connection.close()


@app.get("/api/work-orders/{work_order_id}")
def get_work_order_detail(work_order_id: int, member: dict = Depends(get_current_business_member)):
    """业务部查看工单详情 + 审批进度。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, company, visitors, entry_time, exit_time, reason, area, "
                "contact_name, contact_phone, accompanying_person, custom_fields, status, created_at "
                "FROM work_orders WHERE id = %s",
                (work_order_id,),
            )
            wo = cursor.fetchone()
            if not wo:
                return {"success": False, "message": "工单不存在"}
            wo["visitors"] = json.loads(wo["visitors"]) if wo.get("visitors") else []
            wo["custom_fields"] = json.loads(wo["custom_fields"]) if wo.get("custom_fields") else {}
            wo["display_fields"] = build_display_fields(cursor, wo)

            progress = {"current_step": None, "history": []}
            cursor.execute("SELECT id FROM approval_records WHERE work_order_id = %s LIMIT 1", (work_order_id,))
            ar = cursor.fetchone()
            if ar:
                cursor.execute(
                    "SELECT s.step_name FROM approval_tasks t JOIN approval_steps s ON t.step_id = s.id "
                    "WHERE t.approval_record_id = %s AND t.status = 'pending' LIMIT 1",
                    (ar["id"],),
                )
                cur = cursor.fetchone()
                if cur:
                    progress["current_step"] = cur["step_name"]
                cursor.execute(
                    "SELECT h.action, h.comment, h.created_at, s.step_name, a.real_name AS approver_name "
                    "FROM approval_history h JOIN approval_steps s ON h.step_id = s.id "
                    "JOIN admin_users a ON h.admin_id = a.id "
                    "WHERE h.approval_record_id = %s ORDER BY h.created_at ASC",
                    (ar["id"],),
                )
                progress["history"] = cursor.fetchall()
            wo["progress"] = progress
        return {"success": True, "work_order": wo}
    finally:
        connection.close()


@app.put("/api/work-orders/{work_order_id}")
def update_work_order(work_order_id: int, data: WorkOrderCreate, member: dict = Depends(get_current_business_member)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            visitors_json = json.dumps(data.visitors, ensure_ascii=False)
            custom_json = json.dumps(data.custom_fields, ensure_ascii=False)
            cursor.execute(
                "UPDATE work_orders SET company=%s, visitors=%s, entry_time=%s, exit_time=%s, reason=%s, "
                "area=%s, contact_name=%s, contact_phone=%s, accompanying_person=%s, custom_fields=%s "
                "WHERE id=%s AND status='draft'",
                (data.company, visitors_json, data.entry_time, data.exit_time, data.reason,
                 data.area, data.contact_name, data.contact_phone, data.accompanying_person,
                 custom_json, work_order_id),
            )
            connection.commit()
        return {"success": True, "message": "草稿已更新"}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.post("/api/work-orders/{work_order_id}/submit")
def submit_work_order(work_order_id: int, member: dict = Depends(get_current_business_member)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status FROM work_orders WHERE id = %s", (work_order_id,))
            wo = cursor.fetchone()
            if not wo:
                return {"success": False, "message": "工单不存在"}
            if wo["status"] != 'draft':
                return {"success": False, "message": "只有草稿可以提交"}
            cursor.execute("UPDATE work_orders SET status='pending' WHERE id = %s", (work_order_id,))
            err = start_approval(cursor, work_order_id)
            if err:
                connection.rollback()
                return {"success": False, "message": err}
            connection.commit()
        return {"success": True, "message": "工单已提交，进入审批流程"}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.delete("/api/work-orders/{work_order_id}")
def delete_work_order(work_order_id: int, member: dict = Depends(get_current_business_member)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM work_orders WHERE id = %s AND status = 'draft'", (work_order_id,))
            connection.commit()
        return {"success": True, "message": "草稿已删除"}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.post("/api/reservations")
def create_reservation(data: ReservationCreate):
    """访客快速预约：部门主管直属单级审批。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            visitors_json = json.dumps(data.visitors, ensure_ascii=False)
            cursor.execute(
                "INSERT INTO reservations (visitor_id, company, visitors, entry_time, exit_time, reason, "
                "area, contact_name, contact_phone, accompanying_person, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')",
                (data.visitor_id, data.company, visitors_json, data.entry_time, data.exit_time,
                 data.reason, data.area, data.contact_name, data.contact_phone, data.accompanying_person),
            )
            reservation_id = cursor.lastrowid

            dept_admin = find_admin_by_role(cursor, '部门主管')
            if not dept_admin:
                connection.rollback()
                return {"success": False, "message": "找不到部门主管，暂时无法预约"}
            cursor.execute("SELECT id FROM approval_steps WHERE required_role = '部门主管' LIMIT 1")
            step = cursor.fetchone()

            cursor.execute(
                "INSERT INTO approval_records (reservation_id, status) VALUES (%s, 'pending')",
                (reservation_id,),
            )
            approval_record_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO approval_tasks (approval_record_id, step_id, admin_id, status) "
                "VALUES (%s, %s, %s, 'pending')",
                (approval_record_id, step["id"] if step else None, dept_admin["id"]),
            )
            connection.commit()
        return {"success": True, "reservation_id": reservation_id, "message": "预约已提交，等待部门主管审批"}
    except Exception as e:
        connection.rollback()
        return {"success": False, "message": str(e)}
    finally:
        connection.close()


@app.get("/api/reservations/mine")
def get_my_reservations(visitor_id: int = Query(...)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, company, visitors, entry_time, exit_time, reason, area, "
                "contact_name, contact_phone, accompanying_person, status, created_at "
                "FROM reservations WHERE visitor_id = %s ORDER BY id DESC",
                (visitor_id,),
            )
            rows = cursor.fetchall()
        for row in rows:
            row["visitors"] = json.loads(row["visitors"]) if row.get("visitors") else []
        return {"success": True, "list": rows}
    finally:
        connection.close()


@app.get("/api/reservations")
def list_reservations(current_admin: dict = Depends(get_current_admin)):
    """管理端预约列表。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT r.id, r.visitor_id, r.company, r.visitors, r.entry_time, r.exit_time, r.reason, r.area, "
                "r.contact_name, r.contact_phone, r.accompanying_person, r.status, r.created_at, "
                "ar.id AS approval_record_id "
                "FROM reservations r LEFT JOIN approval_records ar ON ar.reservation_id = r.id "
                "ORDER BY r.id DESC"
            )
            rows = cursor.fetchall()
        for row in rows:
            row["visitors"] = json.loads(row["visitors"]) if row.get("visitors") else []
        return ok({"list": rows, "total": len(rows)})
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
                    COALESCE(work_orders.company, reservations.company) AS company,
                    COALESCE(work_orders.entry_time, reservations.entry_time) AS entry_time,
                    COALESCE(work_orders.exit_time, reservations.exit_time) AS exit_time,
                    COALESCE(work_orders.reason, reservations.reason) AS reason,
                    COALESCE(work_orders.area, reservations.area) AS area,
                    COALESCE(work_orders.contact_name, reservations.contact_name) AS contact_name,
                    COALESCE(work_orders.contact_phone, reservations.contact_phone) AS contact_phone,
                    COALESCE(work_orders.accompanying_person, reservations.accompanying_person) AS accompanying_person,
                    COALESCE(work_orders.visitors, reservations.visitors) AS visitors,
                    CASE WHEN work_orders.id IS NOT NULL THEN 'work_order' ELSE 'reservation' END AS biz_type,
                    approval_steps.step_name
                FROM approval_tasks
                JOIN approval_records ON approval_tasks.approval_record_id = approval_records.id
                LEFT JOIN work_orders ON approval_records.work_order_id = work_orders.id
                LEFT JOIN reservations ON approval_records.reservation_id = reservations.id
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                WHERE approval_tasks.admin_id = %s AND approval_tasks.status = 'pending'
                ORDER BY approval_tasks.created_at ASC
                """,
                (current_admin["id"],),
            )
            tasks = cursor.fetchall()
        for t in tasks:
            t["visitors"] = json.loads(t["visitors"]) if t.get("visitors") else []
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
                    COALESCE(work_orders.company, reservations.company) AS company,
                    COALESCE(work_orders.entry_time, reservations.entry_time) AS entry_time,
                    COALESCE(work_orders.reason, reservations.reason) AS reason,
                    COALESCE(work_orders.area, reservations.area) AS area,
                    COALESCE(work_orders.accompanying_person, reservations.accompanying_person) AS accompanying_person,
                    COALESCE(work_orders.visitors, reservations.visitors) AS visitors,
                    CASE WHEN work_orders.id IS NOT NULL THEN 'work_order' ELSE 'reservation' END AS biz_type,
                    approval_steps.step_name
                FROM approval_tasks
                JOIN approval_records ON approval_tasks.approval_record_id = approval_records.id
                LEFT JOIN work_orders ON approval_records.work_order_id = work_orders.id
                LEFT JOIN reservations ON approval_records.reservation_id = reservations.id
                JOIN approval_steps ON approval_tasks.step_id = approval_steps.id
                WHERE approval_tasks.admin_id = %s
                AND approval_tasks.status IN ('approved', 'rejected')
                ORDER BY approval_tasks.approved_at DESC
                """,
                (current_admin["id"],),
            )
            tasks = cursor.fetchall()
        for t in tasks:
            t["visitors"] = json.loads(t["visitors"]) if t.get("visitors") else []
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
                sync_biz_status(cursor, task["approval_record_id"], "rejected")
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
                sync_biz_status(cursor, task["approval_record_id"], "approved")
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
                    work_orders.company, work_orders.entry_time, work_orders.exit_time,
                    work_orders.reason, work_orders.area,
                    work_orders.contact_name, work_orders.contact_phone,
                    work_orders.accompanying_person, work_orders.visitors,
                    work_orders.custom_fields,
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
        for row in rows:
            row["visitors"] = json.loads(row["visitors"]) if row.get("visitors") else []
            row["custom_fields"] = json.loads(row["custom_fields"]) if row.get("custom_fields") else {}
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
                    COALESCE(work_orders.company, reservations.company) AS company,
                    COALESCE(work_orders.entry_time, reservations.entry_time) AS entry_time,
                    COALESCE(work_orders.exit_time, reservations.exit_time) AS exit_time,
                    COALESCE(work_orders.reason, reservations.reason) AS reason,
                    COALESCE(work_orders.area, reservations.area) AS area,
                    COALESCE(work_orders.contact_name, reservations.contact_name) AS contact_name,
                    COALESCE(work_orders.contact_phone, reservations.contact_phone) AS contact_phone,
                    COALESCE(work_orders.accompanying_person, reservations.accompanying_person) AS accompanying_person,
                    COALESCE(work_orders.visitors, reservations.visitors) AS visitors,
                    work_orders.custom_fields AS custom_fields,
                    approval_records.status AS approval_status,
                    approval_records.created_at AS application_time
                FROM approval_records
                LEFT JOIN work_orders ON approval_records.work_order_id = work_orders.id
                LEFT JOIN reservations ON approval_records.reservation_id = reservations.id
                WHERE approval_records.id = %s
                """,
                (record_id,),
            )
            detail = cursor.fetchone()
            if not detail:
                return fail("审批记录不存在")
            detail["visitors"] = json.loads(detail["visitors"]) if detail.get("visitors") else []
            detail["custom_fields"] = json.loads(detail["custom_fields"]) if detail.get("custom_fields") else {}
            detail["display_fields"] = build_display_fields(cursor, detail)

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
            # 判断是工单审批还是预约审批
            cursor.execute(
                "SELECT work_order_id, reservation_id FROM approval_records WHERE id = %s",
                (record_id,),
            )
            ar = cursor.fetchone()
            is_reservation = bool(ar and ar.get("reservation_id") and not ar.get("work_order_id"))

            if is_reservation:
                # 预约：单级审批，只显示部门主管节点
                cursor.execute(
                    "SELECT id, step_name, step_order, required_role, node_x, node_y "
                    "FROM approval_steps WHERE required_role = '部门主管' ORDER BY step_order ASC"
                )
                nodes = cursor.fetchall()
                transitions = []
            else:
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
# 管理端：题库管理
# =========================

@app.get("/api/admin/questions")
def list_questions(current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, question, option_a, option_b, option_c, option_d, score, correct_answer, is_active "
                "FROM questions ORDER BY id ASC"
            )
            rows = cursor.fetchall()
        return ok({"list": rows, "total": len(rows)})
    finally:
        connection.close()


@app.post("/api/admin/questions")
def create_question(data: QuestionCreate, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO questions (question, option_a, option_b, option_c, option_d, score, correct_answer, is_active) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (data.question, data.option_a, data.option_b, data.option_c, data.option_d,
                 data.score, data.correct_answer, data.is_active),
            )
            connection.commit()
            return ok({"id": cursor.lastrowid}, "创建成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.put("/api/admin/questions/{question_id}")
def update_question(question_id: int, data: QuestionCreate, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE questions SET question=%s, option_a=%s, option_b=%s, option_c=%s, option_d=%s, "
                "score=%s, correct_answer=%s, is_active=%s WHERE id=%s",
                (data.question, data.option_a, data.option_b, data.option_c, data.option_d,
                 data.score, data.correct_answer, data.is_active, question_id),
            )
            connection.commit()
        return ok(None, "更新成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.delete("/api/admin/questions/{question_id}")
def delete_question(question_id: int, current_admin: dict = Depends(get_current_admin)):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM questions WHERE id = %s", (question_id,))
            connection.commit()
        return ok(None, "删除成功")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


# =========================
# 管理端：自定义工单结构
# =========================

# 默认工单结构（恢复默认时据此重建；field_key 与 work_orders 固定列对应）
DEFAULT_WORK_ORDER_FIELDS = [
    {"field_key": "company",             "field_name": "来访单位",       "input_type": "text",     "options": [], "required": True,  "sort_order": 1},
    {"field_key": "visitors",            "field_name": "来访人员",       "input_type": "visitors", "options": [], "required": False, "sort_order": 2},
    {"field_key": "entry_time",          "field_name": "进入时间",       "input_type": "datetime", "options": [], "required": False, "sort_order": 3},
    {"field_key": "exit_time",           "field_name": "出去时间",       "input_type": "datetime", "options": [], "required": False, "sort_order": 4},
    {"field_key": "reason",              "field_name": "进出原因",       "input_type": "select",   "options": ["设备维护", "施工", "参观考察", "业务洽谈", "其他"], "required": False, "sort_order": 5},
    {"field_key": "area",                "field_name": "活动区域",       "input_type": "text",     "options": [], "required": False, "sort_order": 6},
    {"field_key": "contact_name",        "field_name": "来访单位联系人", "input_type": "text",     "options": [], "required": False, "sort_order": 7},
    {"field_key": "contact_phone",       "field_name": "联系人电话",     "input_type": "text",     "options": [], "required": False, "sort_order": 8},
    {"field_key": "accompanying_person", "field_name": "陪同人员",       "input_type": "text",     "options": [], "required": False, "sort_order": 9},
]


def _parse_field_row(row):
    """把 options 列（JSON 字符串）解析成列表，供前端直接使用。"""
    if row.get("options"):
        try:
            row["options"] = json.loads(row["options"])
        except Exception:
            row["options"] = []
    else:
        row["options"] = []
    return row


@app.get("/api/admin/work-order-fields")
def list_work_order_fields(current_admin: dict = Depends(get_current_admin)):
    """当前工单结构（默认字段 + 自定义字段）。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, field_key, field_name, input_type, options, required, sort_order, is_default "
                "FROM work_order_fields ORDER BY sort_order ASC, id ASC"
            )
            rows = cursor.fetchall()
        rows = [_parse_field_row(r) for r in rows]
        return ok({"list": rows, "total": len(rows)})
    finally:
        connection.close()


@app.post("/api/admin/work-order-fields/save")
def save_work_order_fields(data: WorkOrderFieldsSave, current_admin: dict = Depends(get_current_admin)):
    """批量保存整个工单结构（先清空再写入）。"""
    connection = get_connection()
    try:
        if not data.fields:
            return fail("工单结构不能为空，至少保留一个字段")
        with connection.cursor() as cursor:
            # 保存当前 is_default 标记（用于恢复默认），清空重建
            cursor.execute("SELECT field_key FROM work_order_fields WHERE is_default = 1")
            default_keys = {r["field_key"] for r in cursor.fetchall()}
            cursor.execute("DELETE FROM work_order_fields")

            fields = list(data.fields)
            # 保护「来访人员」字段：不可被删除，且类型固定为 visitors
            has_visitors = any(f.field_key == "visitors" for f in fields)
            if not has_visitors:
                fields.insert(0, WorkOrderFieldItem(
                    field_key="visitors", field_name="来访人员",
                    input_type="visitors", options=[], required=False, sort_order=2,
                ))
            for i, f in enumerate(fields):
                key = f.field_key.strip() or f"custom_{int(time.time())}_{i}"
                if key == "visitors":
                    f.input_type = "visitors"  # 锁死类型
                # 默认字段的 key 保持 is_default 标记；自定义字段 is_default=0
                is_default = 1 if key in default_keys else 0
                options_json = json.dumps(f.options, ensure_ascii=False)
                cursor.execute(
                    "INSERT INTO work_order_fields (field_key, field_name, input_type, options, required, sort_order, is_default) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (key, f.field_name, f.input_type, options_json, f.required, f.sort_order, is_default),
                )
            connection.commit()
        return ok(None, "工单结构已保存")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.post("/api/admin/work-order-fields/reset")
def reset_work_order_fields(current_admin: dict = Depends(get_current_admin)):
    """恢复默认工单结构。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM work_order_fields")
            for f in DEFAULT_WORK_ORDER_FIELDS:
                options_json = json.dumps(f["options"], ensure_ascii=False)
                cursor.execute(
                    "INSERT INTO work_order_fields (field_key, field_name, input_type, options, required, sort_order, is_default) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 1)",
                    (f["field_key"], f["field_name"], f["input_type"], options_json, f["required"], f["sort_order"]),
                )
            connection.commit()
        return ok(None, "已恢复默认工单结构")
    except Exception as e:
        connection.rollback()
        return fail(str(e), code=500)
    finally:
        connection.close()


@app.get("/api/work-order-fields/active")
def get_active_work_order_fields(member: dict = Depends(get_current_business_member)):
    """业务部成员拉取当前工单结构（用于工单表单动态渲染）。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, field_key, field_name, input_type, options, required, sort_order "
                "FROM work_order_fields ORDER BY sort_order ASC, id ASC"
            )
            rows = cursor.fetchall()
        rows = [_parse_field_row(r) for r in rows]
        return {"success": True, "fields": rows}
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
