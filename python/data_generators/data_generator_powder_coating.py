import csv
import random
import multiprocessing as mp
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# =========================
# CONFIG
# =========================

OUTPUT_FILE = Path("powder_coating_telemetry.csv")
OPERATORS_FILE = Path("operators.csv")

START_TIME = datetime(2025, 1, 1, 6, 0, 0)
END_TIME = datetime(2025, 5, 1, 0, 0, 0)

TIME_STEP_SECONDS = 10
WORK_STATION_ID = "PC_01"
NUM_CORES = 4

COLUMNS = [
    "telemetry_id",
    "timestamp",
    "work_station_id",
    "operator_id",
    "shift",
    "machine_status",
    "oven_temperature_c",
    "conveyor_speed_m_min",
    "powder_flow_g_min",
    "air_pressure_bar",
    "humidity_pct",
    "power_kw",
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


def get_operator_for_shift(powder_operators, shift, shift_date):
    eligible = powder_operators[powder_operators["shift"] == shift]

    if len(eligible) == 0:
        raise ValueError(f"No operators found for shift {shift}")

    rng = random.Random(f"{shift}_{shift_date}")
    return rng.choice(eligible["operator_id"].tolist())


def choose_next_status(machine_wear, rng):
    if machine_wear >= 90:
        weights = [65, 10, 5, 20]
    elif machine_wear >= 75:
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


def sensor_values(status, oven_temperature, humidity, machine_wear, rng):
    if status == "RUNNING":
        oven_temperature += rng.uniform(0.00, 0.20)
        conveyor_speed_m_min = round(rng.uniform(1.5, 4.5), 2)
        powder_flow_g_min = round(rng.uniform(120, 420), 2)
        air_pressure_bar = round(rng.uniform(4.5, 7.5), 2)
        humidity += rng.uniform(-0.05, 0.05)
        power_kw = round(rng.uniform(18, 45), 2)

        if machine_wear > 75:
            powder_flow_g_min = round(powder_flow_g_min * rng.uniform(0.85, 0.98), 2)
            air_pressure_bar = round(air_pressure_bar * rng.uniform(0.90, 0.98), 2)
            power_kw = round(power_kw * rng.uniform(1.02, 1.12), 2)

    elif status == "IDLE":
        oven_temperature -= rng.uniform(0.00, 0.10)
        conveyor_speed_m_min = 0
        powder_flow_g_min = 0
        air_pressure_bar = round(rng.uniform(2.0, 4.0), 2)
        humidity += rng.uniform(-0.03, 0.08)
        power_kw = round(rng.uniform(3, 8), 2)

    elif status == "SETUP":
        oven_temperature += rng.uniform(-0.05, 0.12)
        conveyor_speed_m_min = round(rng.uniform(0.5, 1.8), 2)
        powder_flow_g_min = round(rng.uniform(20, 120), 2)
        air_pressure_bar = round(rng.uniform(3.5, 5.5), 2)
        humidity += rng.uniform(-0.05, 0.05)
        power_kw = round(rng.uniform(8, 18), 2)

    else:
        oven_temperature -= rng.uniform(0.05, 0.25)
        conveyor_speed_m_min = 0
        powder_flow_g_min = 0
        air_pressure_bar = 0
        humidity += rng.uniform(-0.02, 0.10)
        power_kw = round(rng.uniform(0, 2), 2)

    oven_temperature = round(max(25, min(230, oven_temperature)), 2)
    humidity = round(max(20, min(75, humidity)), 2)

    return (
        oven_temperature,
        conveyor_speed_m_min,
        powder_flow_g_min,
        air_pressure_bar,
        humidity,
        power_kw,
    )


def generate_chunk(args):
    chunk_id, chunk_start, chunk_end, start_row_number = args

    rng = random.Random(42 + chunk_id)

    operators_df = pd.read_csv(OPERATORS_FILE)

    powder_operators = operators_df[
        operators_df["assigned_station_id"] == WORK_STATION_ID
    ].copy()

    if powder_operators.empty:
        raise ValueError(f"No operators found for station {WORK_STATION_ID}")

    temp_file = Path(f"powder_coating_telemetry_part_{chunk_id}.csv")

    rows_written = 0
    current_time = chunk_start

    status = "SETUP"
    status_remaining_steps = (
        get_status_duration_minutes(status, rng)
        * 60
        // TIME_STEP_SECONDS
    )

    oven_temperature = round(rng.uniform(150, 180), 2)
    humidity = round(rng.uniform(35, 50), 2)
    machine_wear = round(rng.uniform(0, 5), 2)

    with temp_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        while current_time < chunk_end:
            shift = get_shift(current_time)
            shift_date = get_shift_date(current_time, shift)

            operator_id = get_operator_for_shift(
                powder_operators,
                shift,
                shift_date
            )

            if status_remaining_steps <= 0:
                previous_status = status
                status = choose_next_status(machine_wear, rng)

                if previous_status == "DOWN" and status == "RUNNING":
                    status = "SETUP"

                status_remaining_steps = (
                    get_status_duration_minutes(status, rng)
                    * 60
                    // TIME_STEP_SECONDS
                )

            (
                oven_temperature,
                conveyor_speed_m_min,
                powder_flow_g_min,
                air_pressure_bar,
                humidity,
                power_kw,
            ) = sensor_values(status, oven_temperature, humidity, machine_wear, rng)

            if status == "RUNNING":
                machine_wear += rng.uniform(0.001, 0.006)
            elif status == "SETUP":
                machine_wear += rng.uniform(0.0002, 0.002)

            if status == "DOWN" and machine_wear >= 90:
                machine_wear = rng.uniform(0, 5)

            machine_wear = round(max(0, min(100, machine_wear)), 2)

            telemetry_id = f"PC_01_TEL_{start_row_number + rows_written:07d}"

            writer.writerow([
                telemetry_id,
                current_time.strftime("%Y-%m-%d %H:%M:%S"),
                WORK_STATION_ID,
                operator_id,
                shift,
                status,
                oven_temperature,
                conveyor_speed_m_min,
                powder_flow_g_min,
                air_pressure_bar,
                humidity,
                power_kw,
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

        chunk_start = START_TIME + timedelta(seconds=chunk_start_step * TIME_STEP_SECONDS)
        chunk_end = START_TIME + timedelta(seconds=chunk_end_step * TIME_STEP_SECONDS)

        start_row_number = chunk_start_step + 1

        chunks.append((i + 1, chunk_start, chunk_end, start_row_number))

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