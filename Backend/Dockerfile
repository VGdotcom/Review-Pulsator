# ==============================================================================
# Review Pulsator AI Backend Engine — Hugging Face Docker Space
# ==============================================================================

# Stage 1: Build & Dependency Wheel Generation
FROM python:3.12-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Hardened Runtime Container for Hugging Face Spaces
FROM python:3.12-slim as runtime
WORKDIR /app

# Hugging Face Spaces sets PORT=7860 by default
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Create non-root system user with UID 1000 (Required by Hugging Face Spaces security policy)
RUN groupadd -g 1000 user && useradd -u 1000 -g user -m user
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application source code with proper ownership
COPY --chown=user:user . .
USER user

# Expose port 7860 for Hugging Face Spaces ingress routing
EXPOSE 7860

# Boot REST API Server
CMD ["python3", "dashboard_server.py"]
