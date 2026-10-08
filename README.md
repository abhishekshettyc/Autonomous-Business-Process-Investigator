# RootLens 2.1 — investigation website and live SQL demo

**Start with LIVE_DEMO_GUIDE.md for the new live demo and SQL walkthrough.**

Version 2.1 adds a measured local workload, background collection, fault controls, recovery and an auto-refreshing database explorer. The original upload workflow described below still works.

A responsive website for detecting unusual asset or process behavior and investigating probable causes. This upgrade adds real SQL storage, validated imports, trained anomaly detection and an entirely redesigned interface. The original banking prototype is separate; this version uses a general asset-and-metrics contract.

## Start on Windows (recommended: Python 3.11 or 3.12)

1. Extract the ZIP fully; do not run inside the ZIP preview.
2. Open the `rootlens-v2` folder.
3. Double-click `START_WINDOWS.bat`. It creates a virtual environment and installs dependencies on first use (internet required). Keep the window open.
4. Open http://127.0.0.1:8000 in your browser.
5. Click **Run investigation** on the overview page.

Manual setup in the VS Code terminal / PowerShell:

```powershell
cd "FULL_PATH_TO_EXTRACTED_FOLDER\rootlens-v2"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If the `py` launcher is unavailable, use `python` for the first command that creates the venv. The folder must contain `app.py`; use `dir` to check. Running the batch launcher avoids the earlier wrong-folder problem.

macOS/Linux:

```bash
cd /path/to/rootlens-v2
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

If port 8000 is occupied, append `--port 8001` and open http://127.0.0.1:8001. Stop with Ctrl+C. After installation the app works offline; the UI uses system font fallbacks if Google Fonts cannot load. No API key is required.

## Delivered tech stack

| Layer | Implementation |
|---|---|
| Website | Responsive HTML5, CSS, modular-function JavaScript, SVG charts |
| Backend | Python, FastAPI, Uvicorn |
| SQL storage | SQLite, parameterized queries and atomic writes |
| ML | scikit-learn Isolation Forest trained on each dataset's earlier asset history |
| Statistical safeguard | Median/MAD deviation detector for large single-metric departures |
| Investigation | Configurable evidence rules, contradiction penalties and abstention |
| Integration | JSON REST API, CSV import, JSONL event import |
| Tests | unittest + FastAPI TestClient |

One backend serves the frontend, so there is no separate Node build or frontend server to manage. No LLM is called in v2. Anomaly detection uses trained ML plus a separately reported statistical safeguard; cause ranking uses transparent rules. UI uses standard browser APIs without a frontend framework to keep local setup small.

## Website screens

- **Overview:** green/ivory workspace, navigation sidebar, scenario launcher, stored-data counts and recent investigations.
- **Investigation:** status, flagged readings, baseline/current chart with metric switcher, ranked causes, actual execution trace, evidence filter, missing evidence and JSON report export.
- **Data sources:** JSON bundle import; CSV plus optional JSONL import; SQL dataset list with investigation actions.
- **History:** saved reports reopen after server restart.
- **How it works:** data acquisition, single-machine baselines, physical diagnostic boundaries, API integration.

## Answers to the hardware questions

Software cannot sense an uninstrumented physical object. It can analyze evidence already exposed by a device, connected software, existing monitoring system or a person reporting observations. No additional hardware is built or required by this project.

| Available information | What RootLens can reasonably do |
|---|---|
| Existing machine metrics/API/log export | Learn earlier normal behavior and detect current deviations |
| Existing diagnostic/error codes | Correlate codes with abnormal readings and rank configured causes |
| Operator observation | Treat a timestamped report as evidence with a named source |
| Only a missing heartbeat | Flag availability evidence if represented; cannot distinguish power loss, network loss or a crashed collector from that alone |
| No telemetry, history, logs or observations | Cannot detect an unseen fault; request measurable evidence |

The house/purifier examples are not the project domain. They illustrate the limit: “not working” is a symptom shared by multiple faults. A broken fuse and a disconnected wire may look identical to software. A leak and a faulty flow measurement can also look alike. Existing diagnostic signals or qualified inspection must distinguish them; the app must not claim a specific damaged part without that evidence. Do not perform electrical inspections through this app; no control actions are provided.

