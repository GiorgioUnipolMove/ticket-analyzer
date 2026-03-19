import time


class RateLimiter:
    """Sliding window rate limiter per rispettare i limiti API."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.timestamps: list[float] = []

    def wait_if_needed(self):
        if self.max_per_minute >= 999:
            return

        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < 60]

        if len(self.timestamps) >= self.max_per_minute:
            wait_time = 60 - (now - self.timestamps[0]) + 0.5
            if wait_time > 0:
                print(f"    ⏳ Rate limit: attendo {wait_time:.0f}s...")
                time.sleep(wait_time)

        self.timestamps.append(time.time())
