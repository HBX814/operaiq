FROM python:3.12-slim
WORKDIR /app
RUN pip install google-cloud-pubsub --no-cache-dir
COPY generator.py .
CMD ["python", "generator.py"]
