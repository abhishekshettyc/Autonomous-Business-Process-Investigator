# RootLens 2.1 — live demo, database setup and panel script

## What changed

The earlier version investigated uploaded snapshots. This version adds a continuously running, instrumented local software workload, automatic SQL writes, automatic investigation, fault controls, recovery, and a database explorer. It preserves the previous import/scenario/history features.

**Truthful description:** This is live measurement of a controlled local software test, not an external machine or a production data feed. The elapsed times are actually measured now; they are not loaded from a prerecorded fault dataset. Delays and timeouts are deliberately injected so the panel can see detection and recovery. Built-in older scenarios are still synthetic.

The pipeline is:

Local software operation → actual duration/error measurement → SQLite commit → read baseline + last 10 current rows from SQLite → ML/statistical detection → evidence comparison → save report → website polls every two seconds.

The detector never reads the fault-control mode or the live_actions table. It reads measurements and execution events. Execution events describe what the worker actually executed, including deliberate test-fault stages.

## 1. Get the upgraded project running

1. Download the updated ZIP and extract it to a new folder, such as `C:\RootLens-Live`. Do not run it inside the ZIP.
2. Close the old app terminal with Ctrl+C so port 8000 is free.
3. Inside the extracted `rootlens-v2` folder, double-click `START_WINDOWS.bat`.
4. Wait for dependency installation and the Uvicorn startup message. Python 3.11 or 3.12 is recommended. Internet is needed for initial installation; no API key is needed.
5. Open http://127.0.0.1:8000. Hard-refresh with Ctrl+F5 if old assets are cached.
6. Confirm you see **Live demo** and **Database** in the left navigation and version 2.1.

The folder name remains `rootlens-v2` for continuity; the application version is 2.1.

Manual alternative from PowerShell in that folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If `py` is unavailable, use `python` for venv creation. On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, then `.venv/bin/python app.py`.

No MySQL, MongoDB, XAMPP or separate database server is required. Use a local folder rather than a network/synced drive for the demo. Run one backend process only; do not start multiple workers or a second app against the same live database.

## 2. Database setup — automatic

At startup the app creates:

`rootlens-v2/storage/rootlens.db`

It creates the tables, indexes and view automatically. You do not need to run CREATE TABLE or insert sample history manually.

SQLite is a real SQL database embedded in the app. It has no separate hostname, username, password or TCP port. **localhost:8000 is the website/backend address, not a database server port.** The Database page displays the exact absolute file path used by your running app.

Existing tables:
- datasets: source, asset, metric definitions and hypothesis configuration.
- readings: historical/current measurement rows.
- events: timestamped execution evidence.
- investigations: saved model results and ranked hypotheses.

New tables/view:
- live_sessions: session state and linked dataset.
- live_actions: an audit of user-selected test modes; not used by detection.
- reading_values: a SQL view showing duration_ms and error_count as convenient columns.

SQLite WAL mode lets the app write measurements while the website/console reads them. Do not edit or delete database/WAL files during the demo.

To keep an earlier database: stop the old app first, back up its storage folder, then copy the stopped app's storage folder into the upgraded folder. Startup creates the new tables without dropping old data. This is optional; a clean live demo works without the old database. Do not copy only the .db file while a writer is running.

## 3. Start and show genuinely new measurements

1. Click **Live demo**.
2. Click **Start live session** once.
3. Watch Historical baseline count rise from 0 to 60, taking about 10 seconds depending on your computer.
4. These 60 timings are measured during this run. They are not fabricated past timestamps.
5. After collection finishes, the session becomes Running. Fault buttons unlock.
6. A new current measurement is committed approximately every two seconds, plus measurement/analysis time.
7. Wait for at least five current readings, about another 10 seconds. Automatic detection then starts.
8. Keep the workload in Normal for a few more readings. Normally the result should be Within learned baseline. Timing noise may produce occasional flags; this is a detector result, not a preset status.

Say to the panel:

“We first observe this task running normally. These earlier measurements become our history. The application then keeps collecting new measurements and compares them with that history.”

## 4. Prove the database connection

1. Open **Database** in another browser tab, leaving Live demo visible in the first.
2. Show Connected, SQLite, WAL and the full database path.
3. Leave Dataset on Latest live session.
4. Choose Historical baseline: it shows the frozen 60 baseline measurements.
5. Choose Latest measurements: new IDs, timestamps and measured durations appear automatically.
6. Point out that total readings keep increasing.
7. Show the exact SELECT statement and bound dataset parameter displayed above the rows.