For a single machine, compare it with **its own known-normal historical readings**. A second machine is unnecessary. With no suitable history, the current app rejects the dataset with a clear minimum-history requirement. It does not silently manufacture a baseline. Different load levels or operating modes can be normal and need separate baseline datasets. Manufacturer limits can be added as a domain extension; they are not automatically inferred here.

## Where real input comes from

1. An existing business/monitoring tool exports timestamped measurements to CSV or JSON.
2. A machine vendor's existing API or diagnostic software exposes readings/error logs, which a connector maps into this schema.
3. An operator records a timestamped observation as an event.
4. A software integration sends a bundle to `POST /api/datasets`, then requests an investigation.

The ingestion API is implemented. Vendor-specific adapters, MQTT/OPC-UA clients, automatic equipment discovery and continuous background collection are not included. Installation is on an ordinary laptop/server; you do not install this application inside every machine. Access to existing device data must already be available. Included demo data is synthetic and always labeled.

## Proper input contract

Every dataset represents **one asset** (a machine, service, workflow, process or monitored system), a consistent operating mode, metric definitions and their units, baseline observations, current observations, and optional events.

Use `samples/capacity.json` as the complete working template. Do not submit the tiny illustrative fragment below as a complete dataset.

```json
{
  "name": "Operations review",
  "asset_id": "OPS-01",
  "source": "Existing monitoring export",
  "synthetic": false,
  "metrics": [{"name": "latency_ms", "unit": "ms"}],
  "readings": [
    {"id": "R001", "timestamp": "2026-10-08T08:00:00+00:00", "period": "baseline", "values": {"latency_ms": 120}}
  ],
  "events": [
    {"id": "E001", "timestamp": "2026-10-08T12:05:00+00:00", "category": "RESOURCE_PRESSURE", "message": "Queue pressure reported", "source": "Monitoring system", "asset_id": "OPS-01", "reading_id": null}
  ]
}
```

Validation rules:

- 1–12 declared metrics with nonempty unit labels; every reading has exactly these numeric fields.
- At least 60 baseline and 5 current readings; maximum 10,000 readings.
- All baseline timestamps precede current timestamps. Timezone offsets are required and normalized to UTC.
- IDs and timestamps are unique within the dataset. Event IDs are unique, and optional reading IDs must resolve.
- Numeric values are finite and within ±1e12. The app validates structure, not the physical truth or correct calibration of a measurement.
- Up to 5,000 events and an 8 MB request body. A dataset is stored entirely or not at all.
- Missing numeric values are rejected, not silently imputed. Sample frequency need not be fixed; the chart uses actual timestamps, but the ML model evaluates rows without temporal features.

CSV columns: `id,timestamp,period,<metric1>,<metric2>,...`. Use `samples/readings.csv`, `events.jsonl` and `units.json` together. Enter dataset name and asset ID in the upload form. Events are optional: metrics can reveal an anomaly without enough information to explain its cause. Empty events should produce uncertainty, not an invented cause.

## General investigation configuration

The numerical detector supports arbitrary metric names. Cause reasoning is domain-configurable, not universal plug-and-play diagnosis. Default hypotheses cover resource capacity, upstream dependencies, configuration changes, physical subsystem warnings and measurement faults.

JSON bundles can supply 2–10 `hypotheses`, each with:

```json
{
  "id": "capacity",
  "name": "Capacity or resource bottleneck",
  "supports": ["RESOURCE_PRESSURE", "QUEUE_BUILDUP"],
  "contradicts": ["RESOURCE_HEALTHY"],
  "metrics": ["latency_ms", "queue_depth"],
  "next_check": "Inspect utilization and queue ownership."
}
```

Known signal categories map to these rules. Free-text event messages are preserved and displayed; they are not interpreted by an LLM. Unrecognized categories do not gain evidence scores. CSV imports use the default hypotheses; JSON supports custom profiles.

## ML and reasoning method

