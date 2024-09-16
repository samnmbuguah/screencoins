# Base image
FROM python:3.12.6-slim-bullseye

# Set the working directory
WORKDIR /app

# Install apt-utils first to avoid debconf errors
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils

# Install other dependencies including cron
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
    ca-certificates \
    python3-dev \
    gcc \
    cron && \
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

# Create a non-root user
RUN useradd -m -d /home/samuel -s /bin/bash samuel

# Install Python dependencies as samuel user
USER samuel
COPY requirements.txt /app/
RUN pip install --user --upgrade pip && \
    pip install --user -r requirements.txt

# Switch back to root user to copy project files and set permissions
USER root
COPY . /app/
RUN chown -R samuel:samuel /app

# Configure crontab for the user
USER samuel
RUN (crontab -l 2>/dev/null; echo "* * * * * /usr/bin/python /app/manage.py some_cron_job") | crontab -

# Expose the port
EXPOSE 8042

# Switch back to the non-root user
USER samuel