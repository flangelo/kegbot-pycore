#!/usr/bin/env python

"""Unittest for manager module"""

import datetime
import unittest
from unittest import mock

from kegbot.api import kbapi

from . import backend
from . import common_defs
from . import kbevent
from . import manager
from .util import AttrDict


class FakeBackend(backend.Backend):
  """In-memory backend that records calls for assertions."""
  def __init__(self):
    self.drinks = []
    self.sensor_readings = []
    self.tokens = {}  # (auth_device, token_value) -> AttrDict
    self.record_drink_exception = None

  def RecordDrink(self, meter_name, ticks, volume_ml=None, username=None,
      pour_time=None, duration=0, auth_token=None, spilled=False, shout=''):
    if self.record_drink_exception:
      raise self.record_drink_exception
    drink = AttrDict({
      'id': len(self.drinks) + 1,
      'time': pour_time,
      'volume_ml': volume_ml if volume_ml is not None else ticks,
      'ticks': ticks,
      'keg_id': 1,
      'user_id': username,
    })
    self.drinks.append(drink)
    return drink

  def LogSensorReading(self, sensor_name, temperature, when=None):
    self.sensor_readings.append((sensor_name, temperature, when))
    return True

  def GetAuthToken(self, auth_device, token_value):
    token = self.tokens.get((auth_device, token_value))
    if token is None:
      raise kbapi.NotFoundError('no such token')
    return token


class FlowManagerTestCase(unittest.TestCase):
  def setUp(self):
    event_hub = kbevent.EventHub()
    backend = None
    self.tap_manager = manager.TapManager(event_hub, backend)
    self.flow_manager = manager.FlowManager(event_hub, self.tap_manager)
    self.tap_manager._RegisterOrUpdateTap(name='flow0', ml_per_tick=1000/2200.0)

  def tearDown(self):
    del self.tap_manager._taps['flow0']

  def testBasicMeterUse(self):
    """Create a new flow device, perform basic operations on it."""
    # Duplicate registration should cause an exception.
    #self.assertRaises(manager.AlreadyRegisteredError,
    #                  self.tap_manager.RegisterTap, 'flow0', 0, 0)

    self.assertIsNone(self.tap_manager.GetTap('flow_unknown'))

    # Our new device should have accumulated 0 volume thus far.
    tap = self.tap_manager.GetTap('flow0')
    meter = self.flow_manager.GetMeter('flow0')
    self.assertEqual(meter.GetTicks(), 0)

    # Report an instantaneous reading of 2000 ticks. Since this is the first
    # reading, this should cause no change in the device volume.
    flow, is_new = self.flow_manager.UpdateFlow(tap.GetName(), 2000)
    self.assertEqual(meter.GetTicks(), 0)
    self.assertIsNotNone(flow)
    self.assertTrue(is_new)

    # Report another instantaneous reading, which should now increment the flow
    new_flow, is_new = self.flow_manager.UpdateFlow(tap.GetName(), 2100)
    self.assertEqual(meter.GetTicks(), 100)
    self.assertFalse(is_new)
    self.assertIs(flow, new_flow)

    # The FlowManager saves the last reading value; check it.
    self.assertEqual(meter.GetLastReading(), 2100)

    # Report a reading that is much larger than the last reading. Values larger
    # than the constant common_defs.MAX_METER_READING_DELTA should be ignored by
    # the FlowManager.
    meter_reading = meter.GetLastReading()
    illegal_delta = common_defs.MAX_METER_READING_DELTA + 100
    new_reading = meter_reading + illegal_delta

    # The illegal update should not affect the volume.
    new_flow, is_new = self.flow_manager.UpdateFlow(tap.GetName(), new_reading)
    self.assertFalse(is_new)
    self.assertIs(flow, new_flow)
    self.assertEqual(meter.GetTicks(), 100)

    # The value of the last update should be recorded, however.
    self.assertEqual(meter.GetLastReading(), new_reading)

  def testOverflowHandling(self):
    first_reading = 2**32 - 100    # start with very large number
    second_reading = 2**32 - 50    # increment by 50
    overflow_reading = 10          # increment by 50+10 (overflow)

    flow, is_new = self.flow_manager.UpdateFlow('flow0', first_reading)
    self.assertIsNotNone(flow)
    self.assertTrue(is_new)
    self.assertEqual(0, flow.GetTicks())

    new_flow, is_new = self.flow_manager.UpdateFlow('flow0', second_reading)
    self.assertIs(flow, new_flow)
    self.assertFalse(is_new)
    self.assertEqual(50, flow.GetTicks())

    new_flow, is_new = self.flow_manager.UpdateFlow('flow0', overflow_reading)
    self.assertIs(flow, new_flow)
    self.assertFalse(is_new)
    self.assertEqual(50, flow.GetTicks())

  def testNoOverflow(self):
    flow, is_new = self.flow_manager.UpdateFlow('flow0', 0)
    self.assertIsNotNone(flow)
    self.assertTrue(is_new)
    self.assertEqual(0, flow.GetTicks())

    new_flow, is_new = self.flow_manager.UpdateFlow('flow0', 100)
    self.assertIs(flow, new_flow)
    self.assertFalse(is_new)
    self.assertEqual(100, flow.GetTicks())

    new_flow, is_new = self.flow_manager.UpdateFlow('flow0', 10)
    self.assertIs(flow, new_flow)
    self.assertFalse(is_new)
    self.assertEqual(100, flow.GetTicks())

    new_flow, is_new = self.flow_manager.UpdateFlow('flow0', 20)
    self.assertIs(flow, new_flow)
    self.assertFalse(is_new)
    self.assertEqual(110, flow.GetTicks())

  def testActivityMonitoring(self):
    def t(stamp):
      return datetime.datetime.fromtimestamp(stamp)

    flow, is_new = self.flow_manager.UpdateFlow('flow0', 0, when=t(0))
    self.assertIsNotNone(flow)
    self.assertTrue(is_new)

    self.assertFalse(flow.IsIdle(when=t(0)))
    self.assertTrue(flow.IsIdle(when=t(1000)))

    idle_flows = list(self.flow_manager.IterIdleFlows(when=t(0)))
    self.assertTrue(len(idle_flows) == 0)

    idle_flows = list(self.flow_manager.IterIdleFlows(when=t(1000)))
    self.assertTrue(len(idle_flows) == 1)

  def testImplicitFlowStartsAtUpdateTime(self):
    def t(stamp):
      return datetime.datetime.fromtimestamp(stamp)

    flow, _ = self.flow_manager.UpdateFlow('flow0', 0, when=t(100))
    self.flow_manager.UpdateFlow('flow0', 5, when=t(110))
    self.flow_manager.UpdateFlow('flow0', 900, when=t(130))
    event = flow.GetUpdateEvent()
    self.assertEqual(t(100), event.start_time)
    self.assertEqual(900, event.ticks)
    self.assertEqual(5, event.onset_ticks)


