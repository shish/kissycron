FROM python:3.14
RUN apt-get update && apt-get install -y rsync docker-cli
COPY kissycron.py /usr/bin/kissycron
COPY backup.sh /usr/bin/backup
CMD ["kissycron", "--file", "/etc/crontabs/root"]
