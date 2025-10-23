FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501

EXPOSE ${STREAMLIT_SERVER_PORT}

CMD ["streamlit", "run", "app.py", "--server.port", "${STREAMLIT_SERVER_PORT}", "--server.headless", "true"]
