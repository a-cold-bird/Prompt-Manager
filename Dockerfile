# Python 3.10 slim base image
FROM python:3.10-slim

# Working directory
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create required folders
RUN mkdir -p instance static/uploads static/thumbnails logs

# Runtime environment
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV DATABASE_URL=postgresql+psycopg2://prompt_manager:prompt_manager@db:5432/prompt_manager

# Expose port
EXPOSE 5000

# Startup script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Initialize DB (idempotent) and ensure admin user exists\n\
echo "[INFO] Running database initialization..."\n\
python -m flask init-db\n\
echo "[OK] Database initialization finished"\n\
\n\
# Start app\n\
exec gunicorn \\\n  -w ${GUNICORN_WORKERS:-2} \\\n  -b ${GUNICORN_BIND:-0.0.0.0:5000} \\\n  --threads ${GUNICORN_THREADS:-4} \\\n  --log-level ${GUNICORN_LOG_LEVEL:-info} \\\n  --access-logfile - \\\n  --error-logfile - \\\n  app:app' > /start.sh && chmod +x /start.sh

# Run
CMD ["/start.sh"]