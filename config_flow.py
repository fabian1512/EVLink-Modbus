from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_SLAVE_ID, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SLAVE_ID

DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
})

class EVLinkModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="EVLink Modbus", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )