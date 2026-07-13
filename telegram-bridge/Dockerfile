FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install ffmpeg for media processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run the python app
CMD ["python", "main.py"]
