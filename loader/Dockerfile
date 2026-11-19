FROM python:3.12-slim
WORKDIR /app
COPY loader/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sql/ sql/
COPY loader/load_fda.py .
CMD ["python", "load_fda.py"]
