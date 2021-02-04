import logging
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
# Import the device class from the component that you want to support
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, PLATFORM_SCHEMA, Light)
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    host = config[CONF_HOST]
    lights = json.loads(requests.get(host))
    add_entities(SolarpathLight(light, host) for light in lights)

class SolarpathLight(Light):
    def __init__(self, light, host):
        self._light = light
        self._host = host
        self._device_eui = light["device_eui"]

    @property
    def name(self):
        return self._light["device_eui"]

    @property
    def brightness(self):
        return None
    
    def rgb_color(self):
        return None

    def is_on(self):
        return self._light["light_on"]

    def turn_on(self, **kwargs):
        self._light["light_on"] = 1
        requests.post(self._host, json.dumps(self._light))

    def turn_off(self, **kwargs):
        self._light["light_on"] = 0
        requests.post(self._host, json.dumps(self._light))

    def update(self):
        lights = json.loads(requests.get(self._host))
        for light in lights:
            if (light["device_eui"] == self._device_eui):
                self._light = light
                break

