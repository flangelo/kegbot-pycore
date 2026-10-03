"""Unittest for pour_detect module"""

import unittest

from . import pour_detect

BIN = 0.5
JITTER = (1.0, 1.2, 0.85, 1.1, 0.9, 1.15, 0.8, 1.05)


def profile(*segments):
  """Builds 0.5 s tick bins (1 tick = 1 mL) from (seconds, mL/s) segments.

  A segment's rate may be a (start, end) pair to ramp linearly. Rates carry a
  deterministic jitter so the input is not unrealistically smooth.
  """
  bins = []
  for secs, rate in segments:
    lo, hi = rate if isinstance(rate, tuple) else (rate, rate)
    n = int(secs / BIN)
    for k in range(n):
      r = lo + (hi - lo) * k / max(n - 1, 1)
      bins.append(int(round(r * BIN * JITTER[len(bins) % len(JITTER)])))
  return bins


def add(base, extra, at_secs):
  out = list(base)
  start = int(at_secs / BIN)
  for k, ticks in enumerate(extra):
    out[start + k] += ticks
  return out


def find(bins):
  return pour_detect.find_pours(bins, BIN, 1.0)


class FindPoursTestCase(unittest.TestCase):
  def assertOnePour(self, pours, start_secs, volume_ml):
    self.assertEqual(1, len(pours), pours)
    start, end, ml = pours[0]
    self.assertAlmostEqual(start_secs, start, delta=1.5)
    self.assertAlmostEqual(volume_ml, ml, delta=volume_ml * 0.15)

  def testEmpty(self):
    self.assertEqual([], find([]))

  def testSlowGhostAlone(self):
    self.assertEqual([], find(profile((300, 1.5))))

  def testAcceleratingGhostAlone(self):
    self.assertEqual([], find(profile((10, 0), (150, (0.5, 60)), (20, 60))))

  def testRealPourAlone(self):
    self.assertOnePour(find(profile((10, 30))), 0, 300)

  def testPourDuringSlowGhost(self):
    ghost = profile((120, 1.5))
    bins = add(ghost, profile((12, 25)), at_secs=40)
    self.assertOnePour(find(bins), 40, 300)

  def testPourDuringRampingGhost(self):
    ghost = profile((150, (1, 20)))
    bins = add(ghost, profile((10, 30)), at_secs=90)
    self.assertOnePour(find(bins), 90, 300)

  def testTwoPoursDuringGhost(self):
    ghost = profile((200, 1))
    bins = add(ghost, profile((8, 30)), at_secs=30)
    bins = add(bins, profile((10, 25)), at_secs=120)
    pours = find(bins)
    self.assertEqual(2, len(pours), pours)
    self.assertAlmostEqual(240, pours[0][2], delta=36)
    self.assertAlmostEqual(250, pours[1][2], delta=38)

  def testPourAtFlowStartIgnoresLaterGhost(self):
    # The baseline window before the first bins is empty, not the flow's tail.
    bins = profile((6, 30), (6, 0), (60, (0.5, 60)))
    self.assertOnePour(find(bins), 0, 180)

  def testOverlongStepIsNotAPour(self):
    self.assertEqual([], find(profile((10, 0), (200, 30))))


if __name__ == '__main__':
  unittest.main()
