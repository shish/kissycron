# KISS-y Cron

Because for some reason everything else is terrible??

- Busybox/debian cron daemons make it a huge pain in the ass to send subprocess logs to docker's logs (ie, just "pass stdout through")
  - they're really designed to collect output and email it to the user, which is a great design for the 1980's
- Busybox/debian crons don't support docker labels at all
- Ofelia doesn't automatically notice changes in the config file
- Ofelia doesn't automatically notice changes in docker labels
- Ofelia only allows `local` jobs to be specified on the ofelia container's labels
  - I don't want to install backup tools in every application container
  - I don't want every application container to have write access to my backups folder
  - I want to have a label on the application-container which tells my backup-container what to do

Kissycron will:

- Read the given crontab (if eg `--file /etc/crontabs/root` is used) once per minute
- Read docker labels (if `--docker` is used) once per minute
- Run any jobs that are due to begin within the current minute
- Log when each job starts
- Send each job's logs to stdout so that it shows up in `docker compose logs cron`

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

Vaguely copy-pasting ofelia's format because that's what I was using up until now:

```
kissycron.<job-type>.<job-id>.<attribute>
```

Where:
- `<job-type>` can be
  - `job-local` - runs a command in the kissycron container
  - `job-exec` - runs a command in the container with the label
- `<job-id>` is any string, unique per container (doesn't need to be globally unique)
- `<attribute>` can be
  - `schedule` - a standard cron schedue as explained in the "crontab format" section
  - `command` - a shell command


Example docker compose file:
```yaml
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

## Support

I've built this for my own personal use, and I'm not sure if I like the docker label format, so I might change that on short notice. If literally a single person says "I'd like to use this too" then I'll try to make the interface stable and do a proper version-numbered release.

## Dependencies

- python
- `docker` CLI - only if using `--docker` option

## Utilities

- The docker image is based on `python`, which is based on `debian`, so you get all the usual debian utilities
- `/usr/bin/backup` - a simple wrapper around rsync
