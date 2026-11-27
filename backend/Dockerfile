FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --system --uid 10001 appuser
USER appuser
CMD ["python","manage.py","runserver","0.0.0.0:8000"]
