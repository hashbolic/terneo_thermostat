import math
import requests
import logging
import time
from threading import RLock

from requests.auth import HTTPBasicAuth

_LOGGER = logging.getLogger(__name__)


class Thermostat:
    """
    A class for interacting with the Terneo Thermostat's HTTP API.
    Parameters
    ----------
    serialnumber: `str`
        Serial Number of device
    host : `str`
        Hostname or IP address.
    port : `int` (optional)
        The port of the web server.
    username : `str` (optional)
        The username for HTTP auth.
    password : `str` (optional)
        The password for the HTTP auth.
    """

    def __init__(self, serialnumber, host, port=80, username=None, password=None):
        if bool(username) != bool(password):
            raise ValueError(
                "Username and Password must both be specified, if either are specified."
            )
        elif username or password:
            self.auth = HTTPBasicAuth(username, password)
        else:
            self.auth = None

        self.sn = serialnumber

        self._base_url = "http://{}:{}/{{endpoint}}.cgi".format(host, port)
        self._setpoint = None
        self._temperature = None
        self._mode = None
        self._state = None
        self._available = False

        self._request_lock = RLock()
        self._last_request = time.monotonic() - 1
        # Register offline devices too; HA polling will retry when they return.

    def _get_url(self, endpoint):
        return self._base_url.format(endpoint=endpoint)

    def get(self, endpoint, **kwargs):
        """
        Perform a GET request
        Parameters
        ----------
        endpoint : `str`
            The endpoint to send the request to, will have 'cgi' appended to it.
        kwargs : `dict`
            All other kwargs are passed to `requests.get`
        Returns
        -------
        response : `requests.Response`
            The result of the request.
        """
        kwergs = {'auth': self.auth, 'timeout': 5}
        kwergs.update(kwargs)

        r = requests.get(self._get_url(endpoint), **kwergs)
        return r

    def post(self, endpoint='api', **kwargs):
        """
        Perform a POST request
        Parameters
        ----------
        endpoint : `str`
            The endpoint to send the request to, will have 'cgi' appended to it.
        kwargs : `dict`
            All other kwargs are passed to `requests.post`
        Returns
        -------
        response : `requests.Response`
            The result of the request.
        """
        kwergs = {'auth': self.auth, 'timeout': 5}
        kwergs.update(kwargs)
        with self._request_lock:
            delay = 1 - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            try:
                r = requests.post(self._get_url(endpoint), **kwergs)
                r.raise_for_status()
                content = r.json()
                if not isinstance(content, dict) or content.get('status') == 'timeout':
                    raise ValueError("Invalid response or device timeout")
            except (requests.RequestException, ValueError) as err:
                self._available = False
                _LOGGER.warning("Terneo request failed at %s: %s", self._get_url(endpoint), err)
                return False
            finally:
                self._last_request = time.monotonic()
            return content

    def status(self):
        """
        Get the status dictionary from the thermostat
        """
        r = self.post(json={"cmd": 4, "sn": self.sn})
        if r is False:
            # A transient disconnect may interrupt telemetry; never retry writes.
            r = self.post(json={"cmd": 4, "sn": self.sn})
        return r

    def is_on(self):
        """
        getting power on/off for firmware 2.3
        :return: bool
        """
        r = self.post(json={"cmd": 1, "sn": self.sn})
        if r and isinstance(r.get('par'), list):
            for a in r['par']:
                if isinstance(a, list) and len(a) >= 3 and a[0] == 125:
                    if str(a[2]) in ("0", "1"):
                        return str(a[2]) == "0"
        raise ValueError("Missing or invalid power state")

    @property
    def temperature(self):
        """
        Current value of the temperature sensor in C
        """
        return self._temperature

    @staticmethod
    def get_temperature(data):
        return float(data['t.1']) / 16

    @property
    def setpoint(self):
        """
        Current thermostat setpoint in C
        """
        return self._setpoint

    @setpoint.setter
    def setpoint(self, val):
        setpoint = str(val)
        self.post(json=dict(sn=self.sn, par=[[125, 7, "0"], [2, 2, "1"], [5, 1, setpoint]]))

    @staticmethod
    def get_setpoint(data):
        return float(data['t.5']) / 16

    @property
    def mode(self):
        """
        Returns the current mode of the thermostat.
        Returns
        -------
        mode : `int`
            `0` for schedule mode, `3` for manual mode and `4` for away mode.
        """
        return self._mode

    def get_mode(self, data):
        if 'f.16' in data:  # in firmware 2.4 was added new flag for power off/on
            is_on = int(data['f.16']) == 0
        else:
            is_on = self.is_on()

        if not is_on:
            return -1
        else:
            return int(data['m.1'])

    @mode.setter
    def mode(self, val):
        val = int(val)
        if val not in [0, 1]:
            raise ValueError("mode must be either 0,1")

        self.post(json=dict(sn=self.sn, par=[[125, 7, "0"], [2, 2, str(val)]]))

    @property
    def state(self):
        """
        Current state of the relay.
        Returns
        -------
        state : `bool`
            returns `True` if the relay is on and `False` if the relay is off.
        """
        return self._state

    @property
    def available(self):
        return self._available
    
    @staticmethod
    def get_state(data):
        return int(data['f.0']) == 1

    def turn_on(self):
        return self.post(json=dict(sn=self.sn, par=[[125, 7, "0"]]))

    def turn_off(self):
        return self.post(json=dict(sn=self.sn, par=[[125, 7, "1"]]))

    def update(self):
        with self._request_lock:
            data = self.status()
            try:
                if not data:
                    self._available = False
                    return
                setpoint = self.get_setpoint(data)
                temperature = self.get_temperature(data)
                if not math.isfinite(setpoint) or not math.isfinite(temperature):
                    raise ValueError("Non-finite temperature")
                mode = self.get_mode(data)
                state = self.get_state(data)
            except (KeyError, TypeError, ValueError, OverflowError) as err:
                self._available = False
                _LOGGER.warning("Invalid Terneo status at %s: %s", self._get_url('api'), err)
                return
            self._setpoint = setpoint
            self._temperature = temperature
            self._mode = mode
            self._state = state
            self._available = True
