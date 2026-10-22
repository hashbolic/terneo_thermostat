"""Recovery tests; no requests are sent to real thermostats."""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
import requests

from custom_components.terneo.thermostat import Thermostat


STATUS = {"t.1": "327", "t.5": "320", "m.1": "3", "f.0": "0", "f.16": "0"}


def response(data=STATUS, status=200):
    result = requests.Response()
    result.status_code = status
    result.json = Mock(return_value=copy.deepcopy(data))
    return result


@pytest.fixture
def transport(monkeypatch):
    get = Mock(return_value=response())
    post = Mock(return_value=response())
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr("custom_components.terneo.thermostat.time.sleep", lambda _: None)
    return get, post


def test_offline_startup_recovers_on_later_poll(transport):
    get, post = transport
    get.side_effect = requests.Timeout("offline")
    post.side_effect = [requests.Timeout("offline"), response()]
    device = Thermostat("test", "example.invalid")
    device.update()
    assert not device.available
    assert (device.temperature, device.setpoint, device.mode, device.state) == (None,) * 4
    assert post.call_count == 1  # Reading properties must not trigger extra requests.
    device.update()
    assert device.available
    assert (device.temperature, device.setpoint, device.mode, device.state) == (20.4375, 20, 3, False)


@pytest.mark.parametrize("bad", [
    response({"status": "timeout"}), response({}, 503), response([]),
    response({}), response({**STATUS, "t.1": "NaN"}),
    response({**STATUS, "m.1": None}), response({**STATUS, "f.0": "invalid"}),
    response({**STATUS, "t.5": "Infinity"}),
])
def test_failed_poll_keeps_last_snapshot_unavailable_then_recovers(transport, bad):
    _, post = transport
    device = Thermostat("test", "example.invalid")
    device.update()
    previous = (device.temperature, device.setpoint, device.mode, device.state)
    post.return_value = bad
    device.update()
    assert not device.available
    assert (device.temperature, device.setpoint, device.mode, device.state) == previous
    post.return_value = response({**STATUS, "t.1": "336"})
    device.update()
    assert device.available
    assert device.temperature == 21


def test_invalid_json_marks_unavailable(transport):
    _, post = transport
    device = Thermostat("test", "example.invalid")
    device.update()
    post.return_value.json.side_effect = ValueError("bad JSON")
    device.update()
    assert not device.available


def test_legacy_power_query_failure_does_not_report_off(transport):
    _, post = transport
    device = Thermostat("test", "example.invalid")
    device.update()
    legacy = {key: val for key, val in STATUS.items() if key != "f.16"}
    post.side_effect = [response(legacy), response({"status": "timeout"}),
                        response(legacy), response({"par": [[125, 7, "0"]]})]
    device.update()
    assert not device.available
    assert device.mode == 3
    device.update()
    assert device.available and device.mode == 3


def test_successful_command_does_not_revive_stale_snapshot(transport):
    _, post = transport
    device = Thermostat("test", "example.invalid")
    device.update()
    post.return_value = response({"status": "timeout"})
    device.update()
    post.return_value = response({"success": "true"})
    device.turn_on()
    assert not device.available


def test_timeout_does_not_mutate_command_or_retry_write(transport):
    _, post = transport
    device = Thermostat("test", "example.invalid")
    post.return_value = response({"status": "timeout"})
    command = {"sn": "test", "par": [[125, 7, "0"]]}
    original = copy.deepcopy(command)
    assert device.post(json=command) is False
    assert command == original
    assert post.call_count == 1
    assert post.call_args.kwargs["timeout"] == 5


def test_valid_basic_auth_pair(transport):
    device = Thermostat("test", "example.invalid", username="user", password="pass")
    assert device.auth.username == "user"


@pytest.mark.parametrize("username,password", [("user", None), (None, "pass")])
def test_partial_auth_rejected(transport, username, password):
    with pytest.raises(ValueError):
        Thermostat("test", "example.invalid", username=username, password=password)


def test_poll_and_write_do_not_overlap(transport):
    _, post = transport
    device = Thermostat("test", "example.invalid")
    poll_entered = Event()
    write_attempted = Event()
    write_entered = Event()

    def send(url, **kwargs):
        if kwargs["json"].get("cmd") == 4:
            poll_entered.set()
            assert write_attempted.wait(2)
            assert not write_entered.wait(0.1), "write overlapped the status request"
            return response()
        write_entered.set()
        return response({"success": "true"})

    def write():
        assert poll_entered.wait(2)
        write_attempted.set()
        return device.turn_on()

    post.side_effect = send
    with ThreadPoolExecutor(max_workers=2) as executor:
        poll = executor.submit(device.update)
        command = executor.submit(write)
        poll.result(timeout=5)
        assert command.result(timeout=5) == {"success": "true"}
    assert device.available


@pytest.mark.parametrize("mode,power,expected", [(0, "0", 0), (3, "0", 3), (4, "0", 4), (3, "1", -1)])
def test_existing_mode_and_temperature_semantics(transport, mode, power, expected):
    _, post = transport
    post.return_value = response({**STATUS, "m.1": str(mode), "f.16": power, "f.0": "1"})
    device = Thermostat("test", "example.invalid")
    device.update()
    assert device.available
    assert device.mode == expected
    assert device.temperature == 327 / 16
    assert device.setpoint == 20
    assert device.state is True
