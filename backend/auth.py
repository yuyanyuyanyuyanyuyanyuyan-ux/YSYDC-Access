"""鉴权与权限：令牌签发/校验、当前管理员依赖、角色权限与菜单。

令牌采用 HMAC-SHA256 签名的 JWT 结构（仅用标准库实现，零额外依赖）。
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Request

from config.database import get_connection

# 生产环境请通过环境变量覆盖
SECRET_KEY = os.environ.get("DC_ACCESS_SECRET", "dc-access-secret-change-me").encode()
TOKEN_EXPIRE_SECONDS = int(os.environ.get("DC_ACCESS_TOKEN_EXPIRE", "86400"))


class AuthError(Exception):
    """鉴权异常：由 main.py 的异常处理器统一转成 {code, msg}（HTTP 200）。"""

    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(message: str) -> str:
    return _b64url(hmac.new(SECRET_KEY, message.encode(), hashlib.sha256).digest())


def create_access_token(admin_id: int, username: str, role: str) -> str:
    header = _b64url(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _b64url(
        json.dumps(
            {
                "sub": str(admin_id),
                "username": username,
                "role": role,
                "exp": int(time.time()) + TOKEN_EXPIRE_SECONDS,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = _sign(f"{header}.{payload}")
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
    except ValueError:
        raise AuthError(401, "无效的登录凭证")
    expected = _sign(f"{header}.{payload}")
    if not hmac.compare_digest(signature, expected):
        raise AuthError(401, "无效的登录凭证")
    data = json.loads(_b64url_decode(payload))
    if data.get("exp", 0) < time.time():
        raise AuthError(401, "登录已过期")
    return data


def get_current_admin(request: Request) -> dict:
    """FastAPI 依赖：从 Authorization: Bearer <token> 解析当前管理员。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError(401, "未登录")
    data = decode_access_token(auth[7:])
    return {
        "id": int(data["sub"]),
        "username": data.get("username"),
        "role": data.get("role"),
    }


def get_admin_row(admin_id: int):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, real_name, phone, role, parent_admin_id "
                "FROM admin_users WHERE id = %s",
                (admin_id,),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def is_top_admin(admin_id: int) -> bool:
    """顶层管理员（parent_admin_id 为空/0）可查看全部工单。"""
    row = get_admin_row(admin_id)
    if not row:
        return False
    parent = row.get("parent_admin_id")
    return parent is None or parent == 0 or parent == ""


def build_menus(top: bool) -> list:
    """返回菜单树（前端 generateRoute 据此生成动态路由）。"""
    children = [
        {
            "id": 11,
            "name": "待办任务",
            "permission": "task:todo",
            "type": 2,
            "sort": 1,
            "parentId": 1,
            "path": "todo",
            "icon": "ep:clock",
            "component": "bpm/task/todo/index",
            "componentName": "BpmTodoTask",
            "status": 0,
            "visible": True,
            "keepAlive": True,
            "alwaysShow": False,
        },
        {
            "id": 12,
            "name": "已办任务",
            "permission": "task:done",
            "type": 2,
            "sort": 2,
            "parentId": 1,
            "path": "done",
            "icon": "ep:finished",
            "component": "bpm/task/done/index",
            "componentName": "BpmDoneTask",
            "status": 0,
            "visible": True,
            "keepAlive": True,
            "alwaysShow": False,
        },
    ]
    if top:
        children.insert(
            0,
            {
                "id": 13,
                "name": "工单列表",
                "permission": "work-order:list:all",
                "type": 2,
                "sort": 3,
                "parentId": 1,
                "path": "work-orders",
                "icon": "ep:list",
                "component": "bpm/processInstance/manager/index",
                "componentName": "BpmWorkOrders",
                "status": 0,
                "visible": True,
                "keepAlive": True,
                "alwaysShow": False,
            },
        )
    return [
        {
            "id": 1,
            "name": "审批管理",
            "permission": "",
            "type": 1,
            "sort": 1,
            "parentId": 0,
            "path": "/bpm",
            "icon": "ep:notebook",
            "component": "",
            "componentName": "",
            "status": 0,
            "visible": True,
            "keepAlive": True,
            "alwaysShow": True,
            "children": children,
        }
    ]


def build_permission_info(current_admin: dict) -> dict:
    """返回 {user, roles, permissions, menus}，供前端登录后拉取权限。"""
    row = get_admin_row(current_admin["id"])
    top = is_top_admin(current_admin["id"])
    real_name = (row.get("real_name") if row else None) or current_admin.get("username")
    role = (row.get("role") if row else None) or current_admin.get("role")

    if top:
        permissions = ["*:*:*"]
    else:
        permissions = ["work-order:view", "task:todo", "task:done", "task:approve"]

    return {
        "user": {
            "id": current_admin["id"],
            "nickname": real_name,
            "avatar": "",
            "deptId": 0,
        },
        "roles": [role] if role else [],
        "permissions": permissions,
        "menus": build_menus(top),
    }
