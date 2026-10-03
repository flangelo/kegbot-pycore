"""Finds real pours hidden inside a ghost flow.

A real pour switches on and off: the tick rate jumps from the flow's baseline
to a pour rate within a second or two, and drops back just as fast. Ghost
flows only drift. Given a flow's tick history in fixed-width bins, find_pours
returns the abrupt steps above baseline and the volume they carried on top of
it, so a pour made while a ghost flow is running can be told apart from it.
"""

import statistics

from . import common_defs

BASELINE_SECS = 8.0
BASELINE_GAP_SECS = 1.0
MIN_POUR_SECS = 2.0
MAX_POUR_SECS = 120.0


def find_pours(bins, bin_secs, ml_per_tick,
    step_ml_per_sec=common_defs.HIDDEN_POUR_STEP_ML_PER_SEC):
  """Returns [(start_secs, end_secs, volume_ml)] for each pour found.

  Args
    bins: ticks counted in each consecutive bin since the flow started
    bin_secs: width of each bin
    ml_per_tick: meter calibration
    step_ml_per_sec: how far above baseline a pour must rise
  """
  r = [ticks * ml_per_tick / bin_secs for ticks in bins]
  per_sec = int(round(1 / bin_secs))
  nb = int(BASELINE_SECS * per_sec)
  ng = int(BASELINE_GAP_SECS * per_sec)

  def mean(a, b):
    window = r[max(a, 0):max(b, 0)]
    return sum(window) / len(window) if window else 0.0

  def median(a, b):
    window = r[max(a, 0):max(b, 0)]
    return statistics.median(window) if window else 0.0

  pours = []
  i = 0
  while i < len(r):
    pre = median(i - nb - ng, i - ng)
    rises = mean(i, i + 2 * per_sec) - pre >= step_ml_per_sec
    was_quiet = mean(i - per_sec, i) - pre < step_ml_per_sec / 2
    if not (rises and was_quiet):
      i += 1
      continue

    # The pour ends when the rate falls back near the pre-pour baseline, or
    # drops sharply from the pour's own level while the ghost carries on.
    j, below = i + per_sec, 0
    while j < len(r) and below < per_sec and (j - i) * bin_secs <= MAX_POUR_SECS:
      now = mean(j, j + per_sec)
      back = now - pre < step_ml_per_sec / 2
      drop = median(i, j) - now >= step_ml_per_sec * 0.6
      below = below + 1 if (back or drop) else 0
      j += 1
    end = j - below
    length = (end - i) * bin_secs
    if not MIN_POUR_SECS <= length <= MAX_POUR_SECS:
      i += 1
      continue

    # Subtract the ghost's own flow, interpolated between its level before
    # and after the pour.
    post = median(end + ng, end + ng + nb) if end + ng < len(r) else pre
    n = end - i
    volume_ml = sum(
        max(r[k] - (pre + (post - pre) * (k - i) / n), 0) for k in range(i, end)
    ) * bin_secs
    pours.append((i * bin_secs, end * bin_secs, volume_ml))
    i = end
  return pours
