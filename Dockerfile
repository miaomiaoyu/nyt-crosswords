FROM --platform=linux/amd64 python:3.13.1-slim-bookworm

# Set the working directory
WORKDIR /app

RUN apt-get update
RUN apt-get install -y curl wget unzip ca-certificates gnupg

# Add Google Chrome repository
RUN wget -q https://dl-ssl.google.com/linux/linux_signing_key.pub \
    && mkdir -p /etc/apt/keyrings \
    && mv linux_signing_key.pub /etc/apt/keyrings/ \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/linux_signing_key.pub] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Install Google Chrome
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Latest ChromeDriver https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json
RUN wget https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.13/linux64/chromedriver-linux64.zip
RUN unzip chromedriver-linux64.zip
RUN mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && chmod +x /usr/local/bin/chromedriver

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
