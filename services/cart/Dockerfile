# Multi-stage Dockerfile for TotemOps service
# Stage 1: Build dependencies in isolated virtual environment
FROM python:3.12-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir -r requirements.txt

# Stage 2: Minimal hardened runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PATH="/opt/venv/bin:$PATH"     PORT=8004

# Non-root user (UID 10001) for container security & K8s Pod Security Standards
RUN groupadd -g 10001 appgroup &&     useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Copy pre-built virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy service application code
COPY . .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8004

CMD ["python", "main.py"]
