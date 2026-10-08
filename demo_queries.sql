-- 1. Confirm which SQLite file is open.
PRAGMA database_list;

-- 2. Show the latest live session and its actual state.
SELECT id,dataset_id,created,state,mode,last_error
FROM live_sessions ORDER BY created DESC LIMIT 1;

-- 3. Count past baseline and accumulated current readings.
SELECT period,COUNT(*) AS number_of_readings,
 MIN(timestamp) AS first_reading,MAX(timestamp) AS newest_reading
FROM readings
WHERE dataset_id=(SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1)
GROUP BY period;

-- 4. Display the newest actual measured timings.
SELECT id,timestamp,period,duration_ms,error_count
FROM reading_values
WHERE dataset_id=(SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1)
ORDER BY timestamp DESC LIMIT 15;

-- 5. Inspect supporting execution events.
SELECT id,json_extract(payload,'$.timestamp') AS timestamp,
 json_extract(payload,'$.category') AS category,
 json_extract(payload,'$.message') AS message
FROM events
WHERE dataset_id=(SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1)
ORDER BY rowid DESC LIMIT 15;

-- 6. Show model results over time (normal -> anomaly -> recovery).
SELECT created,status,
 json_extract(result,'$.flagged_count') AS flagged,
 json_extract(result,'$.current_count') AS window_rows,
 json_extract(result,'$.ml_flagged_count') AS ml_flags,
 json_extract(result,'$.statistical_flagged_count') AS statistical_flags
FROM investigations
WHERE dataset_id=(SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1)
ORDER BY created DESC LIMIT 20;
