# ==============================================================================
# Review Pulsator AI Backend Engine — Hugging Face Docker Space
# ==============================================================================
FROM python:3.12-slim

WORKDIR /app

# Hugging Face Spaces sets PORT=7860 by default
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user with UID 1000 (Required by Hugging Face Spaces security policy)
RUN groupadd -g 1000 user && useradd -u 1000 -g user -m user

# Install Python dependencies directly (avoids --no-deps wheel build failures)
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code with proper ownership
COPY --chown=user:user . .

# Switch to non-root user
USER user

# Expose port 7860 for Hugging Face Spaces ingress routing
EXPOSE 7860

# Boot REST API Server
CMD ["python3", "dashboard_server.py"]
