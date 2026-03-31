# ---- Stage 1: Build frontend ----
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend + built frontend ----
FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy data files
COPY data/ ./data/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
