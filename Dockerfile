# Python Version 3.9
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

# Copy requirement files first
COPY requirements.txt .

# Install dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY run.py .

# Define the command to run the application
CMD ["python3", "run.py"]
