import logging
from datetime import timedelta
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_SLAVE_ID

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


# Fehler Mapping nach Handbuch und EVCC
FAULT_MAP = {
    0: "Kein Fehler",
    1: "Interner Fehler",
    2: "Fehler Erdung",
    3: "Fehler Überspannung",
    4: "Fehler Unterspannung",
    5: "Fehler Überstrom",
    6: "Fehler Temperatur",
    7: "Fehler Kommunikation",
    8: "Fehler FI",
    9: "Fehler Relais",
    10: "Fehler Lüfter",
    11: "Fehler Verriegelung",
    12: "Fehler Authentifizierung",
    13: "Fehler RFID",
    14: "Fehler Zähler",
    15: "Fehler OCPP",
    65535: "Ungültig/Fehler"
}


# Last Stop Cause Mapping nach Handbuch Tabelle 34
LAST_STOP_CAUSE_MAP = {
    0: "Nicht gestoppt / Unbekannt",
    1: "Vom Benutzer gestoppt",
    2: "Vom Fahrzeug gestoppt",
    3: "Fehler",
    4: "Energie-Limit erreicht",
    5: "Zeit-Limit erreicht",
    6: "Extern gestoppt",
    7: "Not-Aus",
    8: "Kommunikationsfehler",
    9: "Lastmanagement",
    65535: "Ungültig/Fehler"
}

OCPP_STATUS_MAP = {
    0: "Unbekannt",
    1: "Verfügbar",
    2: "Vorbereitet",
    3: "Besetzt",
    4: "Fehler",
    5: "Fahrzeug verbunden",
    6: "Fahrzeug verbunden",
    7: "Wartung",
    8: "Abgeschlossen",
    9: "Authentifizierung läuft",
    10: "Authentifizierung fehlgeschlagen",
    11: "Remote gestoppt",
    12: "Remote gestartet",
    65535: "Ungültig/Fehler"
}


