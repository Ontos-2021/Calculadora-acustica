import logging
import signal
import threading

from api.database import init_db
from api.jobs import run_worker


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    init_db()
    logging.getLogger(__name__).info("worker started")
    run_worker(stop_event=stop_event)


if __name__ == "__main__":
    main()
