import threading
from dataclasses import dataclass, field


@dataclass
class RunQueueState:
    run_queue: list = field(default_factory=list)
    runs: dict = field(default_factory=dict)
    queue_lock: threading.Lock = field(default_factory=threading.Lock)
    worker_busy: list = field(default_factory=lambda: [False])
