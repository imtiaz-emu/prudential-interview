# Image Gallery

A Django web application that renders a configurable, paginated image gallery backed by [picsum.photos](https://picsum.photos/).

---

## Requirements

- Python 3.12+
- Docker + Docker Compose

---

## Run

### Docker

```bash
docker compose up
```

Open <http://localhost:8000/>. Migrations run automatically on startup.

```bash
docker compose up -d        # run in background
docker compose logs -f      # stream logs
docker compose down         # stop and remove
```

### Local dev server

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://localhost:8000/>.

---

## Configuration

Copy `.env.example` to `.env` to override defaults. All settings have safe fallback values so the app runs without a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure dev key | Django secret key — **change in production** |
| `DEBUG` | `true` | Set to `false` in production |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed host names |
| `PICSUM_BASE_URL` | `https://picsum.photos` | Upstream image provider base URL |
| `IMAGE_DEFAULT_SIZE` | `medium` | Default image size (`small`, `medium`, `large`) |
| `IMAGES_PER_PAGE` | `10` | Default images per page |
| `CACHE_TTL` | `300` | Cache TTL in seconds |
| `UPSTREAM_TIMEOUT_SECONDS` | `5.0` | Timeout per upstream request |
| `UPSTREAM_RETRY_COUNT` | `3` | Max retry attempts on transient upstream errors |
| `UPSTREAM_BACKOFF_SECONDS` | `0.5` | Base backoff between retries (doubles each attempt) |

---

## Endpoints

### `GET /` — Gallery

Paginated image grid with filter controls.

| Parameter | Default | Validation |
|-----------|---------|------------|
| `page` | `1` | ≥ 1; invalid values redirect to `?page=1` |
| `per_page` | `10` | 1 – 50 |
| `size` | `medium` | `small`, `medium`, `large` |
| `grayscale` | — | `1`, `true`, `yes`, `on` |
| `blur` | `0` | 0 – 10 |

### `GET /image/<id>/` — Detail

Single image with parameter display. Accepts `size`, `grayscale`, `blur`.

### `GET /health/` — Health check

Always HTTP 200. Returns JSON:

```json
{
  "status": "ok",
  "timestamp": "2026-07-30T12:00:00.000Z",
  "checks": { "cache": "ok", "upstream": "ok" }
}
```

`status` is `"degraded"` if any check fails.

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/
```