Say:

“These are rows queried from the same SQL database used by the detector. We can see earlier baseline observations and newly arriving current observations.”

For imported non-live datasets, duration_ms/error_count can be blank because they have other metric names. The live dataset is the intended demonstration for this view.

## 5. Introduce an actual controlled software delay

1. In Live demo, click **Introduce 300 ms delay**.
2. The worker actually executes an extra 300 ms wait. It measures the total elapsed duration using a monotonic timer.
3. Watch duration rise from roughly 25–40 ms to roughly 325–350 ms; exact values depend on the computer.
4. In Database → Latest measurements, show the increased durations in newly committed rows.
5. After enough abnormal current readings arrive, the detector flags the window. It requires at least three flagged readings and at least 20% of the window.
6. The first alert may say Needs more evidence while normal and fault events coexist in the last-10-reading window. After about 20–30 seconds, the old normal events should leave the window and the delay explanation should lead if supported by the measured evidence.
7. Click **Open evidence report**. Inspect the chart, model counts, ranked causes and worker timing events.
8. In Database → Execution events, show DELAY_ENTERED and DELAY_COMPLETED, alongside DB_QUERY_OK. This helps distinguish worker delay from a database query failure.

Say:

“We are now deliberately slowing the test task. The next measurements show the delay, the system stores them, and the detector responds to those new observations. The report explains which execution events support the likely cause.”

Do not say the button directly tells the AI which answer to display. The analyzer does not receive the selected mode. The event logs do reveal the executed test stages, so this is an observable fault demonstration, not a blind discovery benchmark.

## 6. Remove the fault and show recovery

1. Return to Live demo and click **Normal / recover**.
2. New timings return toward the normal range.
3. The alert may remain briefly because recent fault readings are still in the rolling window.
4. Wait around 20–30 seconds for ten new normal readings.
5. Show the detector's latest result and normal measurements. Ordinary host noise can still cause flags; the app does not forcibly switch its verdict to normal.
6. In Database → Saved AI investigations, compare the stored status history.

Say:

“Recovery is evaluated from the new measurements. The alert does not disappear instantly because the investigation still considers recent history.”

## 7. Optional second fault — timeout

After recovery, click **Trigger test timeout**.

The local test dependency stub waits briefly and raises a TimeoutError, which the worker catches. The recorded error_count becomes 1, with UPSTREAM_TIMEOUT and REQUEST_FAILED execution events. The detector analyzes these observations. After the window fills with fault readings, the timeout hypothesis should lead.

This is a deliberately raised local test timeout, not a failed call to a real external service. Set Normal again to recover.

## 8. Show database queries independently of the website

Open a second PowerShell terminal in the project folder. Leave the backend running.

Run every supplied demo SELECT:

```powershell
.\.venv\Scripts\python.exe db_console.py --file demo_queries.sql
```

Show only the latest ten measured readings:

```powershell
.\.venv\Scripts\python.exe db_console.py --query "SELECT id,timestamp,period,duration_ms,error_count FROM reading_values WHERE dataset_id=(SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1) ORDER BY timestamp DESC LIMIT 10;"
```

Show the historical/current counts:

```powershell
.\.venv\Scripts\python.exe db_console.py --query "SELECT period,COUNT(*) AS total FROM readings WHERE dataset_id=(SELECT dataset_id FROM live_sessions ORDER BY created DESC LIMIT 1) GROUP BY period;"
```

Run the count query again after a few seconds. Current rows should increase; the baseline remains 60. The console opens the actual file in read-only mode. There is no separate database tool to install.

If you already use a database GUI, open the same path shown in the Database page with its SQLite driver and execute the statements in demo_queries.sql. Refresh query results to see new commits.

**Do we need INSERT or UPDATE queries?** No. The producer inserts actual measurements, and the app saves investigations automatically. Use the controls for faults; manually changing baseline rows during a demo would invalidate the normal reference.

## 9. Explain the AI simply

“We measure how long this task normally takes. The AI learns patterns from those earlier timings. When new timings or errors become unusual, it flags them. Then execution logs help explain what happened.”

