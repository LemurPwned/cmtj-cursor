FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install CMTJ library
RUN python3 -m pip install cmtj[utils] scienceplots

# Clone CMTJ repository
RUN git clone https://github.com/LemurPwned/cmtj.git

# Configure git and set permissions for CMTJ repo
RUN git config --global --add safe.directory /app/cmtj && \
    find /app/cmtj -type f -exec chmod 444 {} \; && \
    find /app/cmtj -type d -exec chmod 755 {} \;

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Create the _cmtj working directory
RUN mkdir -p _cmtj

# Set environment variables
ENV LOGURU_LEVEL=INFO
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Expose port for Streamlit
EXPOSE 8501

# Default command runs the chat app
CMD ["streamlit", "run", "chat_app.py", "--server.port=8501", "--server.address=0.0.0.0"]

# Alternative: To run the CLI interface instead, use:
# docker run <image> python main.py --interactive --working-dir ./cmtj
