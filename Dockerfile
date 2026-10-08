FROM python:3.12-slim
ARG SERVICE=backend
WORKDIR /app
COPY ${SERVICE}/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ${SERVICE}/main.py /app/main.py
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
