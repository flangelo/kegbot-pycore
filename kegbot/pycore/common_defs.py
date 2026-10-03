"""Various constants used within pycore."""

### Drink-related constants

# Don't record teeny drinks
MIN_VOLUME_TO_RECORD = 10

# Don't record "ghost pours". With the faucet closed, CO2 breaking out of
# warming beer (e.g. a kegerator cycling below freezing) can push ticks through
# a meter, never idling long enough to end the flow. Ghosts begin as a
# near-silent trickle; some stay slow for half an hour (0.06-1.4 mL/s average),
# others accelerate to several times a real pour's rate. Real pours reach full
# flow within a second: >= 89 mL in their first 20 s, and >= 4 mL/s average.
# Observed ghosts had <= 17 mL in their first 20 s. Both checks apply only to
# flows lasting at least GHOST_POUR_MIN_DURATION_SECS.
GHOST_POUR_MIN_DURATION_SECS = 60
GHOST_POUR_MAX_RATE_ML_PER_SEC = 2.0
GHOST_POUR_ONSET_SECS = 20
GHOST_POUR_MIN_ONSET_ML = 40

# A real pour made while a ghost flow is running would be dropped with it.
# Flows keep a tick history in bins of this width (up to the cap), and
# pour_detect looks in dropped flows for abrupt steps at least this far above
# the ghost's baseline. Real pours reach 19-45 mL/s within a second or two;
# ghosts drift by a few mL/s per second. Log-only for now: hidden pours are
# reported, not recorded.
FLOW_HISTORY_BIN_SECS = 0.5
FLOW_HISTORY_MAX_SECS = 2 * 60 * 60
HIDDEN_POUR_STEP_ML_PER_SEC = 15

# The maximum difference between consecutive meter readings that is considered
# valid.
MAX_METER_READING_DELTA = 2200*2

# Minimum and maximum thermo sensor readings (degrees C).
THERMO_SENSOR_RANGE = (-20.0, 80.0)

# Address the kegnet server should bind to.
KB_CORE_DEFAULT_ADDR = 'localhost:9805'

# String name for all taps
ALIAS_ALL_TAPS = '__all_taps__'

# Device names
AUTH_MODULE_CORE_ONEWIRE = 'core.onewire'
AUTH_MODULE_CORE_RFID = 'core.rfid'
AUTH_MODULE_CONTRIB_PHIDGET_RFID = AUTH_MODULE_CORE_RFID

# Flag which determines whether an auth device is captive or non-captive.  A
# captive device is one which captures the authentication token, and provides a
# very reliable signal when the token is detached.
#
# For a device marked as captive, the AuthenticationManager will immediately end
# any active flows when a token is removed.  For non-captive (or contactless)
# devices, such as an RFID reader, the authentication manager does nothing when
# the token is removed (see flow timeout, next).
AUTH_DEVICE_CAPTIVE = {
  AUTH_MODULE_CORE_ONEWIRE: True,
  AUTH_MODULE_CORE_RFID: False,
  'default': True
}

# Maximum idle time for new flows, based on initiating auth device.  "Idle" is
# defined as seconds elapsed without any flow meter activity.
#
# This varies on a per-auth-device basis due to the distinction between captive
# and non-captive devices: we want flows initiated with a contactless auth
# device, like an RFID, to timeout sooner.
AUTH_DEVICE_MAX_IDLE_SECS = {
  AUTH_MODULE_CORE_ONEWIRE: 120,
  AUTH_MODULE_CORE_RFID: 20,
  'default': 10
}

# How often to record a thermo reading?
THERMO_RECORD_DELTA_SECONDS = 60
