FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /app/templates /app/static/css /app/static/js \
    /app/shared_data/input_images /app/shared_data/output_images \
    /app/shared_data/reference_images /app/shared_data/temp_images \
    /app/workflows

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ImgGenScript/ /workspace/ImgGenScript/
RUN pip install --no-cache-dir -r /workspace/ImgGenScript/backend/requirements.txt

COPY main.py /app/
COPY handler.py /app/
COPY test_input.json /app/test_input.json
COPY templates/ /app/templates/
COPY static/ /app/static/

EXPOSE 8000

CMD ["python", "/app/handler.py"]