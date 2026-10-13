FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PIP_NO_CACHE_DIR=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-fra \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads/main

EXPOSE 8080

CMD ["python", "app.py"]
