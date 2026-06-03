# Internal App

The internal app is now DB-free for local development and runtime data storage.
Reference requests are saved to a local JSON file instead of MongoDB.

## Storage

- Default store file: `../hr-ref-requests.json` (relative to `internal/main.py`)
- Override with env var: `HR_REF_STORE_FILE`

## Local run

1. `cd internal`
2. `uv sync`
3. `uv run fastapi dev main.py --host localhost --port 8000`

## Notes

- MongoDB and `VCAP_SERVICES` are no longer required.
- Internal and external apps must point to the same JSON store file to share IDs.
- SSO-related env vars are still required for full auth flow in non-local environments.



RUN BACKEND - 
1. cd Backend
2. .\venv\Scripts\Activate.ps1
3. uvicorn main:app --reload --host 127.0.0.1 --port 8000

RUN FRONTEND

1. cd Frontend
2. Npm install
3. NPM Run Dev