class DrinkManagerTestCase(unittest.TestCase):
  def setUp(self):
    self.hub = kbevent.EventHub()
    self.backend = FakeBackend()
    self.drink_manager = manager.DrinkManager(self.hub, self.backend)

  def _completed_event(self, ticks=100, volume_ml=50, username='alice',
      duration=5, onset_ticks=None):
    e = kbevent.FlowUpdate()
    e.flow_id = 0x1234
    e.meter_name = 'flow0'
    e.state = kbevent.FlowUpdate.FlowState.COMPLETED
    e.username = username
    e.start_time = datetime.datetime.fromtimestamp(0)
    e.last_activity_time = datetime.datetime.fromtimestamp(duration)
    e.ticks = ticks
    e.volume_ml = volume_ml
    e.onset_ticks = ticks if onset_ticks is None else onset_ticks
    return e

  def testRecordsCompletedFlow(self):
    created = []
    self.hub.Subscribe(kbevent.DrinkCreatedEvent, created.append)

    self.drink_manager.HandleFlowUpdateEvent(self._completed_event())

    self.assertEqual(1, len(self.backend.drinks))
    self.assertEqual(100, self.backend.drinks[0].ticks)
    self.assertEqual('alice', self.backend.drinks[0].user_id)

    # A DrinkCreatedEvent should have been published for downstream listeners.
    self.hub.Flush()
    self.assertEqual(1, len(created))
    self.assertEqual(0x1234, created[0].flow_id)

  def testIgnoresNonCompletedFlow(self):
    event = self._completed_event()
    event.state = kbevent.FlowUpdate.FlowState.ACTIVE
    self.drink_manager.HandleFlowUpdateEvent(event)
    self.assertEqual(0, len(self.backend.drinks))

  def testSkipsTinyPour(self):
    self.drink_manager.HandleFlowUpdateEvent(
        self._completed_event(volume_ml=common_defs.MIN_VOLUME_TO_RECORD - 1))
    self.assertEqual(0, len(self.backend.drinks))

  def testSkipsZeroTicks(self):
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(ticks=0))
    self.assertEqual(0, len(self.backend.drinks))

  def testSkipsGhostPour(self):
    # A real ghost pour: 3076 mL trickled in over 36 minutes (1.4 mL/s).
    self.drink_manager.HandleFlowUpdateEvent(
        self._completed_event(ticks=21534, volume_ml=3076, duration=2162))
    self.assertEqual(0, len(self.backend.drinks))

  def testRecordsSlowRealPour(self):
    # The slowest real pour on record: 355 mL over 83 s (4.3 mL/s).
    self.drink_manager.HandleFlowUpdateEvent(
        self._completed_event(ticks=2485, volume_ml=355, duration=83))
    self.assertEqual(1, len(self.backend.drinks))

  def testRecordsSlowShortFlow(self):
    # Below the ghost rate, but too short to be judged by rate.
    self.drink_manager.HandleFlowUpdateEvent(
        self._completed_event(volume_ml=50, duration=59))
    self.assertEqual(1, len(self.backend.drinks))

  def testGhostPourRateBoundary(self):
    min_secs = common_defs.GHOST_POUR_MIN_DURATION_SECS
    max_rate = common_defs.GHOST_POUR_MAX_RATE_ML_PER_SEC
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        volume_ml=max_rate * min_secs, duration=min_secs))
    self.assertEqual(1, len(self.backend.drinks))
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        volume_ml=max_rate * min_secs - 1, duration=min_secs))
    self.assertEqual(1, len(self.backend.drinks))

  def testRetriesThenDropsOnBackendError(self):
    self.backend.record_drink_exception = backend.BackendException('boom')

    # First attempt (via the event handler) seeds the retry counter and requeues.
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event())
    self.assertEqual(1, len(self.drink_manager._pending))

    # Default maximum_event_retries is 3, so the event survives two more flushes
    # before being dropped.
    self.drink_manager._FlushPending()
    self.assertEqual(1, len(self.drink_manager._pending))
    self.drink_manager._FlushPending()
    self.assertEqual(0, len(self.drink_manager._pending))
    self.assertEqual(0, len(self.backend.drinks))


  def testSkipsAcceleratingGhostPour(self):
    # A real ghost pour: 13 ticks in the first 20 s, then a ramp to several
    # times a real pour's rate; 5545 mL over 172 s (32 mL/s average).
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        ticks=38813, volume_ml=5545, duration=172, onset_ticks=13))
    self.assertEqual(0, len(self.backend.drinks))

  def testRecordsLongRealPour(self):
    # Filling a pitcher: full flow from the start, for two minutes.
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        ticks=21000, volume_ml=3000, duration=120, onset_ticks=3500))
    self.assertEqual(1, len(self.backend.drinks))

  def testRecordsShortFlowWithSlowOnset(self):
    # A stray tick, then a real pour starting a few seconds later.
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        ticks=2100, volume_ml=300, duration=25, onset_ticks=1))
    self.assertEqual(1, len(self.backend.drinks))

  def testOnsetBoundary(self):
    min_ml = common_defs.GHOST_POUR_MIN_ONSET_ML
    duration = common_defs.GHOST_POUR_MIN_DURATION_SECS
    # 1 tick per mL, so onset_ticks reads directly as mL.
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        ticks=1000, volume_ml=1000, duration=duration, onset_ticks=min_ml))
    self.assertEqual(1, len(self.backend.drinks))
    self.drink_manager.HandleFlowUpdateEvent(self._completed_event(
        ticks=1000, volume_ml=1000, duration=duration, onset_ticks=min_ml - 1))
    self.assertEqual(1, len(self.backend.drinks))

  def testMissingOnsetSkipsOnsetCheck(self):
    event = self._completed_event(ticks=7000, volume_ml=1000, duration=90)
    event.onset_ticks = None
    self.drink_manager.HandleFlowUpdateEvent(event)
    self.assertEqual(1, len(self.backend.drinks))