SCHNEIDER_REG_EV_STATE_MAP = {
    0: "Kein Fahrzeug verbunden",
    1: "Kein Fahrzeug verbunden",  # Optional: Falls du State F auch als "kein Fahrzeug" sehen willst, sonst entferne diese Zeile
    2: "Fahrzeug verbunden",
    3: "Fahrzeug verbunden",
    4: "Fahrzeug verbunden",
    5: "Fahrzeug verbunden",
    6: "Fahrzeug lädt",
    7: "Fahrzeug lädt",
    8: "Fahrzeug lädt",
    9: "Fahrzeug lädt",
    10: "Fehler/ungültig",
    11: "Fehler/ungültig"
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave_id = entry.data[CONF_SLAVE_ID]

    client = AsyncModbusTcpClient(host, port=port)
    await client.connect()

    sensors = [
        EVLinkPowerSensor(client, slave_id),
        EVLinkEnergySensor(client, slave_id),
        EVLinkEnabledSensor(client, slave_id),
        EVLinkFaultSensor(client, slave_id),
        EVLinkCurrentL1Sensor(client, slave_id),
        EVLinkCurrentL2Sensor(client, slave_id),
        EVLinkCurrentL3Sensor(client, slave_id),
        EVLinkVoltageL1Sensor(client, slave_id),
        EVLinkVoltageL2Sensor(client, slave_id),
        EVLinkVoltageL3Sensor(client, slave_id),
        EVLinkCurrentSumSensor(client, slave_id),
        EVLinkOcppStatusSensor(client, slave_id),
        EVLinkChargingTimeSensor(client, slave_id),
        EVLinkSessionChargingTimeSensor(client, slave_id),
        EVLinkLastStopCauseSensor(client, slave_id),
        SchneiderRegEvStateSensor(client, slave_id),  # <-- Hier hinzugefügt
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
        self._attr_native_unit_of_measurement = UnitOfPower.WATT  # Anpassung auf Watt
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
            self._state = round(value * 1000, 2)  # Keine Division mehr, da jetzt Watt
            _LOGGER.debug(f"Power read from Modbus: {self._state} W")
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



class EVLinkFaultSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Fehlerstatus"
        self._attr_unique_id = "evlink_fault"
        self._attr_native_unit_of_measurement = None
        self._attr_device_info = {
            "identifiers": {("evlink_modbus", "evlink_device")},
            "name": "Schneider EVlink Pro AC",
            "manufacturer": "Schneider Electric",
            "model": "EVlink Pro AC",
        }
        self._state = None

    @property
    def native_value(self):
        return FAULT_MAP.get(self._state, self._state)

    async def async_update(self):
        try:
            rr = await self._client.read_holding_registers(3041, 1, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading fault")
                return
            self._state = rr.registers[0]
            _LOGGER.debug(f"Fault read from Modbus: {self._state}")
        except Exception as e:
            _LOGGER.exception(f"Exception during fault read: {e}")

class EVLinkCurrentL1Sensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Strom L1"
        self._attr_unique_id = "evlink_current_l1"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = "current"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(2999, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading current L1")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 2)
        except Exception as e:
            _LOGGER.exception(f"Exception during current L1 read: {e}")

class EVLinkCurrentL2Sensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Strom L2"
        self._attr_unique_id = "evlink_current_l2"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = "current"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(3001, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading current L2")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 2)
        except Exception as e:
            _LOGGER.exception(f"Exception during current L2 read: {e}")

class EVLinkCurrentL3Sensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Strom L3"
        self._attr_unique_id = "evlink_current_l3"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = "current"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(3003, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading current L3")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 2)
        except Exception as e:
            _LOGGER.exception(f"Exception during current L3 read: {e}")

class EVLinkCurrentSumSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Gesamtstrom"
        self._attr_unique_id = "evlink_current_sum"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = "current"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(3005, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading current sum")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 2)
        except Exception as e:
            _LOGGER.exception(f"Exception during current sum read: {e}")

class EVLinkVoltageL1Sensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Spannung L1"
        self._attr_unique_id = "evlink_voltage_l1"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = "voltage"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(3027, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading voltage L1")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 1)
        except Exception as e:
            _LOGGER.exception(f"Exception during voltage L1 read: {e}")

class EVLinkVoltageL2Sensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Spannung L2"
        self._attr_unique_id = "evlink_voltage_l2"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = "voltage"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(3029, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading voltage L2")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 1)
        except Exception as e:
            _LOGGER.exception(f"Exception during voltage L2 read: {e}")

class EVLinkVoltageL3Sensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Spannung L3"
        self._attr_unique_id = "evlink_voltage_l3"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = "voltage"
        self._attr_state_class = "measurement"
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
            rr = await self._client.read_holding_registers(3031, 2, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading voltage L3")
                return
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Little)
            value = decoder.decode_32bit_float()
            self._state = round(value, 1)
        except Exception as e:
            _LOGGER.exception(f"Exception during voltage L3 read: {e}")

class EVLinkOcppStatusSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink OCPP Status"
        self._attr_unique_id = "evlink_ocpp_status"
        self._attr_native_unit_of_measurement = None
        self._attr_device_info = {
            "identifiers": {("evlink_modbus", "evlink_device")},
            "name": "Schneider EVlink Pro AC",
            "manufacturer": "Schneider Electric",
            "model": "EVlink Pro AC",
        }
        self._state = None

    @property
    def native_value(self):
        return OCPP_STATUS_MAP.get(self._state, self._state)

    async def async_update(self):
        try:
            rr = await self._client.read_holding_registers(150, 1, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading OCPP status")
                return
            self._state = rr.registers[0]
        except Exception as e:
            _LOGGER.exception(f"Exception during OCPP status read: {e}")


class EVLinkChargingTimeSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Charging Time"
        self._attr_unique_id = "evlink_charging_time"
        self._attr_native_unit_of_measurement = "s"
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
            rr = await self._client.read_holding_registers(4007, 1, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading charging time")
                return
            self._state = rr.registers[0]
        except Exception as e:
            _LOGGER.exception(f"Exception during charging time read: {e}")

class EVLinkSessionChargingTimeSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Session Charging Time"
        self._attr_unique_id = "evlink_session_charging_time"
        self._attr_native_unit_of_measurement = "s"
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
            rr = await self._client.read_holding_registers(4009, 1, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading session charging time")
                return
            self._state = rr.registers[0]
        except Exception as e:
            _LOGGER.exception(f"Exception during session charging time read: {e}")

class EVLinkLastStopCauseSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Last Stop Cause"
        self._attr_unique_id = "evlink_last_stop_cause"
        self._attr_native_unit_of_measurement = None
        self._attr_device_info = {
            "identifiers": {("evlink_modbus", "evlink_device")},
            "name": "Schneider EVlink Pro AC",
            "manufacturer": "Schneider Electric",
            "model": "EVlink Pro AC",
        }
        self._state = None

    @property
    def native_value(self):
        return LAST_STOP_CAUSE_MAP.get(self._state, self._state)

    async def async_update(self):
        try:
            rr = await self._client.read_holding_registers(4011, 1, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading last stop cause")
                return
            self._state = rr.registers[0]
        except Exception as e:
            _LOGGER.exception(f"Exception during last stop cause read: {e}")

class SchneiderRegEvStateSensor(SensorEntity):
    def __init__(self, client, slave_id):
        self._client = client
        self._slave_id = slave_id
        self._attr_name = "EVLink Fahrzeugstatus"
        self._attr_unique_id = "schneider_reg_ev_state"
        self._attr_native_unit_of_measurement = None
        self._attr_device_info = {
            "identifiers": {("evlink_modbus", "evlink_device")},
            "name": "Schneider EVlink Pro AC",
            "manufacturer": "Schneider Electric",
            "model": "EVlink Pro AC",
        }
        self._state = None

    @property
    def native_value(self):
        return SCHNEIDER_REG_EV_STATE_MAP.get(self._state, f"Unbekannt ({self._state})")

    async def async_update(self):
        try:
            rr = await self._client.read_holding_registers(1, 1, slave=self._slave_id)
            if rr.isError():
                _LOGGER.error("Modbus error reading SchneiderRegEvState")
                return
            self._state = rr.registers[0]
            _LOGGER.debug(f"SchneiderRegEvState read from Modbus: {self._state}")
        except Exception as e:
            _LOGGER.exception(f"Exception during SchneiderRegEvState read: {e}")