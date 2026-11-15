FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY . /app

# Expose port (default 8000 or from PORT env)
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python3", "scripts/run_server.py"]
