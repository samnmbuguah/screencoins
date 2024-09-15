# Base image
FROM python:3.9.20-slim-bullseye

# Set the working directory
WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    apt-utils && \
    wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the Django project
COPY . /app/

# Copy the shell script
COPY run_fetch_markets.sh /app/
RUN chmod +x /app/run_fetch_markets.sh

# Add the cron job
RUN echo "0 * * * * /app/run_fetch_markets.sh >> /var/log/cron.log 2>&1" > /etc/cron.d/fetch_markets && \
    chmod 0644 /etc/cron.d/fetch_markets && \
    crontab /etc/cron.d/fetch_markets

# Expose the port
EXPOSE 8042