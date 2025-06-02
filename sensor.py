import logging
from datetime import timedelta
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_SLAVE_ID

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave_id = entry.data[CONF_SLAVE_ID]

    client = AsyncModbusTcpClient(host, port=port)
    await client.connect()

    sensors = [
        EVLinkPowerSensor(client, slave_id),
        EVLinkEnergySensor(client, slave_id),
    ]

    async_add_entities(sensors)

    async def async_update_sensors(event_time):
        for sensor in sensors:
            await sensor.async_update()

    async_track_time_interval(hass, async_update_sensors, SCAN_INTERVAL)

class EVLinkPowerSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Ladeleistung"
        self._attr_unique_id = "evlink_power"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_state_class = "measurement"
        self._attr_device_class = "power"
        self._attr_device_info = {
            "identifiers": {("evlink_modbus", "evlink_device")},
            "name": "Schneider EVlink Pro AC",
            "manufacturer": "Schneider Electric",
            "model": "EVlink Pro AC",
        }
        self._state = None

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        try:
            rr = await self._client.read_holding_registers(3059, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading power")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value / 1000, 2)
            _LOGGER.debug(f"Power read from Modbus: {self._state} kW")
        except Exception as e:
            _LOGGER.exception(f"Exception during power read: {e}")

class EVLinkEnergySensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Energie total"
        self._attr_unique_id = "evlink_energy_total"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = "total_increasing"
        self._attr_device_class = "energy"
        self._attr_device_info = {
            "identifiers": {("evlink_modbus", "evlink_device")},
            "name": "Schneider EVlink Pro AC",
            "manufacturer": "Schneider Electric",
            "model": "EVlink Pro AC",
        }
        self._state = None

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        try:
            rr = await self._client.read_holding_registers(3203, 4, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading total energy")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_64bit_uint()
            self._state = round(value / 1000, 2)
            _LOGGER.debug(f"Total energy read from Modbus: {self._state} kWh")
        except Exception as e:
            _LOGGER.exception(f"Exception during energy read: {e}")