FROM python:3.10-slim

WORKDIR /app

# System deps (safe minimum for pip builds)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (better caching)
COPY pyproject.toml ./

# If you have a lock file, copy it too (choose one if exists)
# COPY poetry.lock ./
# COPY uv.lock ./

# Install project (editable not needed inside container)
RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir .

# Now copy source code
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]