class ThermoManagerTestCase(unittest.TestCase):
  def setUp(self):
    self.hub = kbevent.EventHub()
    self.backend = FakeBackend()
    self.thermo_manager = manager.ThermoManager(self.hub, self.backend)

  def _event(self, name='sensor0', value=4.0):
    e = kbevent.ThermoEvent()
    e.sensor_name = name
    e.sensor_value = value
    return e

  def testRecordsReading(self):
    self.thermo_manager._HandleThermoUpdateEvent(self._event(value=4.0))
    self.assertEqual(1, len(self.backend.sensor_readings))
    self.assertEqual('sensor0', self.backend.sensor_readings[0][0])
    self.assertEqual(4.0, self.backend.sensor_readings[0][1])

  def testRejectsOutOfRange(self):
    too_hot = common_defs.THERMO_SENSOR_RANGE[1] + 100
    self.thermo_manager._HandleThermoUpdateEvent(self._event(value=too_hot))
    self.assertEqual(0, len(self.backend.sensor_readings))

  def testDropsDuplicateWithinSameMinute(self):
    with mock.patch('kegbot.pycore.manager.datetime') as mock_dt:
      mock_dt.datetime.now.return_value = datetime.datetime(2024, 1, 1, 12, 30, 15)
      mock_dt.timedelta = datetime.timedelta
      self.thermo_manager._HandleThermoUpdateEvent(self._event(value=4.0))
      self.thermo_manager._HandleThermoUpdateEvent(self._event(value=5.0))
    self.assertEqual(1, len(self.backend.sensor_readings))


