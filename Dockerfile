FROM mcr.microsoft.com/playwright/python:v1.49.0-noble
WORKDIR /app
RUN pip install --no-cache-dir playwright==1.49.0
COPY monitor.py .
CMD ["python", "-u", "monitor.py"]
