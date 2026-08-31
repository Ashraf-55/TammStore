import os
import job_handlers  # registers durable handlers
from jobs import worker_loop

if __name__ == "__main__":
    worker_loop(float(os.environ.get("CODELA_JOB_POLL_SECONDS", "1")))
