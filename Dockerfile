FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

ENV PORT 8080
EXPOSE 8080

# Use a shell command to handle the PORT env variable correctly
CMD ["sh", "-c", "uvicorn src.web_app:app --host 0.0.0.0 --port ${PORT:-8080}"]