Technical answer:
- 60 real baseline rows collected at session start.
- First 48 train a 160-tree Isolation Forest.
- Last 12 calibrate the anomaly-score threshold.
- Baseline stays fixed during the session; fault readings do not become training data.
- Each investigation reads the last 10 current rows from SQL (or 5–9 while starting).
- Isolation Forest scores these rows. A separately reported 6-MAD statistical safeguard catches large single-metric changes.
- A trigger requires at least three flagged observations and at least 20% of the window.
- Evidence rules compare causes and preserve contradictory signals.
- The fitted model is rebuilt deterministically from the same baseline each cycle in this prototype; model caching is a future optimization.

The UI and report show ML flags and statistical flags separately. Do not claim every alert came only from ML. Cause scores are evidence strength, not accuracy or fault probabilities.

## 10. Persistence and stopping

Click Stop at the end. Data and results remain saved. Closing only the browser does not stop the backend worker. Closing the backend stops measurement; reopening the app preserves records and marks the old session stopped. Click Start live session to create a fresh baseline and session. Old sessions remain available from the Database dataset selector and History.

History/overview list only the newest 100 entries. Live sessions can produce many saved results; the Database page selects the latest 30 reports for the chosen dataset. The live demo has no automatic retention deletion.

## 11. Likely panel questions

**Is this live data or prerecorded data?**
“The live mode measures the task's execution now and appends new timestamped rows. The workload and faults are controlled test conditions. We do not claim this is an external production feed.”

**Where is the database connection?**
“SQLite is embedded in our backend, with a real database file. The UI displays the exact file path and executes SQL against it; we can also query the same file independently.”

**Where does history come from?**
“The first 60 normal measurements become the baseline. They were collected earlier in this session and remain fixed while current observations keep arriving.”

**Does the AI know which button we pressed?**
“The detector receives measured readings and execution logs, not the control mode or action audit. Logs expose the executed stages, which makes this an explainable controlled test.”

**What if the website is closed?**
“Collection continues on the backend until Stop or server shutdown. The browser only requests the latest saved state.”

**Why does recovery take time?**
“The current window includes the latest ten observations, so earlier fault measurements must leave that window.”

**Does this prove accuracy on real equipment?**
“No. It verifies the live ingestion, SQL persistence, detection and investigation pipeline. Real equipment still needs an existing data source and representative evaluation.”

**Is this machine learning or just a fixed limit?**
“Isolation Forest is fitted to collected history. A separate robust statistical safeguard also runs, and we show both flag counts. The fixed pipeline thresholds decide when enough unusual readings justify an investigation.”

## 12. Troubleshooting

- No Live demo tab: confirm version 2.1, stop the older backend, launch from the new extracted folder and hard-refresh.
- Wrong folder / app.py missing: use START_WINDOWS.bat, which sets its own working directory.
- No database file: start the backend first; it creates storage/rootlens.db.
- Two different databases: compare the absolute path shown in the website with the one opened in your SQL tool. ROOTLENS_DB can override the default.
- Start is warming: allow the 60 baseline measurements to finish; fault injection is disabled during training collection.
- No result yet: wait for at least five current readings after the baseline.
- Fault not named immediately: allow enough fault observations into the rolling window. Needs more evidence is an intentional state.
- Database rows appear but report is older: the producer commits the reading first; model computation follows. The report displays the last reading ID it evaluated.
- Unexpected normal-mode alert: host scheduling and a short baseline can cause false positives. Show the evidence honestly; use representative conditions for the baseline and investigate threshold calibration rather than hiding the result.
- Database locked: close tools holding write transactions; run one backend process. Use the read-only console for demo queries.
- Worker error: the Live demo page shows the error; correct it and start a new session. Previously stored rows remain available.
- Server stops: collection stops. A website alone cannot keep the Python backend alive.

## 13. Validation scope

Automated tests exercise measured delay, timeout and recovery through SQL; insufficient-current-data handling; duplicate-start prevention; stop lifecycle; database views and API errors, in addition to the original detection/import tests. Laptop timing varies. The local workload is a reproducible demonstration mechanism, not a statistically validated industrial benchmark.

SQLite references: https://www.sqlite.org/serverless.html and https://www.sqlite.org/wal.html

Build verification: 19 automated tests passed. A full timed background-worker rehearsal also passed normal detection, delay detection, recovery, stop/persistence and independent SQL-console queries. Browser visual verification remains unavailable in this environment.
