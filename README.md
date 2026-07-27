# Image Gallery

A Django web application that renders a configurable, paginated image gallery backed by [picsum.dev](https://picsum.dev/).

---

## Quick start

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

Copy `.env.example` to `.env` and edit the values. All settings have safe defaults so the application runs without a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure dev key | Django secret key — **must** be changed in production |
| `DEBUG` | `true` | Set to `false` in production |
| `ALLOWED_HOSTS` | `*` | Comma-separated list of allowed host names |
| `IMAGE_DEFAULT_SIZE` | `medium` | Default image size (`small`, `medium`, `large`) |
| `IMAGES_PER_PAGE` | `10` | Number of images shown per page by default |
| `CACHE_TTL` | `300` | Cache time-to-live in seconds; `0` disables caching |
| `UPSTREAM_TIMEOUT_SECONDS` | `5.0` | HTTP timeout per picsum.dev request |
| `UPSTREAM_RETRY_COUNT` | `3` | Max retry attempts on transient upstream errors |
| `UPSTREAM_BACKOFF_SECONDS` | `0.5` | Base backoff in seconds between retries (doubles each attempt) |

### Cache policy

The application uses Django's in-memory local cache (`LocMemCache`) by default. Generated image URL payloads are cached by a deterministic key that includes all output-affecting inputs (image ID, size, grayscale, blur, and relevant config values). This prevents duplicate upstream calls for identical requests within a single process lifetime. The cache is invalidated automatically when the process restarts.

---

## Running with Docker

```bash
docker compose up
```

The application will be available at <http://localhost:8000/>.

---

## Testing

```bash
pytest --cov=gallery --cov-report=term-missing
```
