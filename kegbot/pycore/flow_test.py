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

  def testTickHistoryBins(self):
    t = datetime.datetime.fromtimestamp
    self.flow.AddTicks(3, when=t(0.2))
    self.flow.AddTicks(4, when=t(0.4))
    self.flow.AddTicks(5, when=t(1.6))
    self.flow.SetState('completed')
    e = self.flow.GetUpdateEvent()
    self.assertEqual([7, 0, 0, 5], e.tick_bins)
    self.assertEqual(0.5, e.tick_bin_secs)

  def testTickHistoryOnlyOnCompletedEvent(self):
    self.flow.AddTicks(3, when=datetime.datetime.fromtimestamp(1))
    self.assertIsNone(self.flow.GetUpdateEvent().tick_bins)

  def testTickHistoryIsCapped(self):
    t = datetime.datetime.fromtimestamp
    self.flow.AddTicks(1, when=t(10))
    self.flow.AddTicks(1, when=t(3 * 60 * 60))
    self.flow.SetState('completed')
    self.assertEqual(21, len(self.flow.GetUpdateEvent().tick_bins))
    self.assertEqual(2, self.flow.GetTicks())
