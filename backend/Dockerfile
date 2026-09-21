FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# curl is pre-installed in ubi9/python-311 — no additional install needed

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/backend

# UBI python-311 image already runs as non-root user 1001 by default
USER 1001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://0.0.0.0:8000/api/health || exit 1

# Bind to 0.0.0.0 inside the container so the frontend container can reach the backend
# over the internal Docker bridge network. The host-side port binding in docker-compose.yml
# (127.0.0.1:8000) ensures no external exposure.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
