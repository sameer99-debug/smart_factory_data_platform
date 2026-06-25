from faker import Faker
import pandas as pd
import random
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)
Faker.seed(42)

NUM_ROWS = 100_000
BAD_DATA_RATE = 0.03

OPERATORS_FILE = "operators.csv"
SHIFTS_FILE = "shifts.csv"
BREAKS_FILE = "breaks.csv"

START_DATE = datetime(2025, 1, 1).date()
END_DATE = datetime(2025, 4, 30).date()

products = ["PD_01", "PD_02", "PD_03", "PD_04", "PD_05", "PD_06", "PD_07"]
workstations = ["PU_01", "BE_01", "WL_01", "AM_01", "PC_01", "PK_01"]

scrap_rates = {
    "PD_01": 0.03,
    "PD_02": 0.06,
    "PD_03": 0.06,
    "PD_04": 0.05,
    "PD_05": 0.04,
    "PD_06": 0.06,
    "PD_07": 0.03
}

operators_df = pd.read_csv(OPERATORS_FILE)
shifts_df = pd.read_csv(SHIFTS_FILE)
breaks_df = pd.read_csv(BREAKS_FILE)

shifts = shifts_df["shift"].tolist()

operator_map = (
    operators_df
    .groupby(["assigned_station_id", "shift"])["operator_id"]
    .apply(list)
    .to_dict()
)


def parse_time(value):
    return datetime.strptime(str(value), "%H:%M").time()


shift_map = {}
for _, row in shifts_df.iterrows():
    shift_map[row["shift"]] = {
        "start": parse_time(row["start_time"]),
        "end": parse_time(row["end_time"])
    }

break_map = {}
for _, row in breaks_df.iterrows():
    break_map[row["shift"]] = {
        "start": parse_time(row["break_start"]),
        "end": parse_time(row["break_end"])
    }


def get_valid_operator(work_station_id, shift):
    valid_ops = operator_map.get((work_station_id, shift), [])
    if not valid_ops:
        return None
    return random.choice(valid_ops)


def get_shift_window(work_date, shift):
    shift_start_time = shift_map[shift]["start"]
    shift_end_time = shift_map[shift]["end"]

    shift_start = datetime.combine(work_date, shift_start_time)
    shift_end = datetime.combine(work_date, shift_end_time)

    if shift_end <= shift_start:
        shift_end += timedelta(days=1)

    return shift_start, shift_end


def get_break_window(work_date, shift, shift_start):
    if shift not in break_map:
        return None, None

    break_start_time = break_map[shift]["start"]
    break_end_time = break_map[shift]["end"]

    break_start = datetime.combine(work_date, break_start_time)
    break_end = datetime.combine(work_date, break_end_time)

    if break_start < shift_start:
        break_start += timedelta(days=1)

    if break_end <= break_start:
        break_end += timedelta(days=1)

    return break_start, break_end


def generate_order_times(shift):
    work_date = fake.date_between(
        start_date=START_DATE,
        end_date=END_DATE
    )

    shift_start, shift_end = get_shift_window(work_date, shift)
    break_start, break_end = get_break_window(work_date, shift, shift_start)

    intervals = []

    if break_start and break_end:
        intervals.append((shift_start, break_start))
        intervals.append((break_end, shift_end))
    else:
        intervals.append((shift_start, shift_end))

    valid_intervals = [
        (s, e) for s, e in intervals
        if (e - s).total_seconds() >= 5 * 60
    ]

    interval_start, interval_end = random.choice(valid_intervals)

    duration_minutes = random.randint(2, 20)

    latest_start = interval_end - timedelta(minutes=duration_minutes)

    random_seconds = random.randint(
        0,
        int((latest_start - interval_start).total_seconds())
    )

    start_time = interval_start + timedelta(seconds=random_seconds)
    end_time = start_time + timedelta(minutes=duration_minutes)

    return start_time, end_time


def inject_bad_data(row, rows):
    bad_type = random.choice([
        "nulls",
        "duplicates",
        "wrong_workstation",
        "wrong_operator",
        "wrong_shift",
        "negative_qty",
        "actual_gt_planned",
        "scrap_gt_actual",
        "outlier",
        "null_timestamp",
        "end_before_start",
        "extreme_duration"
    ])

    if bad_type == "nulls":
        row[random.choice(["product_id", "work_station_id", "operator_id", "shift"])] = None

    elif bad_type == "duplicates":
        if rows:
            row = random.choice(rows).copy()

    elif bad_type == "wrong_workstation":
        row["work_station_id"] = random.choice(["UNKNOWN", "BAD_01", "INVALID", "123XYZ"])

    elif bad_type == "wrong_operator":
        row["operator_id"] = random.choice(["EMP_999", "BAD_OPERATOR", "UNKNOWN", "123XYZ"])

    elif bad_type == "wrong_shift":
        row["shift"] = random.choice(["X", "Y", "Z"])

    elif bad_type == "negative_qty":
        row[random.choice(["planned_qty", "actual_qty", "scrap_qty"])] = random.randint(-50, -1)

    elif bad_type == "actual_gt_planned":
        row["actual_qty"] = row["planned_qty"] + random.randint(1, 50)

    elif bad_type == "scrap_gt_actual":
        row["scrap_qty"] = row["actual_qty"] + random.randint(1, 50)

    elif bad_type == "outlier":
        row["planned_qty"] = random.randint(5000, 20000)
        row["actual_qty"] = row["planned_qty"]
        row["scrap_qty"] = random.randint(0, 500)

    elif bad_type == "null_timestamp":
        row[random.choice(["start_time", "end_time"])] = None

    elif bad_type == "end_before_start":
        row["end_time"] = row["start_time"] - timedelta(minutes=random.randint(1, 120))

    elif bad_type == "extreme_duration":
        row["end_time"] = row["start_time"] + timedelta(days=random.randint(30, 365))

    return row


rows = []

for i in range(1, NUM_ROWS + 1):
    product_id = random.choice(products)
    work_station_id = random.choice(workstations)
    shift = random.choice(shifts)

    planned_qty = random.randint(5, 40)

    scrap_qty = max(
        0,
        round(random.normalvariate(planned_qty * scrap_rates[product_id], 2))
    )

    actual_qty = planned_qty - scrap_qty

    start_time, end_time = generate_order_times(shift)

    row = {
        "order_id": f"ORD_{i:06}",
        "product_id": product_id,
        "work_station_id": work_station_id,
        "operator_id": get_valid_operator(work_station_id, shift),
        "planned_qty": planned_qty,
        "actual_qty": actual_qty,
        "scrap_qty": scrap_qty,
        "shift": shift,
        "start_time": start_time,
        "end_time": end_time
    }

    if random.random() < BAD_DATA_RATE:
        row = inject_bad_data(row, rows)

    rows.append(row)


df = pd.DataFrame(rows)

df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")

df["start_time"] = df["start_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
df["end_time"] = df["end_time"].dt.strftime("%Y-%m-%d %H:%M:%S")

if "bad_data_type" in df.columns:
    df = df.drop(columns=["bad_data_type"])

df.to_csv("production_orders.csv", index=False)

print(df.head())
print("\nRows Generated:", len(df))
print("\nCSV Saved: production_orders.csv")