1. Sort readings chronologically. Train a 160-tree Isolation Forest on the first 80% of baseline rows only (fixed seed 42).
2. Score the remaining 20% of baseline rows as a calibration set. Its 2nd-percentile score becomes the outlier threshold. Current data is never used for training or calibration.
3. Evaluate current observations. Independently flag any metric more than 6 robust scale units from its training median; scale is `max(1.4826 × MAD, abs(median) × 0.01, 0.001)`. This safeguard handles large one-dimensional changes that the multivariate model can miss.
4. Trigger investigation when at least 20% and at least 3 current rows are flagged by either detector. Export includes individual ML/statistical flags and counts (they can overlap). This threshold needs domain calibration; it is not a general accuracy guarantee.
5. Retrieve events for the same asset during the current interval. Keep unrelated/old events visible as ignored.
6. Each supporting/contradicting signal gets ±35 points for a linked anomalous reading, 60% weight for same-window aggregate evidence, or 25% weight for a linked non-anomalous reading. Repeated copies of the same signal category count once per cause. Up to 20 extra points come from aligned metric median shifts.
7. A leading cause requires score ≥50, margin ≥15 over runner-up, and two different supporting signal categories. Otherwise report **Needs more evidence**.

These are heuristic evidence scores, not causal probabilities. Two sources can still be correlated, so “leading hypothesis” does not establish physical damage. Even stable readings do not certify equipment health. Demo data intentionally separates these situations.

Execution is bounded and automatic after a user/API trigger: fit → score → conditionally inspect events → compare hypotheses → propose next check or abstain. It is not an open-ended LLM agent. Version 2.1 continuously measures a controlled local software workload while its session is running; it does not monitor external hardware.

## SQL persistence

The app creates `storage/rootlens.db` at startup. Tables: `datasets`, `readings`, `events`, `investigations`. Raw validated numeric inputs and source evidence are preserved; report rows include model settings, baseline fingerprint, scores and execution trace. Fitted model objects are not persisted; each investigation retrains deterministically. Default history/dataset listing returns the latest 100 records, so overview counts are capped at 100. To choose another database file, set `ROOTLENS_DB` before starting the server.

Use SQLite for this hackathon: no separate DB installation or credentials. It satisfies SQL persistence. PostgreSQL/MongoDB are not currently wired up. For deployment, add authentication, per-user access, retention policy and a production database strategy; this delivery is a local website bound to 127.0.0.1 and has no login.

## API

- GET `/api/health`
- GET `/api/demo/{scenario}` — capacity, dependency, ambiguous, hardware, unknown, healthy
- POST `/api/datasets` — raw dataset JSON
- POST `/api/import-csv` — JSON containing `name`, `asset_id`, `csv`, `events`, `units`
- GET `/api/datasets` and `/api/datasets/{id}`
- POST `/api/datasets/{id}/investigate`
- GET `/api/history` and `/api/investigations/{id}`
- `/docs` — API routes (use the samples here for request bodies)

A read-only client integration example is in `send_dataset.py`; it uploads only the explicitly selected file to your local server and triggers investigation.

## Four-person demo plan

| Owner | Work |
|---|---|
| Backend/data | Imports, schema, SQL persistence and API integration |
| ML | Baseline selection, held-out evaluation, thresholds and drift limitations |
| UI | Website navigation, charts, evidence inspection and responsive refinements |
| Investigation/demo | Hypothesis profiles, data provenance, independent test scenarios and presentation |

Demo order: resource bottleneck → dependency → conflicting signals (abstention) → unknown (anomaly without cause) → device telemetry (generic physical warning) → stable operation. Refresh/restart to prove persistence. Upload the CSV samples. Select a hypothesis to filter evidence. Export a report and point out ML flags versus statistical flags.

## Tests and verified limits

```bash
python -m unittest discover -s tests -v
```

Automated checks cover expected leading hypotheses, ambiguity, unseen synthetic random seeds, healthy scenarios, missing/nonfinite/duplicate input rejection, leakage prevention, unrelated evidence, duplicate-signal suppression, CSV ingestion, SQL persistence, API errors and request size.

These synthetic tests are engineering checks, not independently measured real-world accuracy. Evaluate on representative held-out customer data before use. Live local software measurements are tested; no external hardware connection was tested. Browser visual verification was unavailable in the build environment; JavaScript syntax and API interactions were checked.

Sources for the chosen APIs/method: https://scikit-learn.org/stable/modules/outlier_detection.html and https://fastapi.tiangolo.com/tutorial/sql-databases/
