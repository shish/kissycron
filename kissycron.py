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

    def _comparison_key(self):
        return (
            self.minute,
            self.hour,
            self.day_of_month,
            self.month,
            self.day_of_week,
            self.command,
            self.id,
        )

    def __eq__(self, other):
        if not isinstance(other, CronJob):
            return False
        return self._comparison_key() == other._comparison_key()

    def __hash__(self):
        return hash(self._comparison_key())

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

    def spawn(self, wait=False):
        maybe_id = f"[{self.id}] " if self.id else ""
        log.info(f"{maybe_id}Executing command: {self.command}")
        proc = subprocess.Popen(self.command, shell=True)
        if wait:
            proc.wait()

    def __str__(self):
        maybe_id = f" # {self.id}" if self.id else ""
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week} {self.command}{maybe_id}"


def parse_crontab(path: Path) -> list[CronJob]:
    jobs = []
    log.debug(f"Parsing {path.absolute()}")

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
    log.debug("Getting jobs from docker labels")
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


def find_jobs(args: argparse.Namespace) -> set[CronJob]:
    jobs: set[CronJob] = {
        *(parse_crontab(args.file) if args.file else []),
        *(parse_docker_labels() if args.docker else []),
    }

    if args.match:
        jobs = {
            job for job in jobs if args.match in job.id or args.match in job.command
        }

    return jobs


def run_cron(args: argparse.Namespace):
    """Run cron daemon - continuously check and execute scheduled jobs"""
    last_jobs: set[CronJob] = set()
    while True:
        jobs = find_jobs(args)

        if jobs != last_jobs:
            if del_jobs := last_jobs - jobs:
                log.info("Jobs removed:\n" + "\n".join(str(job) for job in del_jobs))
            if add_jobs := jobs - last_jobs:
                log.info("Jobs added:\n" + "\n".join(str(job) for job in add_jobs))
            last_jobs = jobs

        log.debug("Running any scheduled tasks")
        now = datetime.datetime.now()
        for job in jobs:
            if job.matches(now):
                job.spawn()

        log.debug("Sleeping until next minute")
        now = datetime.datetime.now()
        next_minute = (now + datetime.timedelta(minutes=1)).replace(
            second=0, microsecond=0
        )
        sleep_duration = (next_minute - now).total_seconds()
        sleep(sleep_duration)
        # if we accidentally slept for 59 seconds, sleep some more
        while datetime.datetime.now().minute == now.minute:
            sleep(0.5)


def run_now(args: argparse.Namespace):
    """Run all matching jobs immediately, ignoring their schedules"""
    jobs = find_jobs(args)
    for job in jobs:
        job.spawn(wait=True)


def dump(args: argparse.Namespace):
    """Dump parsed jobs and exit"""
    jobs = find_jobs(args)
    for job in jobs:
        print(str(job))


def main(argv: list[str]):
    parser = argparse.ArgumentParser(description="Kissycron")
    parser.add_argument("--file", type=Path, help="Parse crontab file")
    parser.add_argument("--docker", action="store_true", help="Parse docker labels")
    parser.add_argument("--match", type=str, help="Only process jobs with matching ID")
    parser.add_argument("--verbose", "-v", action="store_true")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.add_parser("run-cron", help="Run cron daemon (default)")
    subparsers.add_parser("run-now", help="Run all matching jobs immediately")
    subparsers.add_parser("dump", help="Dump parsed jobs and exit")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
    )

    if args.file and not os.path.isfile(args.file):
        log.error(f"Crontab file '{args.file}' does not exist.")
        sys.exit(1)

    # Default to run-cron if no command specified
    command = args.command or "run-cron"

    if command == "run-cron":
        run_cron(args)
    elif command == "run-now":
        run_now(args)
    elif command == "dump":
        dump(args)


if __name__ == "__main__":
    main(sys.argv[1:])
