from datetime import datetime as RealDateTime
from types import SimpleNamespace
import threading

import pytest

from farmbot import bluestacks, gui, instances
from test_farm_worker import world, worker, eventually


@pytest.fixture
def clock(monkeypatch):
    class Clock(RealDateTime):
        hour_now = 23
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 24, cls.hour_now, 0, tzinfo=tz)
    monkeypatch.setattr(gui, "datetime", Clock)
    return Clock


def outside_status(window):
    return any(kind == "status" and "Outside active hours" in str(value)
               for kind, value in list(window.events.queue))


def test_slot_wait_crosses_midnight_then_resumes_at_eight(world, clock):
    queue = instances.FarmQueue(1)
    assert queue.acquire(99, "occupied", threading.Event())
    hub = SimpleNamespace(farm_queue=queue)
    window, stop, thread = worker(1, hub, world, hours=list(range(8, 24)))
    eventually(lambda: queue.waiting == [1])
    clock.hour_now = 0
    queue.release(99)
    eventually(lambda: outside_status(window) or world.opened)
    assert not world.opened
    assert not world.opened and not queue.active and not queue.held
    clock.hour_now = 8
    eventually(lambda: world.resident == {"instance-1"})
    world.gate.set()
    thread.join(3)
    assert not thread.is_alive()
    assert world.opened == ["instance-1"]
    assert not world.resident and not queue.active and not queue.held


def test_stop_while_outside_hours_never_reserves_or_opens(world, clock):
    clock.hour_now = 0
    queue = instances.FarmQueue(3)
    window, stop, thread = worker(1, SimpleNamespace(farm_queue=queue), world,
                                  hours=list(range(8, 24)))
    eventually(lambda: outside_status(window) or world.opened)
    assert not world.opened
    stop.set()
    thread.join(3)
    assert not thread.is_alive()
    assert not world.opened and not queue.active and not queue.waiting and not queue.held


def test_midnight_during_startup_preparation_releases_slot(world, clock, monkeypatch):
    real_open = bluestacks.open_device
    def prepare(cfg, **kwargs):
        clock.hour_now = 0
        return real_open(cfg, **kwargs)
    monkeypatch.setattr(bluestacks, "open_device", prepare)
    queue = instances.FarmQueue(3)
    window, stop, thread = worker(1, SimpleNamespace(farm_queue=queue), world,
                                  hours=list(range(8, 24)))
    eventually(lambda: outside_status(window) or world.opened)
    assert not world.opened
    assert not world.opened and not queue.active and not queue.held
    clock.hour_now = 8
    eventually(lambda: world.resident == {"instance-1"})
    world.gate.set()
    thread.join(3)
    assert not thread.is_alive()
    assert world.opened == ["instance-1"] and not world.resident
