FROM python:3.10-slim

WORKDIR /app

# install uv + build tools (keeps it fast)
RUN pip install --no-cache-dir uv

# copy only dependency files first (better layer caching)
COPY pyproject.toml ./
# if you have it, also copy the lock file
# COPY uv.lock ./

# install deps
RUN uv pip install --system --no-cache -r pyproject.toml

# now copy the code
COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]