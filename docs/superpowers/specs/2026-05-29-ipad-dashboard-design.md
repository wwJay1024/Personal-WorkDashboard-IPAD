# iPad Dashboard System Design

## Goal

Build a local-first iPad dashboard that runs from a Mac and exposes a browser UI on the local network. The dashboard shows weather, schedule, todos, LLM balance usage, sticky notes, and break reminders. Schedule, todos, and notes can be edited quickly on the Mac through JSON files or REST APIs, then pushed to the iPad in near real time.

## Delivery Shape

Use option 1: FastAPI backend, vanilla HTML/CSS/JS frontend, JSON file storage, and local startup scripts.

## Architecture

- API layer: FastAPI REST endpoints, WebSocket endpoint, and static frontend hosting.
- Service layer: JSON data service, file watcher, weather fetcher, balance fetcher, scheduler, reminder loop, and WebSocket manager.
- Model layer: Pydantic models for todos, events, notes, balances, dashboard config, and external service payloads.
- Infrastructure: `data/*.json`, `config.yaml`, `dashboard.json`, `watchdog`, `httpx`, `APScheduler`, `loguru`.

## Data Flow

Mac edits to files under `data/` or `dashboard.json` are detected by `watchdog`, debounced, validated, and broadcast to connected iPad clients through WebSocket. External weather and balance data refresh on intervals and use cached values when network/API calls fail. REST endpoints provide CRUD access for editor tools and future automation.

## Frontend

The UI is a single dashboard page optimized for iPad landscape and passive viewing. Components are rendered through a registry keyed by `component.type`. `dashboard.json` controls component visibility, order, size, and refresh labels. The WebSocket client updates components in place, with HTTP polling as a fallback if the socket disconnects.

## Extensibility

Adding a component requires:

1. Add a Pydantic model if it stores records.
2. Register the data type in `app/main.py`.
3. Add a frontend renderer in `static/app.js`.
4. Add a component entry to `dashboard.json`.

## Error Handling

Invalid JSON files return safe empty lists and log errors. External API failures keep the last cache. WebSocket disconnects are cleaned up automatically. Missing API keys show a clear configured/unconfigured state without breaking the dashboard.

## Verification

Run dependency installation, start the FastAPI app, call `/health`, call representative `/api/*` endpoints, and load the static dashboard route.
