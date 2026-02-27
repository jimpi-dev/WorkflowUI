# Build frontend (static) and backend, then run backend serving frontend on one port.
# Build context: parent directory (WorkflowUI). Build from docker: docker build -f docker/Dockerfile .

# --- Stage 1: build frontend (static) ---
FROM node:20-alpine AS frontend-build
WORKDIR /app

# Backend URL empty = same origin (backend will serve static + API).
ENV BACKEND_URL=
ENV ADAPTER_STATIC=1

COPY frontend/package.json frontend/package-lock.json* ./frontend/
COPY app.config.json ./
RUN cd frontend && npm ci
COPY frontend/ ./frontend/
# Ensure blog content is present so the home page (/home) blog section works
COPY frontend/src/blog/ ./frontend/src/blog/
# Regenerate .svelte-kit (COPY overwrote the one created by npm ci prepare)
RUN cd frontend && npx svelte-kit sync
RUN cd frontend && npm run build

# --- Stage 2: backend + static ---
FROM python:3.12-slim
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/frontend/build ./static
COPY docker/entrypoint.sh /app/backend/entrypoint.sh
RUN chmod +x /app/backend/entrypoint.sh

ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["./entrypoint.sh"]
