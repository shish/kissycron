#!/usr/bin/env python3
import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from time import sleep

log = logging.getLogger()


class CronJob:
    def __init__(
        self,
        id: str,
    ):
        self.minute = "*"
        self.hour = "*"
        self.day_of_month = "*"
        self.month = "*"
        self.day_of_week = "*"
        self.command = "echo 'No command specified'"
        self.id = id

    def set_schedule(
        self,
        minute: str,
        hour: str,
        day_of_month: str,
        month: str,
        day_of_week: str,
    ):
        self.minute = minute
        self.hour = hour
        self.day_of_month = day_of_month
        self.month = month
        self.day_of_week = day_of_week

    def set_command(self, command: str):
        self.command = command

    def matches(self, dt: datetime.datetime) -> bool:
        return (
            self._matches_field(self.minute, dt.minute)
            and self._matches_field(self.hour, dt.hour)
            and self._matches_field(self.day_of_month, dt.day)
            and self._matches_field(self.month, dt.month)
            and self._matches_field(self.day_of_week, dt.weekday())
        )

    def _matches_field(self, field: str, value: int) -> bool:
        if field == "*":
            return True
        for part in field.split(","):
            if part.isdigit() and int(part) == value:
                return True
        return False

    def spawn(self):
        maybe_id = f"[{self.id}] " if self.id else ""
        log.info(f"{maybe_id}Executing command: {self.command}")
        subprocess.Popen(self.command, shell=True)

    def __str__(self):
        maybe_id = f" # {self.id}" if self.id else ""
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week} {self.command}{maybe_id}"


def parse_crontab(path: Path) -> list[CronJob]:
    jobs = []
    log.info(f"Parsing {path.absolute()}")

    if not path.is_file():
        log.warning(f"Crontab file '{path.absolute()}' not found, skipping.")
        return []

    for n, line in enumerate(path.read_text().splitlines()):
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split(maxsplit=5)
            if len(parts) == 6:
                job = CronJob(f"{path.name}:{n}")
                job.set_schedule(*parts[:5])
                job.set_command(parts[5])
                jobs.append(job)
            else:
                log.warning(f"Invalid crontab line: {line}")

    return jobs


def parse_docker_labels() -> list[CronJob]:
    jobs = {}
    log.info("Getting jobs from docker labels")
    try:
        docker_ps = subprocess.check_output(
            ["docker", "ps", "--format", "{{.ID}} {{.Names}}"]
        ).decode()
        for line in docker_ps.strip().split("\n"):
            container_id, container_name = line.split(maxsplit=1)
            docker_inspect = subprocess.check_output(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{json .Config.Labels}}",
                    container_id,
                ]
            ).decode()

            for label, value in json.loads(docker_inspect).items():
                label_parts = label.split(".")
                if len(label_parts) == 4 and label_parts[0] == "kissycron":
                    (_, job_type, job_name, attr) = label_parts
                    job_id = f"{container_name}.{job_name}"
                    if job_id not in jobs:
                        jobs[job_id] = CronJob(job_id)
                    if attr == "schedule":
                        jobs[job_id].set_schedule(*value.split(maxsplit=5)[:5])
                    elif attr == "command":
                        if job_type == "job-local":
                            jobs[job_id].set_command(value)
                        elif job_type == "job-exec":
                            jobs[job_id].set_command(
                                f"docker exec {container_name} sh -c '{value}'"
                            )
    except Exception:
        log.exception("Error retrieving docker labels:")

    return list(jobs.values())


def main(argv: list[str]):
    parser = argparse.ArgumentParser(description="Kissycron")
    parser.add_argument("--file", type=Path, help="Path to crontab file")
    parser.add_argument("--docker", action="store_true", help="Parse docker labels")
    parser.add_argument("--dump", action="store_true", help="Dump parsed jobs and exit")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")

    if args.file and not os.path.isfile(args.file):
        log.error(f"Crontab file '{args.file}' does not exist.")
        sys.exit(1)

    while True:
        jobs = [
            *(parse_crontab(args.file) if args.file else []),
            *(parse_docker_labels() if args.docker else []),
        ]
        if args.dump:
            for job in jobs:
                print(str(job))
            sys.exit(0)

        log.info("Running any scheduled tasks")
        now = datetime.datetime.now()
        for job in jobs:
            if job.matches(now):
                job.spawn()

        log.info("Sleeping until next minute")
        now = datetime.datetime.now()
        next_minute = (now + datetime.timedelta(minutes=1)).replace(
            second=0, microsecond=0
        )
        sleep_duration = (next_minute - now).total_seconds()
        sleep(sleep_duration)
        # if we accidentally slept for 59 seconds, sleep some more
        while datetime.datetime.now().minute == now.minute:
            sleep(0.5)


if __name__ == "__main__":
    main(sys.argv[1:])
