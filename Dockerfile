# Use official Python image as base
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install dependencies from requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code
COPY . .

# Create and use a non-root user
RUN useradd --create-home --shell /bin/bash botuser && \
    chown -R botuser:botuser /app

USER botuser

# Set environment variable for unbuffered output
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "bot.py"]
