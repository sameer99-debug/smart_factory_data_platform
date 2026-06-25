import csv
import random
import multiprocessing as mp
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# =========================
# CONFIG
# =========================

OUTPUT_FILE = Path("welding_telemetry.csv")
OPERATORS_FILE = Path("operators.csv")

START_TIME = datetime(2025, 1, 1, 6, 0, 0)
END_TIME = datetime(2025, 5, 1, 0, 0, 0)

TIME_STEP_SECONDS = 10
WORK_STATION_ID = "WL_01"
NUM_CORES = 4

COLUMNS = [
    "telemetry_id",
    "timestamp",
    "work_station_id",
    "operator_id",
    "shift",
    "machine_status",
    "welding_current_amp",
    "welding_voltage_v",
    "gas_flow_l_min",
    "wire_feed_speed_m_min",
    "temperature_c",
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


def get_operator_for_shift(welding_operators, shift, shift_date):
    eligible = welding_operators[welding_operators["shift"] == shift]

    if len(eligible) == 0:
        raise ValueError(f"No operators found for shift {shift}")

    rng = random.Random(f"{shift}_{shift_date}")
    return rng.choice(eligible["operator_id"].tolist())


def choose_next_status(torch_wear, rng):
    if torch_wear >= 90:
        weights = [65, 10, 5, 20]
    elif torch_wear >= 75:
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


def sensor_values(status, temperature, torch_wear, rng):
    if status == "RUNNING":
        welding_current_amp = round(rng.uniform(120, 260), 2)
        welding_voltage_v = round(rng.uniform(18, 32), 2)
        gas_flow_l_min = round(rng.uniform(12, 28), 2)
        wire_feed_speed_m_min = round(rng.uniform(2, 9), 2)
        temperature += rng.uniform(0.05, 0.35)
        power_kw = round(rng.uniform(6, 18), 2)

        if torch_wear > 75:
            welding_current_amp += round(rng.uniform(-15, 20), 2)
            gas_flow_l_min += round(rng.uniform(0, 4), 2)

    elif status == "IDLE":
        welding_current_amp = 0
        welding_voltage_v = round(rng.uniform(0, 5), 2)
        gas_flow_l_min = round(rng.uniform(0, 3), 2)
        wire_feed_speed_m_min = 0
        temperature -= rng.uniform(0.02, 0.20)
        power_kw = round(rng.uniform(1, 4), 2)

    elif status == "SETUP":
        welding_current_amp = round(rng.uniform(20, 80), 2)
        welding_voltage_v = round(rng.uniform(8, 18), 2)
        gas_flow_l_min = round(rng.uniform(5, 15), 2)
        wire_feed_speed_m_min = round(rng.uniform(0.5, 2.5), 2)
        temperature += rng.uniform(-0.05, 0.15)
        power_kw = round(rng.uniform(3, 8), 2)

    else:
        welding_current_amp = 0
        welding_voltage_v = 0
        gas_flow_l_min = 0
        wire_feed_speed_m_min = 0
        temperature -= rng.uniform(0.05, 0.25)
        power_kw = round(rng.uniform(0, 1), 2)

    temperature = round(max(25, min(180, temperature)), 2)

    return (
        welding_current_amp,
        welding_voltage_v,
        gas_flow_l_min,
        wire_feed_speed_m_min,
        temperature,
        power_kw,
    )


def generate_chunk(args):
    chunk_id, chunk_start, chunk_end, start_row_number = args

    rng = random.Random(42 + chunk_id)

    operators_df = pd.read_csv(OPERATORS_FILE)

    welding_operators = operators_df[
        operators_df["assigned_station_id"] == WORK_STATION_ID
    ].copy()

    if welding_operators.empty:
        raise ValueError(f"No operators found for station {WORK_STATION_ID}")

    temp_file = Path(f"welding_telemetry_part_{chunk_id}.csv")

    rows_written = 0
    current_time = chunk_start

    status = "SETUP"
    status_remaining_steps = (
        get_status_duration_minutes(status, rng)
        * 60
        // TIME_STEP_SECONDS
    )

    temperature = round(rng.uniform(35, 60), 2)
    torch_wear = round(rng.uniform(0, 5), 2)

    with temp_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        while current_time < chunk_end:
            shift = get_shift(current_time)
            shift_date = get_shift_date(current_time, shift)

            operator_id = get_operator_for_shift(
                welding_operators,
                shift,
                shift_date
            )

            if status_remaining_steps <= 0:
                previous_status = status
                status = choose_next_status(torch_wear, rng)

                if previous_status == "DOWN" and status == "RUNNING":
                    status = "SETUP"

                status_remaining_steps = (
                    get_status_duration_minutes(status, rng)
                    * 60
                    // TIME_STEP_SECONDS
                )

            (
                welding_current_amp,
                welding_voltage_v,
                gas_flow_l_min,
                wire_feed_speed_m_min,
                temperature,
                power_kw,
            ) = sensor_values(status, temperature, torch_wear, rng)

            if status == "RUNNING":
                torch_wear += rng.uniform(0.001, 0.009)
            elif status == "SETUP":
                torch_wear += rng.uniform(0.0002, 0.002)

            if status == "DOWN" and torch_wear >= 90:
                torch_wear = rng.uniform(0, 5)

            torch_wear = round(max(0, min(100, torch_wear)), 2)

            telemetry_id = f"WL_01_TEL_{start_row_number + rows_written:07d}"

            writer.writerow([
                telemetry_id,
                current_time.strftime("%Y-%m-%d %H:%M:%S"),
                WORK_STATION_ID,
                operator_id,
                shift,
                status,
                welding_current_amp,
                welding_voltage_v,
                gas_flow_l_min,
                wire_feed_speed_m_min,
                temperature,
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

        chunk_start = START_TIME + timedelta(
            seconds=chunk_start_step * TIME_STEP_SECONDS
        )

        chunk_end = START_TIME + timedelta(
            seconds=chunk_end_step * TIME_STEP_SECONDS
        )

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