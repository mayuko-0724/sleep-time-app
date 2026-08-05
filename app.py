from datetime import datetime, timedelta
import os
import sqlite3

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

DB_DIR = os.environ.get("DB_DIR", "data")
DB_PATH = os.path.join(DB_DIR, "sleep_records.db")


def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sleep_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sleep_date TEXT NOT NULL,
                bedtime TEXT NOT NULL,
                wake_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                memo TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def calculate_sleep_minutes(sleep_date: str, bedtime: str, wake_time: str) -> int:
    start = datetime.strptime(f"{sleep_date} {bedtime}", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{sleep_date} {wake_time}", "%Y-%m-%d %H:%M")

    if end <= start:
        end += timedelta(days=1)

    return int((end - start).total_seconds() // 60)


def format_minutes(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}時間{mins}分"


def sleep_comment(minutes: int) -> tuple[str, str]:
    hours = minutes / 60
    if hours < 6:
        return "短め", "睡眠時間が短めです。翌日の集中力低下を防ぐため、早めに休む予定を立ててみましょう。"
    if hours <= 8.5:
        return "標準", "よい睡眠時間です。この調子で生活リズムを保ちましょう。"
    return "長め", "睡眠時間が長めです。疲れが残っている可能性もあるため、生活リズムを確認してみましょう。"


def fetch_records():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, sleep_date, bedtime, wake_time, duration_minutes, memo, created_at
            FROM sleep_records
            ORDER BY sleep_date DESC, id DESC
            LIMIT 10
            """
        ).fetchall()

    records = []
    for row in rows:
        status, comment = sleep_comment(row["duration_minutes"])
        records.append(
            {
                "id": row["id"],
                "sleep_date": row["sleep_date"],
                "bedtime": row["bedtime"],
                "wake_time": row["wake_time"],
                "duration": format_minutes(row["duration_minutes"]),
                "status": status,
                "comment": comment,
                "memo": row["memo"] or "",
            }
        )
    return records


def fetch_summary():
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count, AVG(duration_minutes) AS avg_minutes
            FROM sleep_records
            """
        ).fetchone()

    count = row["count"] or 0
    avg_minutes = row["avg_minutes"]
    if count == 0 or avg_minutes is None:
        return {"count": 0, "average": "未記録"}
    return {"count": count, "average": format_minutes(int(avg_minutes))}


@app.route("/", methods=["GET"])
def index():
    init_db()
    return render_template(
        "index.html",
        records=fetch_records(),
        summary=fetch_summary(),
        error=None,
    )


@app.route("/add", methods=["POST"])
def add_record():
    init_db()
    sleep_date = request.form.get("sleep_date", "").strip()
    bedtime = request.form.get("bedtime", "").strip()
    wake_time = request.form.get("wake_time", "").strip()
    memo = request.form.get("memo", "").strip()

    if not sleep_date or not bedtime or not wake_time:
        return render_template(
            "index.html",
            records=fetch_records(),
            summary=fetch_summary(),
            error="日付・就寝時刻・起床時刻を入力してください。",
        )

    try:
        duration_minutes = calculate_sleep_minutes(sleep_date, bedtime, wake_time)
    except ValueError:
        return render_template(
            "index.html",
            records=fetch_records(),
            summary=fetch_summary(),
            error="入力形式が正しくありません。",
        )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sleep_records
            (sleep_date, bedtime, wake_time, duration_minutes, memo, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sleep_date,
                bedtime,
                wake_time,
                duration_minutes,
                memo,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()

    return redirect(url_for("index"))


@app.route("/delete/<int:record_id>", methods=["POST"])
def delete_record(record_id):
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM sleep_records WHERE id = ?", (record_id,))
        conn.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)