class AuthenticationManagerTestCase(unittest.TestCase):
  def setUp(self):
    self.hub = kbevent.EventHub()
    self.backend = FakeBackend()
    self.tap_manager = manager.TapManager(self.hub, self.backend)
    self.flow_manager = manager.FlowManager(self.hub, self.tap_manager)
    self.auth_manager = manager.AuthenticationManager(
        self.hub, self.flow_manager, self.tap_manager, self.backend)
    self.tap_manager._RegisterOrUpdateTap('flow0', ml_per_tick=0.5,
        relay_name='relay0')

  def _auth_event(self, device, status, meter_name='flow0', token_value='tok1'):
    e = kbevent.TokenAuthEvent()
    e.meter_name = meter_name
    e.auth_device_name = device
    e.token_value = token_value
    e.status = status
    return e

  def testCaptiveTokenStartsAndEndsFlow(self):
    self.backend.tokens[(common_defs.AUTH_MODULE_CORE_ONEWIRE, 'tok1')] = \
        AttrDict({'username': 'alice', 'enabled': True})

    self.auth_manager.HandleAuthTokenEvent(self._auth_event(
        common_defs.AUTH_MODULE_CORE_ONEWIRE,
        kbevent.TokenAuthEvent.TokenState.ADDED))

    flow = self.flow_manager.GetFlow('flow0')
    self.assertIsNotNone(flow)
    self.assertEqual('alice', flow.GetUsername())

    # Regression test: TokenRecord equality was broken under Python 3 (only
    # __cmp__ was defined), so removing a captive token silently no-op'd and
    # the flow was never stopped.
    self.auth_manager.HandleAuthTokenEvent(self._auth_event(
        common_defs.AUTH_MODULE_CORE_ONEWIRE,
        kbevent.TokenAuthEvent.TokenState.REMOVED))
    self.assertIsNone(self.flow_manager.GetFlow('flow0'))

  def testNonCaptiveTokenRemovalKeepsFlow(self):
    self.backend.tokens[(common_defs.AUTH_MODULE_CORE_RFID, 'tok1')] = \
        AttrDict({'username': 'bob', 'enabled': True})

    self.auth_manager.HandleAuthTokenEvent(self._auth_event(
        common_defs.AUTH_MODULE_CORE_RFID,
        kbevent.TokenAuthEvent.TokenState.ADDED))
    self.assertIsNotNone(self.flow_manager.GetFlow('flow0'))

    # Non-captive (contactless) devices leave the flow running; it times out
    # rather than ending immediately on token removal.
    self.auth_manager.HandleAuthTokenEvent(self._auth_event(
        common_defs.AUTH_MODULE_CORE_RFID,
        kbevent.TokenAuthEvent.TokenState.REMOVED))
    self.assertIsNotNone(self.flow_manager.GetFlow('flow0'))

  def testUnknownTokenStartsNoFlow(self):
    self.auth_manager.HandleAuthTokenEvent(self._auth_event(
        common_defs.AUTH_MODULE_CORE_ONEWIRE,
        kbevent.TokenAuthEvent.TokenState.ADDED))
    self.assertIsNone(self.flow_manager.GetFlow('flow0'))

  def testDisabledTokenStartsNoFlow(self):
    self.backend.tokens[(common_defs.AUTH_MODULE_CORE_ONEWIRE, 'tok1')] = \
        AttrDict({'username': 'alice', 'enabled': False})
    self.auth_manager.HandleAuthTokenEvent(self._auth_event(
        common_defs.AUTH_MODULE_CORE_ONEWIRE,
        kbevent.TokenAuthEvent.TokenState.ADDED))
    self.assertIsNone(self.flow_manager.GetFlow('flow0'))


if __name__ == '__main__':
  unittest.main()
