from __future__ import annotations

from rq import Worker

from .db import Base, ENGINE
from .queueing import get_redis


def main() -> int:
    Base.metadata.create_all(bind=ENGINE)
    worker = Worker(["default"], connection=get_redis())
    worker.work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
