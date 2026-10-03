"""Unittest for flow module"""

import datetime
import unittest
from . import flow

class FlowTestCase(unittest.TestCase):
  def setUp(self):
    self.meter_name = 'test.meter'
    self.flow = flow.Flow(self.meter_name, 123, username=None, max_idle_secs=10,
        when=datetime.datetime.fromtimestamp(0))

  def testAddTicks(self):
    self.assertEqual(0, self.flow.GetTicks())
    self.flow.AddTicks(100)
    self.assertEqual(100, self.flow.GetTicks())

  def testGetUpdateEvent(self):
    self.flow.AddTicks(10, when=datetime.datetime.fromtimestamp(20))
    e = self.flow.GetUpdateEvent()

    self.assertEqual(None, e.username)
    self.assertEqual(123, e.flow_id)
    self.assertEqual(self.meter_name, e.meter_name)
    self.assertEqual('active', e.state)
    self.assertEqual(datetime.datetime.fromtimestamp(0), e.start_time)
    self.assertEqual(datetime.datetime.fromtimestamp(20), e.last_activity_time)
    self.assertEqual(10, e.ticks)
    self.assertEqual(10, e.onset_ticks)

  def testOnsetTicksOnlyCountsStartOfFlow(self):
    t = datetime.datetime.fromtimestamp
    self.flow.AddTicks(5, when=t(1))
    self.flow.AddTicks(8, when=t(20))
    self.flow.AddTicks(1000, when=t(21))
    self.assertEqual(1013, self.flow.GetTicks())
    self.assertEqual(13, self.flow.GetUpdateEvent().onset_ticks)
