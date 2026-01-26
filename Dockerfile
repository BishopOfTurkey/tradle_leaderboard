FROM python:3.13-slim

# Install litestream
RUN apt-get update && apt-get install -y wget && \
    wget https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.deb && \
    dpkg -i litestream-v0.3.13-linux-amd64.deb && \
    rm litestream-v0.3.13-linux-amd64.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv and dependencies
RUN pip install uv
COPY pyproject.toml .
COPY backend/ backend/
RUN uv pip install --system .

# Create data directory
RUN mkdir -p /data

# Copy config and startup script
COPY litestream.yml /etc/litestream.yml
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

EXPOSE 8080

CMD ["/app/run.sh"]
