import csv
import random
import multiprocessing as mp
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# =========================
# CONFIG
# =========================

OUTPUT_FILE = Path("punching_telemetry.csv")
OPERATORS_FILE = Path("operators.csv")

START_TIME = datetime(2025, 1, 1, 6, 0, 0)
END_TIME = datetime(2025, 5, 1, 0, 0, 0)

TIME_STEP_SECONDS = 10
WORK_STATION_ID = "PU_01"
NUM_CORES = 4

COLUMNS = [
    "telemetry_id",
    "timestamp",
    "work_station_id",
    "operator_id",
    "shift",
    "machine_status",
    "spindle_speed_rpm",
    "feed_rate_mm_min",
    "vibration_g",
    "temperature_c",
    "power_kw",
    "tool_wear_pct",
]

# =========================
# HELPERS
# =========================

def get_shift(ts):
    hour = ts.hour

    if 6 <= hour < 14:
        return "A"
    elif 14 <= hour < 22:
        return "B"
    else:
        return "C"


def get_shift_date(ts, shift):
    shift_date = ts.date()

    if shift == "C" and ts.hour < 6:
        shift_date = shift_date - timedelta(days=1)

    return shift_date


def get_operator_for_shift(punching_operators, shift, shift_date):
    eligible = punching_operators[punching_operators["shift"] == shift]

    if len(eligible) == 0:
        raise ValueError(f"No operators found for shift {shift}")

    rng = random.Random(f"{shift}_{shift_date}")

    return rng.choice(eligible["operator_id"].tolist())


def choose_next_status(tool_wear, rng):
    if tool_wear >= 90:
        weights = [65, 10, 5, 20]
    elif tool_wear >= 75:
        weights = [75, 10, 5, 10]
    else:
        weights = [82, 10, 5, 3]

    return rng.choices(
        ["RUNNING", "IDLE", "SETUP", "DOWN"],
        weights=weights,
        k=1
    )[0]


def get_status_duration_minutes(status, rng):
    if status == "RUNNING":
        return rng.randint(10, 120)
    elif status == "IDLE":
        return rng.randint(5, 30)
    elif status == "SETUP":
        return rng.randint(10, 45)
    else:
        return rng.randint(5, 60)


def sensor_values(status, temperature, tool_wear, rng):
    if status == "RUNNING":
        spindle_speed_rpm = round(rng.uniform(1800, 3200), 2)
        feed_rate_mm_min = round(rng.uniform(800, 2500), 2)
        vibration_g = round(
            rng.uniform(0.8, 2.5) + (tool_wear / 100) * 0.4,
            2
        )
        temperature += rng.uniform(0.00, 0.15)
        power_kw = round(rng.uniform(12, 25), 2)

    elif status == "IDLE":
        spindle_speed_rpm = round(rng.uniform(100, 500), 2)
        feed_rate_mm_min = round(rng.uniform(0, 50), 2)
        vibration_g = round(rng.uniform(0.1, 0.8), 2)
        temperature -= rng.uniform(0.00, 0.10)
        power_kw = round(rng.uniform(1, 5), 2)

    elif status == "SETUP":
        spindle_speed_rpm = round(rng.uniform(500, 1500), 2)
        feed_rate_mm_min = round(rng.uniform(100, 600), 2)
        vibration_g = round(rng.uniform(0.3, 1.5), 2)
        temperature += rng.uniform(-0.05, 0.08)
        power_kw = round(rng.uniform(4, 12), 2)

    else:
        spindle_speed_rpm = 0
        feed_rate_mm_min = 0
        vibration_g = round(rng.uniform(0, 0.3), 2)
        temperature -= rng.uniform(0.00, 0.12)
        power_kw = round(rng.uniform(0, 1), 2)

    temperature = round(max(20, min(60, temperature)), 2)

    return (
        spindle_speed_rpm,
        feed_rate_mm_min,
        vibration_g,
        temperature,
        power_kw,
    )


