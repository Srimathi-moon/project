from flask import Flask, render_template
import psutil
import sqlite3
import time
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__)

DB_NAME = "disk_io.db"


def create_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS disk_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cpu_usage REAL,
        memory_usage REAL,
        disk_read REAL,
        disk_write REAL,
        disk_load TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_disk_load(read_speed, write_speed):
    total = read_speed + write_speed

    if total < 1:
        return "Low"
    elif total < 10:
        return "Medium"
    else:
        return "High"


def collect_current_data():
    old_disk = psutil.disk_io_counters()
    time.sleep(1)
    new_disk = psutil.disk_io_counters()

    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent

    read_speed = (new_disk.read_bytes - old_disk.read_bytes) / (1024 * 1024)
    write_speed = (new_disk.write_bytes - old_disk.write_bytes) / (1024 * 1024)

    load = get_disk_load(read_speed, write_speed)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO disk_metrics 
    (cpu_usage, memory_usage, disk_read, disk_write, disk_load)
    VALUES (?, ?, ?, ?, ?)
    """, (cpu, memory, read_speed, write_speed, load))

    conn.commit()
    conn.close()

    return cpu, memory, read_speed, write_speed, load


def train_and_predict(cpu, memory, read_speed, write_speed):
    conn = sqlite3.connect(DB_NAME)
    data = pd.read_sql_query("SELECT * FROM disk_metrics", conn)
    conn.close()

    if len(data) < 5:
        return "Collect more data"

    X = data[["cpu_usage", "memory_usage", "disk_read", "disk_write"]]
    y = data["disk_load"]

    model = RandomForestClassifier()
    model.fit(X, y)

    current_data = pd.DataFrame([{
        "cpu_usage": cpu,
        "memory_usage": memory,
        "disk_read": read_speed,
        "disk_write": write_speed
    }])

    prediction = model.predict(current_data)
    return prediction[0]


@app.route("/")
def dashboard():
    create_table()

    cpu, memory, read_speed, write_speed, actual_load = collect_current_data()
    predicted_load = train_and_predict(cpu, memory, read_speed, write_speed)

    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM disk_metrics ORDER BY id DESC LIMIT 10", conn)
    conn.close()

    records = df.to_dict(orient="records")

    return render_template(
        "index.html",
        cpu=round(cpu, 2),
        memory=round(memory, 2),
        read_speed=round(read_speed, 2),
        write_speed=round(write_speed, 2),
        actual_load=actual_load,
        predicted_load=predicted_load,
        records=records
    )


if __name__ == "__main__":
    app.run(debug=True)