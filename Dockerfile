FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for X11 forwarding and input devices
RUN apt-get update && apt-get install -y \
    xvfb \
    x11-utils \
    libx11-dev \
    libxtst-dev \
    libpng-dev \
    libjpeg-dev \
    libxcb1-dev \
    python3-tk \
    python3-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install LanguageTool for grammar checking
RUN apt-get update && apt-get install -y \
    openjdk-17-jre \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Update pip
RUN pip install --upgrade pip

# Explicitly install streamlit to ensure it's available
RUN pip install streamlit

RUN pip install chardet==5.2.0

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || echo "Some packages failed to install, continuing build"

# Copy the rest of the application
COPY . .

# Set environment variables for display and disable Streamlit's welcome screen
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_TELEMETRY=false
ENV STREAMLIT_BROWSER_SERVER_ADDRESS="0.0.0.0"
ENV STREAMLIT_SERVER_PORT=10000
ENV STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true

# Create a .streamlit directory and config.toml file to disable the welcome screen
RUN mkdir -p /root/.streamlit && \
    echo '[general]\nshowWarningOnDirectExecution = false\nemail = ""\ndisableWatchdogWarning = true\n\n[server]\nenableXsrfProtection = false\nenableCORS = false\n\n[browser]\ngatherUsageStats = false\nserverPort = 10000\nserverAddress = "0.0.0.0"' > /root/.streamlit/config.toml

# Create improved entrypoint script with error handling for Xvfb
RUN echo '#!/bin/bash\n\
# Remove any stale X lock files\n\
rm -f /tmp/.X99-lock\n\
rm -f /tmp/.X11-unix/X99\n\
\n\
# Start Xvfb in the background\n\
Xvfb :99 -screen 0 1024x768x16 &\n\
sleep 2\n\
\n\
# Run the application with options to disable interactive welcome\n\
exec streamlit run app.py --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false --browser.gatherUsageStats=false\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Set entrypoint to our script
ENTRYPOINT ["/app/entrypoint.sh"]

# Expose port 10000 for Streamlit
EXPOSE 10000