def generate_chunk(args):
    chunk_id, chunk_start, chunk_end, start_row_number = args

    rng = random.Random(42 + chunk_id)

    operators_df = pd.read_csv(OPERATORS_FILE)

    punching_operators = operators_df[
        operators_df["assigned_station_id"] == WORK_STATION_ID
    ].copy()

    if punching_operators.empty:
        raise ValueError(f"No operators found for station {WORK_STATION_ID}")

    temp_file = Path(f"punching_telemetry_part_{chunk_id}.csv")

    rows_written = 0
    current_time = chunk_start

    status = "SETUP"
    status_remaining_steps = (
        get_status_duration_minutes(status, rng)
        * 60
        // TIME_STEP_SECONDS
    )

    temperature = round(rng.uniform(25, 32), 2)
    tool_wear = round(rng.uniform(0, 5), 2)

    with temp_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        while current_time < chunk_end:
            shift = get_shift(current_time)
            shift_date = get_shift_date(current_time, shift)

            operator_id = get_operator_for_shift(
                punching_operators,
                shift,
                shift_date
            )

            if status_remaining_steps <= 0:
                previous_status = status
                status = choose_next_status(tool_wear, rng)

                if previous_status == "DOWN" and status == "RUNNING":
                    status = "SETUP"

                status_remaining_steps = (
                    get_status_duration_minutes(status, rng)
                    * 60
                    // TIME_STEP_SECONDS
                )

            (
                spindle_speed_rpm,
                feed_rate_mm_min,
                vibration_g,
                temperature,
                power_kw,
            ) = sensor_values(status, temperature, tool_wear, rng)

            if status == "RUNNING":
                tool_wear += rng.uniform(0.001, 0.01)
            elif status == "SETUP":
                tool_wear += rng.uniform(0.0002, 0.002)

            if status == "DOWN" and tool_wear >= 90:
                tool_wear = rng.uniform(0, 5)

            tool_wear = round(max(0, min(100, tool_wear)), 2)

            telemetry_id = f"PU_01_TEL_{start_row_number + rows_written:07d}"

            writer.writerow([
                telemetry_id,
                current_time.strftime("%Y-%m-%d %H:%M:%S"),
                WORK_STATION_ID,
                operator_id,
                shift,
                status,
                spindle_speed_rpm,
                feed_rate_mm_min,
                vibration_g,
                temperature,
                power_kw,
                tool_wear,
            ])

            rows_written += 1
            status_remaining_steps -= 1
            current_time += timedelta(seconds=TIME_STEP_SECONDS)

    return temp_file, rows_written


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    total_seconds = int((END_TIME - START_TIME).total_seconds())
    total_steps = total_seconds // TIME_STEP_SECONDS
    steps_per_chunk = total_steps // NUM_CORES

    chunks = []

    for i in range(NUM_CORES):
        chunk_start_step = i * steps_per_chunk

        if i == NUM_CORES - 1:
            chunk_end_step = total_steps
        else:
            chunk_end_step = (i + 1) * steps_per_chunk

        chunk_start = START_TIME + timedelta(
            seconds=chunk_start_step * TIME_STEP_SECONDS
        )

        chunk_end = START_TIME + timedelta(
            seconds=chunk_end_step * TIME_STEP_SECONDS
        )

        start_row_number = chunk_start_step + 1

        chunks.append(
            (i + 1, chunk_start, chunk_end, start_row_number)
        )

    with mp.Pool(processes=NUM_CORES) as pool:
        results = pool.map(generate_chunk, chunks)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as final_file:
        writer = csv.writer(final_file)
        writer.writerow(COLUMNS)

        for temp_file, _ in sorted(results):
            with temp_file.open("r", newline="", encoding="utf-8") as part_file:
                reader = csv.reader(part_file)
                writer.writerows(reader)

            temp_file.unlink()

    total_rows = sum(row_count for _, row_count in results)

    print(f"Created {OUTPUT_FILE}")
    print(f"Rows written: {total_rows}")
    print(f"Cores used: {NUM_CORES}")