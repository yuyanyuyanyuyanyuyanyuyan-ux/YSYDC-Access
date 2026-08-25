import pymysql


def get_connection():
    connection = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="20060306",
        database="dc_access_system",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

    return connection