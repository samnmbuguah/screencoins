# Base image
FROM debian:bullseye-slim

# Set the working directory
WORKDIR /app

# Install dependencies
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
    apt-utils && \
    wget https://www.python.org/ftp/python/3.12.5/Python-3.12.5.tgz && \
    tar -xzf Python-3.12.5.tgz && \
    cd Python-3.12.5 && \
    ./configure --enable-optimizations && \
    make -j$(nproc) && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.12.5 Python-3.12.5.tgz && \
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

# Install Python dependencies
COPY requirements.txt /app/
RUN pip3.12 install --upgrade pip && \
    pip3.12 install -r requirements.txt

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