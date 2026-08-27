"""数据库连接配置。

统一提供 get_connection()，供所有接口复用。
连接参数可通过环境变量覆盖（默认值与开发环境一致）。
"""
import os

import pymysql
from pymysql.cursors import DictCursor


def get_connection():
    return pymysql.connect(
        host=os.environ.get("DC_ACCESS_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DC_ACCESS_DB_PORT", "3306")),
        user=os.environ.get("DC_ACCESS_DB_USER", "root"),
        password=os.environ.get("DC_ACCESS_DB_PASSWORD", "20060306"),
        database=os.environ.get("DC_ACCESS_DB_NAME", "dc_access_system"),
        charset="utf8mb4",
        cursorclass=DictCursor,
    )
