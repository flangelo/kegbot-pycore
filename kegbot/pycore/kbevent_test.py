"""Unittest for kbevent module"""

import json
import unittest

from . import kbevent


class EventTestCase(unittest.TestCase):
  def testToDictAndJson(self):
    e = kbevent.MeterUpdate()
    e.meter_name = 'flow0'
    e.reading = 123

    d = e.ToDict()
    self.assertEqual('MeterUpdate', d['event'])
    self.assertEqual('flow0', d['data']['meter_name'])
    self.assertEqual(123, d['data']['reading'])

    # ToJson is just a JSON encoding of ToDict.
    self.assertEqual(json.loads(e.ToJson()), d)

  def testUnknownFieldRaises(self):
    e = kbevent.MeterUpdate()
    with self.assertRaises(AttributeError):
      e.nonexistent_field

  def testDecodeFromString(self):
    e = kbevent.MeterUpdate()
    e.meter_name = 'flow0'
    e.reading = 50

    decoded = kbevent.DecodeEvent(e.ToJson())
    self.assertIsInstance(decoded, kbevent.MeterUpdate)
    self.assertEqual('flow0', decoded.meter_name)
    self.assertEqual(50, decoded.reading)

  def testDecodeFromDict(self):
    decoded = kbevent.DecodeEvent(
        {'event': 'MeterUpdate', 'data': {'meter_name': 'f', 'reading': 1}})
    self.assertIsInstance(decoded, kbevent.MeterUpdate)
    self.assertEqual('f', decoded.meter_name)

  def testDecodeUnknownEventRaises(self):
    with self.assertRaises(ValueError):
      kbevent.DecodeEvent({'event': 'NoSuchEvent', 'data': {}})


class EventHubTestCase(unittest.TestCase):
  def setUp(self):
    self.hub = kbevent.EventHub()

  def testSubscribeAndDispatch(self):
    received = []
    self.hub.Subscribe(kbevent.Ping, received.append)
    self.hub.PublishEvent(kbevent.Ping())
    self.hub.DispatchNextEvent(timeout=0.1)
    self.assertEqual(1, len(received))

  def testUnsubscribe(self):
    received = []
    self.hub.Subscribe(kbevent.Ping, received.append)
    self.hub.Unsubscribe(kbevent.Ping, received.append)
    self.hub.PublishEvent(kbevent.Ping())
    self.hub.Flush()
    self.assertEqual(0, len(received))

  def testFlushReturnsCount(self):
    self.hub.PublishEvent(kbevent.Ping())
    self.hub.PublishEvent(kbevent.Ping())
    self.assertEqual(2, self.hub.Flush())

  def testDispatchEmptyQueueIsNoOp(self):
    # Should return without raising even though nothing is queued.
    self.hub.DispatchNextEvent(timeout=0.01)

  def testSubscribeRejectsPlainClass(self):
    class Plain(object):
      pass
    with self.assertRaises(ValueError):
      self.hub.Subscribe(Plain, lambda e: None)


if __name__ == '__main__':
  unittest.main()
