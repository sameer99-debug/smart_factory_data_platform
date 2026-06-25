from concurrent.futures import ThreadPoolExecutor
import psycopg2

ranges = [
    ("2025-01-01", "2025-02-01"),
    ("2025-02-01", "2025-03-01"),
    ("2025-03-01", "2025-04-01"),
    ("2025-04-01", "2025-05-01"),
]

def load_range(start, end):
    conn = psycopg2.connect(
        host="localhost",
        database="smart_factory",
        user="postgres",
        password="poiu1999"
    )
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO
            CLEAN.POWDER_COATING_TELEMETRY (
                TELEMETRY_ID,
                TIMESTAMP,
                WORK_STATION_ID,
                OPERATOR_ID,
                SHIFT,
                MACHINE_STATUS,
                OVEN_TEMPERATURE_C,
                CONVEYOR_SPEED_M_MIN,
                POWDER_FLOW_G_MIN,
                AIR_PRESSURE_BAR,
                HUMIDITY_PCT,
                POWER_KW
            )
        WITH
            TYPED AS (
                SELECT
                    TELEMETRY_ID,
                    TIMESTAMP::TIMESTAMP AS TIMESTAMP,
                    WORK_STATION_ID,
                    OPERATOR_ID,
                    SHIFT,
                    MACHINE_STATUS,
                    OVEN_TEMPERATURE_C::NUMERIC AS OVEN_TEMPERATURE_C,
                    CONVEYOR_SPEED_M_MIN::NUMERIC AS CONVEYOR_SPEED_M_MIN,
                    POWDER_FLOW_G_MIN::NUMERIC AS POWDER_FLOW_G_MIN,
                    AIR_PRESSURE_BAR::NUMERIC AS AIR_PRESSURE_BAR,
                    HUMIDITY_PCT::NUMERIC AS HUMIDITY_PCT,
                    POWER_KW::NUMERIC AS POWER_KW
                FROM
                    STAGE.POWDER_COATING_TELEMETRY
                WHERE
                    TELEMETRY_ID IS NOT NULL
                    AND TIMESTAMP ~ '^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]) ([01]\d|2[0-3]):[0-5]\d:[0-5]\d$'
                    AND TIMESTAMP::TIMESTAMP >= %s
                    AND TIMESTAMP::TIMESTAMP < %s
            ),
            VALIDATED AS (
                SELECT
                    T.*
                FROM
                    TYPED T
                    JOIN CLEAN.WORK_STATIONS W ON W.WORK_STATION_ID = T.WORK_STATION_ID
                    JOIN CLEAN.OPERATORS O ON O.OPERATOR_ID = T.OPERATOR_ID
                    JOIN CLEAN.SHIFTS S ON S.SHIFT = T.SHIFT
                    JOIN CLEAN.MACHINE_STATES M ON M.STATUS = T.MACHINE_STATUS
                WHERE
                    T.OVEN_TEMPERATURE_C BETWEEN 0 AND 999.99
                    AND T.CONVEYOR_SPEED_M_MIN BETWEEN 0 AND 9.99
                    AND T.POWDER_FLOW_G_MIN BETWEEN 0 AND 999.99
                    AND T.AIR_PRESSURE_BAR BETWEEN 0 AND 9.99
                    AND T.HUMIDITY_PCT BETWEEN 0 AND 99.99
                    AND T.POWER_KW BETWEEN 0 AND 99.99
            ),
            DEDUPED AS (
                SELECT
                    *
                FROM
                    (
                        SELECT
                            *,
                            ROW_NUMBER() OVER (
                                PARTITION BY
                                    TIMESTAMP
                                ORDER BY
                                    TELEMETRY_ID
                            ) AS RN
                        FROM
                            VALIDATED
                    ) X
                WHERE
                    RN = 1
            )
        SELECT
            TELEMETRY_ID,
            TIMESTAMP,
            WORK_STATION_ID,
            OPERATOR_ID,
            SHIFT::CHAR(1),
            MACHINE_STATUS,
            OVEN_TEMPERATURE_C::NUMERIC(5, 2),
            CONVEYOR_SPEED_M_MIN::NUMERIC(3, 2),
            POWDER_FLOW_G_MIN::NUMERIC(5, 2),
            AIR_PRESSURE_BAR::NUMERIC(3, 2),
            HUMIDITY_PCT::NUMERIC(4, 2),
            POWER_KW::NUMERIC(4, 2)
        FROM
            DEDUPED
        ON CONFLICT (TIMESTAMP) DO NOTHING;
    """, (start, end))

    conn.commit()
    cur.close()
    conn.close()

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(lambda r: load_range(*r), ranges)