"""Unittest for kegnet module (Redis pub/sub client)."""

import json
import unittest
from unittest import mock

import redis

from . import kbevent
from . import kegnet


class KegnetClientTestCase(unittest.TestCase):
  def setUp(self):
    # KegnetClient connects to Redis in __init__; replace from_url with a mock.
    self.patcher = mock.patch.object(kegnet.redis, 'from_url')
    self.mock_from_url = self.patcher.start()
    self.redis = self.mock_from_url.return_value
    self.client = kegnet.KegnetClient(redis_url='redis://localhost:6379/0',
        channel_name='kegnet')

  def tearDown(self):
    self.patcher.stop()

  def _published(self):
    self.redis.publish.assert_called_once()
    (channel, payload), _ = self.redis.publish.call_args
    return channel, json.loads(payload)

  def testPing(self):
    self.redis.ping.return_value = True
    self.assertTrue(self.client.ping())

  def testPingConnectionError(self):
    self.redis.ping.side_effect = redis.exceptions.ConnectionError()
    self.assertFalse(self.client.ping())

  def testSendMessageSwallowsConnectionError(self):
    self.redis.publish.side_effect = redis.exceptions.ConnectionError()
    # Must not raise; a dropped message is logged and ignored.
    self.client.SendMeterUpdate('flow0', 100)

  def testSendMeterUpdate(self):
    self.client.SendMeterUpdate('flow0', 100)
    channel, msg = self._published()
    self.assertEqual('kegnet', channel)
    self.assertEqual('MeterUpdate', msg['event'])
    self.assertEqual('flow0', msg['data']['meter_name'])
    self.assertEqual(100, msg['data']['reading'])

  def testSendFlowStart(self):
    self.client.SendFlowStart('flow0')
    _, msg = self._published()
    self.assertEqual('FlowRequest', msg['event'])
    self.assertEqual(kbevent.FlowRequest.Action.START_FLOW,
        msg['data']['request'])

  def testSendFlowStop(self):
    self.client.SendFlowStop('flow0')
    _, msg = self._published()
    self.assertEqual(kbevent.FlowRequest.Action.STOP_FLOW,
        msg['data']['request'])

  def testSendThermoUpdate(self):
    self.client.SendThermoUpdate('sensor0', 4.0)
    _, msg = self._published()
    self.assertEqual('ThermoEvent', msg['event'])
    self.assertEqual('sensor0', msg['data']['sensor_name'])
    self.assertEqual(4.0, msg['data']['sensor_value'])

  def testSendAuthTokenAdd(self):
    self.client.SendAuthTokenAdd('flow0', 'core.rfid', 'tok')
    _, msg = self._published()
    self.assertEqual('TokenAuthEvent', msg['event'])
    self.assertEqual(kbevent.TokenAuthEvent.TokenState.ADDED,
        msg['data']['status'])

  def testSendAuthTokenRemove(self):
    self.client.SendAuthTokenRemove('flow0', 'core.rfid', 'tok')
    _, msg = self._published()
    self.assertEqual(kbevent.TokenAuthEvent.TokenState.REMOVED,
        msg['data']['status'])

  def testSendControllerConnected(self):
    self.client.SendControllerConnectedEvent('kegboard')
    _, msg = self._published()
    self.assertEqual('ControllerConnectedEvent', msg['event'])
    self.assertEqual('kegboard', msg['data']['controller_name'])


class HandleMessageTestCase(unittest.TestCase):
  def setUp(self):
    self.patcher = mock.patch.object(kegnet.redis, 'from_url')
    self.patcher.start()

    received = {'new': [], 'flow': [], 'drink': [], 'relay': []}
    self.received = received

    class RecordingClient(kegnet.KegnetClient):
      def onNewEvent(self, event):
        received['new'].append(event)

      def onFlowUpdate(self, event):
        received['flow'].append(event)

      def onDrinkCreated(self, event):
        received['drink'].append(event)

      def onSetRelayOutput(self, event):
        received['relay'].append(event)

    self.client = RecordingClient()

  def tearDown(self):
    self.patcher.stop()

  def _msg(self, event):
    return {'type': 'message', 'data': event.ToJson()}

  def testIgnoresNonMessageType(self):
    self.client._handle_message({'type': 'subscribe', 'data': 1})
    self.assertEqual(0, len(self.received['new']))

  def testIgnoresUndecodableEvent(self):
    self.client._handle_message(
        {'type': 'message', 'data': '{"event": "Nope", "data": {}}'})
    self.assertEqual(0, len(self.received['new']))

  def testDispatchesFlowUpdate(self):
    e = kbevent.FlowUpdate()
    e.flow_id = 1
    self.client._handle_message(self._msg(e))
    self.assertEqual(1, len(self.received['new']))
    self.assertEqual(1, len(self.received['flow']))

  def testDispatchesDrinkCreated(self):
    e = kbevent.DrinkCreatedEvent()
    e.drink_id = 1
    self.client._handle_message(self._msg(e))
    self.assertEqual(1, len(self.received['drink']))

  def testDispatchesSetRelayOutput(self):
    e = kbevent.SetRelayOutputEvent()
    e.output_name = 'relay0'
    self.client._handle_message(self._msg(e))
    self.assertEqual(1, len(self.received['relay']))


if __name__ == '__main__':
  unittest.main()
