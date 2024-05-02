import logging
import time
from contextlib import contextmanager
from typing import Iterator, Optional, Sequence


def generate_wire(*args: bytes) -> Iterator[bytes]:
    yield b"*%d" % len(args)
    for arg in args:
        yield b"$%d" % len(arg)
        yield arg


def construct_command(*args: bytes) -> bytes:
    return b"\r\n".join(generate_wire(*args)) + b"\r\n"


@contextmanager
def time_it(name: str, iterations: Optional[int] = None) -> Iterator[None]:
    start = time.perf_counter_ns()
    yield None
    elapsed = time.perf_counter_ns() - start
    if iterations:
        print(
            f"[{name}] {elapsed / iterations / 1000:.1f}µs/it, total: {elapsed * 1e-6:.1f}ms"
        )
    else:
        print(f"[{name}] {elapsed * 1e-3:.1f}µs")
