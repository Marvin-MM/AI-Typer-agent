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

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || echo "Some packages failed to install, continuing build"

# Copy the rest of the application
COPY . .

# Set environment variables for display
# Set the DISPLAY environment variable for Xvfb to simulate a display environment
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# Create entrypoint script
RUN echo '#!/bin/bash\nXvfb :99 -screen 0 1024x768x16 &\nsleep 1\nstreamlit run app.py' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Run the application with Xvfb
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["streamlit", "run", "app.py"]
