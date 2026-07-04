FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
COPY run.sh .
RUN chmod a+x run.sh

# Databasen gemmes i /data, som Home Assistant Supervisor automatisk
# gør persistent for dette add-on (overlever genstart/opdatering).
ENV INDKOBSLISTE_DB=/data/indkobsliste.db

CMD [ "./run.sh" ]
