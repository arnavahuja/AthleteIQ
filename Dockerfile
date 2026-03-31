# ---- Stage 1: Build frontend ----
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --production=false

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Install Python deps ----
FROM python:3.12-slim AS python-build

WORKDIR /app

# Install build tools needed for numpy/scipy compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./

# Install CPU-only PyTorch first (saves ~1.5GB vs default CUDA build)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining deps
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 3: Final slim runtime image ----
FROM python:3.12-slim

WORKDIR /app

# Copy installed Python packages from build stage
COPY --from=python-build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=python-build /usr/local/bin /usr/local/bin

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

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"]
