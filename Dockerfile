FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y git
RUN python3 -m pip install cmtj[utils] scienceplots
RUN git clone https://github.com/LemurPwned/cmtj.git
# change to read only mode - make all existing files read-only but keep directory writable for new files
RUN git config --global --add safe.directory /app/cmtj && \
    find /app/cmtj -type f -exec chmod 444 {} \; && \
    find /app/cmtj -type d -exec chmod 755 {} \;

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
ENV LOGURU_LEVEL=INFO
ENTRYPOINT ["python", "main.py", "--interactive", "--working-dir", "./cmtj"]
