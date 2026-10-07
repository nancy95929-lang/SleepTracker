import sqlite3
from datetime import datetime

DB_NAME = "sleep.db"


def connect():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _column_names(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(sleep_records)")
    return {row["name"] for row in cursor.fetchall()}


def _deduplicate_dates(conn):
    """
    舊版本若留下同一天多筆紀錄，每個 sleep_date 只保留一筆：
    1. 優先保留已完成紀錄
    2. 若同日有多筆已完成紀錄，保留睡眠時間最長者
    3. 若都未完成，保留 id 最大者
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sleep_date
        FROM sleep_records
        GROUP BY sleep_date
        HAVING COUNT(*) > 1
    """)

    duplicate_dates = [row["sleep_date"] for row in cursor.fetchall()]

    for sleep_date in duplicate_dates:
        cursor.execute("""
            SELECT id, sleep_time, wake_time
            FROM sleep_records
            WHERE sleep_date = ?
        """, (sleep_date,))

        rows = cursor.fetchall()

        def score(row):
            record_id = row["id"]
            sleep_time_text = row["sleep_time"]
            wake_time_text = row["wake_time"]

            if wake_time_text:
                try:
                    sleep_time = datetime.fromisoformat(sleep_time_text)
                    wake_time = datetime.fromisoformat(wake_time_text)
                    minutes = max(
                        0,
                        int((wake_time - sleep_time).total_seconds() // 60)
                    )
                except Exception:
                    minutes = 0

                return (2, minutes, record_id)

            return (1, 0, record_id)

        keep_id = max(rows, key=score)["id"]

        cursor.execute("""
            DELETE FROM sleep_records
            WHERE sleep_date = ?
              AND id != ?
        """, (sleep_date, keep_id))


def create_table():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sleep_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sleep_time TEXT NOT NULL,
            wake_time TEXT,
            sleep_date TEXT NOT NULL,
            note TEXT
        )
    """)

    # v0.6 預留 iOS 睡後手機使用資料欄位
    columns = _column_names(conn)

    migrations = {
        "last_phone_activity_time": "TEXT",
        "last_phone_app": "TEXT",
        "post_checkin_screen_minutes": "INTEGER",
        "activity_source": "TEXT",
        "activity_status": "TEXT",
        "monitoring_started_at": "TEXT",
        "monitoring_ended_at": "TEXT",
    }

    for column, column_type in migrations.items():
        if column not in columns:
            cursor.execute(
                f"ALTER TABLE sleep_records ADD COLUMN {column} {column_type}"
            )

    _deduplicate_dates(conn)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_sleep_date
        ON sleep_records(sleep_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sleep_time
        ON sleep_records(sleep_time)
    """)

    conn.commit()
    conn.close()


