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
            CLEAN.PUNCHING_TELEMETRY (
                TELEMETRY_ID,
                TIMESTAMP,
                WORK_STATION_ID,
                OPERATOR_ID,
                SHIFT,
                MACHINE_STATUS,
                SPINDLE_SPEED_RPM,
                FEED_RATE_MM_MIN,
                VIBRATION_G,
                TEMPERATURE_C,
                POWER_KW,
                TOOL_WEAR_PCT
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
                    SPINDLE_SPEED_RPM::NUMERIC AS SPINDLE_SPEED_RPM,
                    FEED_RATE_MM_MIN::NUMERIC AS FEED_RATE_MM_MIN,
                    VIBRATION_G::NUMERIC AS VIBRATION_G,
                    TEMPERATURE_C::NUMERIC AS TEMPERATURE_C,
                    POWER_KW::NUMERIC AS POWER_KW,
                    TOOL_WEAR_PCT::NUMERIC AS TOOL_WEAR_PCT
                FROM
                    STAGE.PUNCHING_TELEMETRY
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
                    T.SPINDLE_SPEED_RPM BETWEEN 0 AND 9999.99
                    AND T.FEED_RATE_MM_MIN BETWEEN 0 AND 9999.99
                    AND T.VIBRATION_G BETWEEN 0 AND 9.99
                    AND T.TEMPERATURE_C BETWEEN 0 AND 99.99
                    AND T.POWER_KW BETWEEN 0 AND 99.99
                    AND T.TOOL_WEAR_PCT BETWEEN 0 AND 99.99
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
            SPINDLE_SPEED_RPM::NUMERIC(6, 2),
            FEED_RATE_MM_MIN::NUMERIC(6, 2),
            VIBRATION_G::NUMERIC(3, 2),
            TEMPERATURE_C::NUMERIC(4, 2),
            POWER_KW::NUMERIC(4, 2),
            TOOL_WEAR_PCT::NUMERIC(4, 2)
        FROM
            DEDUPED
        ON CONFLICT (TIMESTAMP) DO NOTHING;
    """, (start, end))

    conn.commit()
    cur.close()
    conn.close()

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(lambda r: load_range(*r), ranges)