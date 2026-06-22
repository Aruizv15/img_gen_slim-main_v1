FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /app/templates /app/static/css /app/static/js \
    /app/shared_data/input_images /app/shared_data/output_images \
    /app/shared_data/reference_images /app/shared_data/temp_images \
    /app/workflows

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py /app/
COPY templates/ /app/templates/
COPY static/ /app/static/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]