def record_exists_for_date(sleep_date, exclude_id=None):
    conn = connect()
    cursor = conn.cursor()

    if exclude_id is None:
        cursor.execute("""
            SELECT 1
            FROM sleep_records
            WHERE sleep_date = ?
            LIMIT 1
        """, (sleep_date,))
    else:
        cursor.execute("""
            SELECT 1
            FROM sleep_records
            WHERE sleep_date = ?
              AND id != ?
            LIMIT 1
        """, (sleep_date, exclude_id))

    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def start_sleep():
    now = datetime.now()
    sleep_date = now.strftime("%Y-%m-%d")

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO sleep_records (
                sleep_time,
                wake_time,
                sleep_date,
                note
            )
            VALUES (?, NULL, ?, '')
        """, (
            now.isoformat(),
            sleep_date,
        ))
        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()

        return {
            "ok": False,
            "reason": "duplicate_date",
            "sleep_date": sleep_date,
        }

    conn.close()

    return {
        "ok": True,
        "record_id": cursor.lastrowid,
        "sleep_time": now,
        "sleep_date": sleep_date,
    }


def wake_up():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, sleep_time
        FROM sleep_records
        WHERE wake_time IS NULL
        ORDER BY sleep_time DESC
        LIMIT 1
    """)

    record = cursor.fetchone()

    if record is None:
        conn.close()
        return None

    record_id = record["id"]
    sleep_time_text = record["sleep_time"]
    now = datetime.now()

    cursor.execute("""
        UPDATE sleep_records
        SET wake_time = ?
        WHERE id = ?
    """, (
        now.isoformat(),
        record_id,
    ))

    conn.commit()
    conn.close()

    sleep_time = datetime.fromisoformat(sleep_time_text)
    duration = now - sleep_time
    total_minutes = max(0, int(duration.total_seconds() // 60))

    return {
        "record_id": record_id,
        "hours": total_minutes // 60,
        "minutes": total_minutes % 60,
        "sleep_time": sleep_time,
        "wake_time": now,
    }


def get_active_sleep():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, sleep_time, sleep_date
        FROM sleep_records
        WHERE wake_time IS NULL
        ORDER BY sleep_time DESC
        LIMIT 1
    """)

    record = cursor.fetchone()
    conn.close()
    return tuple(record) if record else None


def get_streak():
    dates = _completed_dates_desc()

    if not dates:
        return 0

    streak = 1

    for i in range(len(dates) - 1):
        if (dates[i] - dates[i + 1]).days == 1:
            streak += 1
        else:
            break

    return streak


def get_longest_streak():
    dates = sorted(set(_completed_dates_desc()))

    if not dates:
        return 0

    longest = 1
    current = 1

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    return longest


def _completed_dates_desc():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sleep_date
        FROM sleep_records
        WHERE wake_time IS NOT NULL
        ORDER BY sleep_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        datetime.strptime(row["sleep_date"], "%Y-%m-%d").date()
        for row in rows
    ]


def get_all_records():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            sleep_time,
            wake_time,
            sleep_date,
            note,
            last_phone_activity_time,
            last_phone_app,
            post_checkin_screen_minutes,
            activity_source,
            activity_status,
            monitoring_started_at,
            monitoring_ended_at
        FROM sleep_records
        ORDER BY sleep_time DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    records = []

    for row in rows:
        sleep_time = datetime.fromisoformat(row["sleep_time"])

        if row["wake_time"]:
            wake_time = datetime.fromisoformat(row["wake_time"])
            duration = wake_time - sleep_time
            total_minutes = max(0, int(duration.total_seconds() // 60))
            hours = total_minutes // 60
            minutes = total_minutes % 60
        else:
            wake_time = None
            hours = None
            minutes = None

        last_activity = None
        if row["last_phone_activity_time"]:
            try:
                last_activity = datetime.fromisoformat(
                    row["last_phone_activity_time"]
                )
            except Exception:
                last_activity = None

        records.append({
            "id": row["id"],
            "sleep_date": row["sleep_date"],
            "sleep_time": sleep_time,
            "wake_time": wake_time,
            "hours": hours,
            "minutes": minutes,
            "note": row["note"] or "",
            "last_phone_activity_time": last_activity,
            "last_phone_app": row["last_phone_app"] or "",
            "post_checkin_screen_minutes": (
                row["post_checkin_screen_minutes"]
                if row["post_checkin_screen_minutes"] is not None
                else None
            ),
            "activity_source": row["activity_source"] or "",
            "activity_status": row["activity_status"] or "",
            "monitoring_started_at": (
                datetime.fromisoformat(row["monitoring_started_at"])
                if row["monitoring_started_at"]
                else None
            ),
            "monitoring_ended_at": (
                datetime.fromisoformat(row["monitoring_ended_at"])
                if row["monitoring_ended_at"]
                else None
            ),
        })

    return records


def add_manual_record(sleep_time, wake_time, note=""):
    sleep_date = sleep_time.strftime("%Y-%m-%d")

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO sleep_records (
                sleep_time,
                wake_time,
                sleep_date,
                note
            )
            VALUES (?, ?, ?, ?)
        """, (
            sleep_time.isoformat(),
            wake_time.isoformat(),
            sleep_date,
            note,
        ))
        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()

        return {
            "ok": False,
            "reason": "duplicate_date",
            "sleep_date": sleep_date,
        }

    conn.close()

    return {
        "ok": True,
        "sleep_date": sleep_date,
    }


def update_record(record_id, sleep_time, wake_time, note=""):
    sleep_date = sleep_time.strftime("%Y-%m-%d")

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE sleep_records
            SET
                sleep_time = ?,
                wake_time = ?,
                sleep_date = ?,
                note = ?
            WHERE id = ?
        """, (
            sleep_time.isoformat(),
            wake_time.isoformat() if wake_time else None,
            sleep_date,
            note,
            record_id,
        ))
        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()

        return {
            "ok": False,
            "reason": "duplicate_date",
            "sleep_date": sleep_date,
        }

    conn.close()

    return {
        "ok": True,
        "sleep_date": sleep_date,
    }



def mark_phone_monitoring_started(record_id):
    """標記睡後手機偵測流程已啟動；正式 iOS 版由原生橋接接手。"""
    conn = connect()
    cursor = conn.cursor()
    now = datetime.now()

    cursor.execute("""
        UPDATE sleep_records
        SET
            activity_status = ?,
            monitoring_started_at = ?,
            monitoring_ended_at = NULL,
            activity_source = ?
        WHERE id = ?
    """, (
        "waiting_for_ios",
        now.isoformat(),
        "ios_bridge_pending",
        record_id,
    ))

    conn.commit()
    conn.close()


def mark_phone_monitoring_stopped(record_id):
    """起床時結束監測流程。若尚無原生資料，不偽造使用分鐘。"""
    conn = connect()
    cursor = conn.cursor()
    now = datetime.now()

    cursor.execute("""
        UPDATE sleep_records
        SET
            activity_status = CASE
                WHEN post_checkin_screen_minutes IS NOT NULL
                    THEN 'data_ready'
                ELSE 'waiting_for_ios_data'
            END,
            monitoring_ended_at = ?
        WHERE id = ?
    """, (
        now.isoformat(),
        record_id,
    ))

    conn.commit()
    conn.close()


def get_record(record_id):
    for record in get_all_records():
        if record["id"] == record_id:
            return record
    return None


def update_phone_activity(
    record_id,
    last_phone_activity_time=None,
    last_phone_app="",
    post_checkin_screen_minutes=None,
    activity_source="",
):
    """
    供未來 iOS 原生橋接使用。
    Windows / Flet 開發階段不會自行填入這些欄位。
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sleep_records
        SET
            last_phone_activity_time = ?,
            last_phone_app = ?,
            post_checkin_screen_minutes = ?,
            activity_source = ?,
            activity_status = 'data_ready'
        WHERE id = ?
    """, (
        (
            last_phone_activity_time.isoformat()
            if last_phone_activity_time
            else None
        ),
        last_phone_app or None,
        post_checkin_screen_minutes,
        activity_source or None,
        record_id,
    ))

    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM sleep_records
        WHERE id = ?
    """, (record_id,))

    conn.commit()
    conn.close()
