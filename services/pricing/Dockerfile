FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PORT=8003

# Create non-root user (UID 10001) for security & Kubernetes Pod Security Standards
RUN useradd -u 10001 -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8003

CMD ["python", "main.py"]
