FROM python:3.12-slim

RUN apt-get update && apt-get install -y git
RUN git clone https://github.com/LemurPwned/cmtj.git
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
ENV LOGURU_LEVEL=INFO
ENTRYPOINT ["python", "main.py", "--interactive"]
