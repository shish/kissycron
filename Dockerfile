FROM python:3.14-alpine
RUN apk add --no-cache rsync docker-cli
COPY kissycron.py /usr/bin/kissycron
COPY backup.py /usr/bin/backup
ENTRYPOINT ["kissycron", "--docker"]
CMD ["run-cron"]
