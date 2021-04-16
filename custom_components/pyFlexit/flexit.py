"""Asynchronous Python client for Flexit."""
import asyncio
import socket
import logging
import urllib.parse
from datetime import date, timedelta

from typing import Any, Optional, Dict

import aiohttp
import async_timeout
from yarl import URL

from .__version__ import __version__
from .exceptions import FlexitConnectionError, FlexitError
from .models import Token, FlexitInfo, DeviceInfo
from .const import (
    VENTILATION_MODE_PATH,
    VENTILATION_MODE_PUT_PATH,
    OUTSIDE_AIR_TEMPERATURE_PATH,
    SUPPLY_AIR_TEMPERATURE_PATH,
    EXTRACT_AIR_TEMPERATURE_PATH,
    EXHAUST_AIR_TEMPERATURE_PATH,
    HOME_AIR_TEMPERATURE_PATH,
    AWAY_AIR_TEMPERATURE_PATH,
    FILTER_STATE_PATH,
    FILTER_TIME_FOR_EXCHANGE_PATH,
    ROOM_TEMPERATURE_PATH,
    ELECTRIC_HEATER_PATH,
    SCHEME,
    HOST,
    TOKEN_PATH,
    DATAPOINTS_PATH,
    APPLICATION_SOFTWARE_VERSION_PATH,
    DEVICE_DESCRIPTION_PATH,
    MODEL_NAME_PATH,
    MODEL_INFORMATION_PATH,
    SERIAL_NUMBER_PATH,
    FIRMWARE_REVISION_PATH,
    OFFLINE_ONLINE_PATH,
    SYSTEM_STATUS_PATH,
    LAST_RESTART_REASON_PATH,
)

_LOGGER = logging.getLogger(__name__)

