import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# =========================
# CONFIG
# =========================

OUTPUT_FILE = Path("maintenance_events.csv")
OPERATORS_FILE = Path("operators.csv")

NUM_ROWS = 50_000
BAD_DATA_RATE = 0.03

START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2026, 1, 1)

SHIFT_WINDOWS = {
    "A": (6, 14),
    "B": (14, 22),
    "C": (22, 6),
}

MAINTENANCE_TYPES = [
    "Preventive",
    "Corrective",
    "Inspection",
    "Emergency",
]

DOWNTIME_REASONS_BY_STATION = {
    "PU_01": [
        "Punch tool wear",
        "Sheet misfeed",
        "Clamp fault",
        "CNC alarm",
        "Lubrication issue",
    ],
    "BE_01": [
        "Back gauge fault",
        "Hydraulic pressure issue",
        "Bend angle correction",
        "Tool alignment issue",
        "Safety sensor fault",
    ],
    "WL_01": [
        "Welding torch issue",
        "Wire feed jam",
        "Gas flow issue",
        "Welding current instability",
        "Cooling fault",
    ],
    "AM_01": [
        "Assembly jig issue",
        "Fastener shortage",
        "Fixture alignment issue",
        "Manual tool failure",
        "Quality rework",
    ],
    "PC_01": [
        "Oven temperature issue",
        "Powder gun blockage",
        "Conveyor fault",
        "Air pressure issue",
        "Pre-treatment issue",
    ],
    "PK_01": [
        "Barcode scanner issue",
        "Label printer fault",
        "Packaging conveyor fault",
        "Wrapping material jam",
        "Palletizing delay",
    ],
}


# =========================
# LOAD OPERATORS
# =========================

def load_operators(path: Path) -> list[dict]:
    operators = []

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            operators.append({
                "operator_id": row["operator_id"],
                "work_station_id": row["assigned_station_id"],
                "shift": row["shift"],
            })

    return operators


# =========================
# TIME HELPERS
# =========================

def random_date() -> datetime:
    days = (END_DATE - START_DATE).days
    return START_DATE + timedelta(days=random.randint(0, days - 1))


def get_shift_window(base_date: datetime, shift: str):
    start_hour, end_hour = SHIFT_WINDOWS[shift]

    shift_start = base_date.replace(
        hour=start_hour,
        minute=0,
        second=0,
        microsecond=0
    )

    if shift == "C":
        shift_end = shift_start + timedelta(hours=8)
    else:
        shift_end = base_date.replace(
            hour=end_hour,
            minute=0,
            second=0,
            microsecond=0
        )

    return shift_start, shift_end


def random_downtime_minutes() -> int:
    """
    Very low realistic downtime:
    70% -> 2 to 10 minutes
    20% -> 11 to 20 minutes
    8%  -> 21 to 45 minutes
    2%  -> 46 to 90 minutes
    """

    bucket = random.choices(
        population=["tiny", "small", "medium", "long"],
        weights=[70, 20, 8, 2],
        k=1
    )[0]

    if bucket == "tiny":
        return random.randint(2, 10)

    elif bucket == "small":
        return random.randint(11, 20)

    elif bucket == "medium":
        return random.randint(21, 45)

    else:
        return random.randint(46, 90)


def random_event_time_for_shift(shift: str):
    base_date = random_date()
    shift_start, shift_end = get_shift_window(base_date, shift)

    downtime_min = random_downtime_minutes()

    latest_start = shift_end - timedelta(minutes=downtime_min)

    seconds_range = int((latest_start - shift_start).total_seconds())

    start_time = shift_start + timedelta(
        seconds=random.randint(0, seconds_range)
    )

    end_time = start_time + timedelta(minutes=downtime_min)

    return start_time, end_time, downtime_min


# =========================
# GENERATE ROWS
# =========================

def make_good_event(event_num: int, operators: list[dict]) -> dict:
    operator = random.choice(operators)

    operator_id = operator["operator_id"]
    work_station_id = operator["work_station_id"]
    shift = operator["shift"]

    start_time, end_time, downtime_min = random_event_time_for_shift(shift)

    downtime_reason = random.choice(
        DOWNTIME_REASONS_BY_STATION.get(
            work_station_id,
            ["General maintenance"]
        )
    )

    maintenance_type = random.choice(MAINTENANCE_TYPES)

    return {
        "maintenance_id": f"MT_{event_num:06d}",
        "work_station_id": work_station_id,
        "operator_id": operator_id,
        "maintenance_type": maintenance_type,
        "downtime_reason": downtime_reason,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "downtime_min": downtime_min,
    }


def corrupt_event(row: dict) -> dict:
    row = row.copy()

    bad_type = random.choice([
        "bad_workstation",
        "bad_operator",
        "wrong_reason_for_station",
        "corrupted_timestamp",
        "end_before_start",
        "negative_downtime",
        "extreme_downtime",
        "null_value",
        "duplicate_style_id",
    ])

    if bad_type == "bad_workstation":
        row["work_station_id"] = "123XYZ"

    elif bad_type == "bad_operator":
        row["operator_id"] = "OP_999"

    elif bad_type == "corrupted_timestamp":
        row["start_time"] = "bad_timestamp"

    elif bad_type == "end_before_start":
        row["end_time"] = "2024-01-01 00:00:00"

    elif bad_type == "negative_downtime":
        row["downtime_min"] = -random.randint(1, 60)

    elif bad_type == "extreme_downtime":
        row["downtime_min"] = random.randint(300, 900)

    elif bad_type == "null_value":
        row[random.choice([
            "work_station_id",
            "operator_id",
            "maintenance_type",
            "downtime_reason",
            "start_time",
            "downtime_min",
        ])] = ""

    elif bad_type == "duplicate_style_id":
        row["maintenance_id"] = f"MT_{random.randint(1, 100):06d}"

    return row


# =========================
# MAIN
# =========================

def generate():
    operators = load_operators(OPERATORS_FILE)

    fieldnames = [
        "maintenance_id",
        "work_station_id",
        "operator_id",
        "maintenance_type",
        "downtime_reason",
        "start_time",
        "end_time",
        "downtime_min",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i in range(1, NUM_ROWS + 1):
            row = make_good_event(i, operators)

            if random.random() < BAD_DATA_RATE:
                row = corrupt_event(row)

            writer.writerow(row)

    print(f"Generated {NUM_ROWS:,} maintenance events into {OUTPUT_FILE}")


if __name__ == "__main__":
    generate()