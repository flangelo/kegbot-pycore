"""Unittest for kb_threads module (testable thread logic)."""

import unittest
from unittest import mock

from kegbot.api import exceptions as api_exceptions

from . import kb_threads
from . import kbevent
from .util import AttrDict


class FakeEnv(object):
  """Minimal kb_env stand-in exposing only the event hub."""
  def __init__(self, hub):
    self._hub = hub

  def GetEventHub(self):
    return self._hub


class SyncThreadTestCase(unittest.TestCase):
  def setUp(self):
    self.hub = kbevent.EventHub()
    self.env = FakeEnv(self.hub)

  def _make_thread(self, backend):
    return kb_threads.SyncThread(self.env, 'sync-thread', backend)

  def testSyncPublishesSyncEvent(self):
    backend = mock.Mock()
    backend.GetStatus.return_value = {'current_session': {'id': 1}, 'taps': []}
    thread = self._make_thread(backend)

    received = []
    self.hub.Subscribe(kbevent.SyncEvent, received.append)

    status = thread.sync_now()
    self.hub.Flush()

    self.assertEqual({'current_session': {'id': 1}, 'taps': []}, status)
    self.assertEqual(1, len(received))
    self.assertIsInstance(received[0].data, AttrDict)
    self.assertEqual(1, received[0].data.current_session.id)

  def testSyncHandlesApiError(self):
    backend = mock.Mock()
    backend.GetStatus.side_effect = api_exceptions.Error('boom')
    thread = self._make_thread(backend)

    received = []
    self.hub.Subscribe(kbevent.SyncEvent, received.append)

    status = thread.sync_now()
    self.hub.Flush()

    self.assertEqual({}, status)
    self.assertEqual(0, len(received))

  def testHandleQuitStopsThread(self):
    thread = self._make_thread(mock.Mock())
    self.assertFalse(thread._quit)
    thread._HandleQuit(kbevent.QuitEvent())
    self.assertTrue(thread._quit)


if __name__ == '__main__':
  unittest.main()
