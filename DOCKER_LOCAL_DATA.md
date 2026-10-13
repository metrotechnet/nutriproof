# Docker + local data storage

This project can run in Docker without code signing, while keeping user data on the local machine.

## Why this approach

- Docker avoids native macOS code signing issues
- the app can run on macOS, Windows, and Linux
- uploaded files are stored in a host bind mount instead of inside the container
- `uploads/main` stays on the user PC, not inside a Docker layer

## How it works

The server reads the `UPLOAD_ROOT` environment variable and stores all project data there.

By default, Docker Compose mounts the host folder to `/app/uploads` inside the container.

## Run locally

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set a local folder, for example:

```bash
UPLOAD_ROOT=/Users/yourname/NutriProof/uploads
PORT=8080
```

or on Windows:

```bash
UPLOAD_ROOT=C:/NutriProof/uploads
PORT=8080
```

3. Start the app:

```bash
docker compose up --build
```

4. Open the app in the browser:

```text
http://localhost:8080
```

## Data location

The app will write project files under the host path you configure in `UPLOAD_ROOT`, so the user data stays on the local machine.

This is the right pattern when you want:

- server-style execution
- no native app signing
- local file persistence on the user machine
- cross-platform deployment via Docker

## Important note

This is a Docker/container deployment. It is not a signed desktop app for macOS distribution. For end-user installation, you still need proper Apple signing + notarization if you want a native `.app` package.
