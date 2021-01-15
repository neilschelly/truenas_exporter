FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY truenas_exporter.py .
COPY truenas_collector.py .
ENTRYPOINT [ "python", "./truenas_exporter.py" ]
CMD [ "--help" ]
