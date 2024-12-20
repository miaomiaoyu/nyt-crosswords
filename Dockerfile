# Python Version 3.9
FROM --platform=$TARGETPLATFORM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install Chrome so selenium driver works
RUN apt-get update
RUN apt-get install -y chromium wget unzip

# Latest ChromeDriver https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "mac-arm64" ]; then \
        # For ARM64, use chromedriver built for ARM
        wget -O chromedriver.zip https://storage.googleapis.com/chrome-for-testing-public/133.0.6906.0/mac-arm64/chromedriver-mac-arm64.zip; \
    else \
        # For AMD64/x86_64
        wget -O chromedriver.zip https://storage.googleapis.com/chrome-for-testing-public/133.0.6906.0/linux64/chromedriver-linux64.zip; \
    fi && \

    unzip chromedriver.zip && \
    rm chromedriver.zip

# Setup venv
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
