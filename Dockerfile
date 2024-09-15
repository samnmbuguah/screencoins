# Base image
FROM python:3.12.6-slim-bullseye

# Set the working directory
WORKDIR /app

# Install apt-utils first to avoid debconf errors
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils

# Install other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    libssl-dev \
    zlib1g-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libgdbm-dev \
    libdb5.3-dev \
    libbz2-dev \
    libexpat1-dev \
    liblzma-dev \
    tk-dev \
    ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install ta-lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Switch to the non-root user
USER samuel

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --user --upgrade pip && \
    pip install --user -r requirements.txt

# Switch back to root user to copy project files and set permissions
USER root

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

# Switch back to the non-root user
USER samuel