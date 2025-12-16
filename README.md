# KISS-y Cron

Because for some reason everything else is terrible??

- Ofelia doesn't automatically notice changes in the config file
- Ofelia doesn't automatically notice changes in docker labels
- Ofelia only allows `local` jobs to be specified on the ofelia container's labels
- busybox/debian cron daemons make it a huge pain in the ass to send subprocess logs to docker's logs (ie, just pass stdout through)
- busybox/debian crons don't support docker labels at all

Kissycron will:

- read the given crontab (if eg `--file /etc/crontabs/root` is used) once per minute
- read docker labels (if `--docker` is used) once per minute
- run any jobs that are due to begin within the current minute
- log when each job starts
- each job's logs go to stdout

## Crontab Format

Standard minimalist crontab, eg

```
0,15,30,45 1 * * * echo "hello world"
```

Supported syntax:
- single integer for minute / hour / day of month / month / day of week
- list of integers separated by commas
- `*` for "every"

Not-(yet)-supported syntax:
- `*/5` for "every 5 minutes"
- `@hourly` or other named shortcuts

## Docker Labels

Fairly similar to ofelia's format:

```
kissycron.<job-type>.<job-id>.<attribute>
```

Where:
- `<job-type>` can be
  - `job-local` (runs a command in the kissycron container)
  - `job-exec` (runs a command in the container with the label)
- `<job-id>` is any string, unique per container (doesn't need to be globally unique)
- `<attribute>`
  - `schedule` is a standard cron schedue as explained in the "crontab format" section
  - `command` is a shell command


Example docker compose file:
```
services:
  cron:
    image: shish2k/kissycron:latest
    command: kissycron --docker
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /data:/data:ro
      - /data/backups:/data/backups:rw

  travmap:
    image: shish2k/travmap:latest
    labels:
      kissycron.job-local.backup.schedule: "18 1 * * *"
      kissycron.job-local.backup.command: "backup /data/travmap/ /data/backups/travmap/"
      kissycron.job-exec.update.schedule: "5 2 * * *"
      kissycron.job-exec.update.command: "/usr/bin/python3 /utils/manage.py update"
    volumes:
      - /data/travmap:/data
```