class Flexit:
    """Main class for handling connections with an Flexit."""

    def __init__(
        self, 
        username, 
        password, 
        api_key,
        loop,
        session: aiohttp.client.ClientSession = None,
    ) -> None:
        """Initialize connection with the Flexit."""
        self._loop = loop
        self._session = session
        self._close_session:bool = False
        self.request_timeout:int = 8
        self.username:str = username
        self.password:str = password
        self.api_key:str = api_key
        self.token:str = ""
        self.token_refreshdate = date.today()
        self.data:dict = {}
        self.device_info:dict = {}

    def get_token_body(self):
        return "grant_type=password&username=" + self.username + "&password=" + self.password 

    def get_token_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-us",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Flexit%20GO/2.0.6 CFNetwork/1128.0.1 Darwin/19.6.0",
            "Ocp-Apim-Subscription-Key": self.api_key
        }
    
    def get_headers(self) -> dict:
        headers = self.get_token_headers()
        headers['Authorization'] = "Bearer " + self.token
        return headers

    async def _generic_request(
        self, 
        method: str = "GET",
        url: str = "",
        body = None,
    ) -> Any:

        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True

        try:
            with async_timeout.timeout(self.request_timeout, loop=self._loop):

                if method == "POST":
                    response = await self._post_request(url, body)
                elif method == "PUT":
                    response = await self._put_request(url, body) 
                else:
                    response = await self._get_request(url)

                response.raise_for_status()

        except asyncio.TimeoutError as exception:
            raise FlexitConnectionError(
                "Timeout occurred while connecting to Flexit device"
            ) from exception

        except (
            aiohttp.ClientError,
            aiohttp.ClientResponseError,
            socket.gaierror,
        ) as exception:
            raise FlexitConnectionError(
                "Error occurred while communicating with Flexit device"
            ) from exception

        content_type = response.headers.get("Content-Type", "")

        if "application/json" not in content_type:
            text = await response.text()
            raise FlexitError(
                "Unexpected response from the Flexit device",
                {"Content-Type": content_type, "response": text},
            )

        return await response.json()

    async def _get_request(self, uri):
        return await self._session.request(
            method="GET", 
            url=URL.build(
                scheme=SCHEME, 
                host=HOST,
            ).join(URL(uri)), 
            headers=self.get_headers(),
        ) 

    async def _put_request(self, uri, body):
        return await self._session.request(
            method="PUT", 
            url=URL.build(
                scheme=SCHEME, 
                host=HOST,
            ).join(URL(uri)), 
            data=body,
            headers=self.get_headers(),
        )

    async def _post_request(self, uri, body): 
        return await self._session.request(
            method="POST", 
            url=URL.build(
                scheme=SCHEME, 
                host=HOST,
            ).join(URL(uri)), 
            data=body,
            headers=self.get_token_headers(),
        )

    async def token_request( self ) -> Any:
        return await self._generic_request(
            method="POST",
            url=TOKEN_PATH,
            body=self.get_token_body()
        )

    async def set_token(self) -> None: 
        if self.token_refreshdate == date.today():
            _LOGGER.debug( "Updating flexit token" )
            
            response = await self.token_request()
            self.token = response["access_token"]
            self.token_refreshdate = date.today() + timedelta(days = 1)

    def put_body(self, value: str) -> str:
        return '{"Value": "' + value + '"}'

    def get_escaped_datapoints_url(self, id: str) -> str:
        return DATAPOINTS_PATH + urllib.parse.quote(id)

    async def update_data(self) -> None:
        filterPath = "/DataPoints/Values?filterId="
        pathVariables = f"""[
        {{"DataPoints":"{VENTILATION_MODE_PATH}"}},
        {{"DataPoints":"{OUTSIDE_AIR_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{SUPPLY_AIR_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{EXTRACT_AIR_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{EXHAUST_AIR_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{HOME_AIR_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{AWAY_AIR_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{FILTER_STATE_PATH}"}},
        {{"DataPoints":"{FILTER_TIME_FOR_EXCHANGE_PATH}"}},
        {{"DataPoints":"{ROOM_TEMPERATURE_PATH}"}},
        {{"DataPoints":"{ELECTRIC_HEATER_PATH}"}}]"""

        response = await self._generic_request( 
            method="GET", 
            url=filterPath + urllib.parse.quote(pathVariables) )
        self.data = FlexitInfo.format_dict( response )

    async def update_device_info(self) -> None:
        filterPath = "/DataPoints/Values?filterId="
        pathVariables = f"""[
        {{"DataPoints":"{APPLICATION_SOFTWARE_VERSION_PATH}"}},
        {{"DataPoints":"{DEVICE_DESCRIPTION_PATH}"}},
        {{"DataPoints":"{MODEL_NAME_PATH}"}},
        {{"DataPoints":"{MODEL_INFORMATION_PATH}"}},
        {{"DataPoints":"{SERIAL_NUMBER_PATH}"}},
        {{"DataPoints":"{FIRMWARE_REVISION_PATH}"}},
        {{"DataPoints":"{OFFLINE_ONLINE_PATH}"}},
        {{"DataPoints":"{SYSTEM_STATUS_PATH}"}},
        {{"DataPoints":"{LAST_RESTART_REASON_PATH}"}}]"""

        response = await self._generic_request( 
            method="GET", 
            url=filterPath + urllib.parse.quote(pathVariables) )
        self.device_info = DeviceInfo.format_dict( response )

    async def set_home_temp(self, temp) -> None:
        response = await self._generic_request(
            method="PUT",
            url=self.get_escaped_datapoints_url( HOME_AIR_TEMPERATURE_PATH ), 
            body=self.put_body(temp)
        )

        if response["stateTexts"][HOME_AIR_TEMPERATURE_PATH] == 'Success':
            self.data["home_air_temperature"] = float(temp)

    async def set_away_temp(self, temp) -> None:
        response = await self._generic_request(
            method="PUT",
            url=self.get_escaped_datapoints_url( AWAY_AIR_TEMPERATURE_PATH ), 
            body=self.put_body(temp)
        )
        _LOGGER.debug("set_away temp response %s", response)
        if response["stateTexts"][AWAY_AIR_TEMPERATURE_PATH] == 'Success':
            self.data["away_air_temperature"] = float(temp)

    async def set_mode(self, mode) -> None:
        switcher = { "Home": 0, "Away": 2, "High": 4 }
        mode_int = switcher.get(mode, -1)
        if mode_int == -1:
            return

        _LOGGER.debug("Setting ventilation-mode to %s: %s", mode, mode_int)
        response = await self._generic_request(
            method="PUT",
            url=self.get_escaped_datapoints_url( VENTILATION_MODE_PUT_PATH ), 
            body=self.put_body(str(mode_int))
        )
        _LOGGER.debug("set_mode response %s", response)
        if response["stateTexts"][VENTILATION_MODE_PUT_PATH] == 'Success':
            self.data["ventilation_mode"] = mode
    
    async def set_heater_state(self, state) -> None:
        switcher = { "on": 1, "off": 0 }
        state_int = switcher.get(state, -1)
        if state_int == -1:
            return

        _LOGGER.debug("Setting heater state to %s: %s", state, state_int)
        response = await self._generic_request(
            method="PUT",
            url=self.get_escaped_datapoints_url( ELECTRIC_HEATER_PATH ), 
            body=self.put_body(str(state_int))
        )
        _LOGGER.debug("set_heater state response %s", response)
        if response["stateTexts"][ELECTRIC_HEATER_PATH] == 'Success':
            self.data["electric_heater"] = state


    async def close(self) -> None:
        """Close open client session."""
        if self._session and self._close_session:
            await self._session.close()

    async def __aenter__(self) -> "Flexit":
        """Async enter."""
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Async exit."""
        await self.close()