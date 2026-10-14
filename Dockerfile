FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home quantlab && mkdir -p /app/data && chown -R quantlab:quantlab /app/data
USER quantlab
ENV QUANTLAB_PUBLIC=1 QUANTLAB_DB_PATH=/app/data/quantlab.sqlite MPLCONFIGDIR=/tmp/matplotlib
EXPOSE 8000
CMD ["python", "-m", "scripts.serve"]
