"""Unittest for backend module (WebBackend exception translation)."""

import socket
import unittest
from unittest import mock

from kegbot.api import kbapi

from . import backend
from . import common_defs


class WebBackendTestCase(unittest.TestCase):
  def setUp(self):
    # WebBackend builds a kbapi.Client in __init__; replace it with a mock so
    # no network access occurs.
    self.client_patcher = mock.patch.object(backend.kbapi, 'Client')
    self.MockClient = self.client_patcher.start()
    self.client = self.MockClient.return_value
    self.wb = backend.WebBackend(api_url='http://example/api/', api_key='key')

  def tearDown(self):
    self.client_patcher.stop()

  # --- RecordDrink ---
  def testRecordDrinkSuccess(self):
    self.client.record_drink.return_value = {'id': 1}
    result = self.wb.RecordDrink('flow0', ticks=100, username='alice')
    self.assertEqual({'id': 1}, result)
    _, kwargs = self.client.record_drink.call_args
    self.assertEqual('flow0', kwargs['tap_name'])
    self.assertEqual(100, kwargs['ticks'])
    self.assertEqual('alice', kwargs['username'])

  def testRecordDrinkNotFound(self):
    self.client.record_drink.side_effect = kbapi.NotFoundError('nope')
    with self.assertRaises(backend.DoesNotExistException):
      self.wb.RecordDrink('flow0', ticks=100)

  def testRecordDrinkError(self):
    self.client.record_drink.side_effect = kbapi.Error('boom')
    with self.assertRaises(backend.BackendException):
      self.wb.RecordDrink('flow0', ticks=100)

  # --- LogSensorReading ---
  def testLogSensorReadingSuccess(self):
    self.client.log_sensor_reading.return_value = 'ok'
    self.assertEqual('ok', self.wb.LogSensorReading('sensor0', 4.0))

  def testLogSensorReadingOutOfRange(self):
    too_hot = common_defs.THERMO_SENSOR_RANGE[1] + 100
    with self.assertRaises(ValueError):
      self.wb.LogSensorReading('sensor0', too_hot)
    self.client.log_sensor_reading.assert_not_called()

  def testLogSensorReadingNotFound(self):
    self.client.log_sensor_reading.side_effect = kbapi.NotFoundError()
    self.assertIsNone(self.wb.LogSensorReading('sensor0', 4.0))

  def testLogSensorReadingServerError(self):
    self.client.log_sensor_reading.side_effect = kbapi.ServerError()
    self.assertIsNone(self.wb.LogSensorReading('sensor0', 4.0))

  def testLogSensorReadingSocketError(self):
    self.client.log_sensor_reading.side_effect = socket.error()
    self.assertIsNone(self.wb.LogSensorReading('sensor0', 4.0))

  # --- GetAuthToken ---
  def testGetAuthTokenSuccess(self):
    self.client.get_token.return_value = {'username': 'alice'}
    self.assertEqual({'username': 'alice'},
        self.wb.GetAuthToken('core.rfid', 'tok'))

  def testGetAuthTokenNotFoundReRaised(self):
    self.client.get_token.side_effect = kbapi.NotFoundError()
    with self.assertRaises(kbapi.NotFoundError):
      self.wb.GetAuthToken('core.rfid', 'tok')

  def testGetAuthTokenSocketErrorBecomesNotFound(self):
    self.client.get_token.side_effect = socket.error()
    with self.assertRaises(kbapi.NotFoundError):
      self.wb.GetAuthToken('core.rfid', 'tok')

  # --- CreateController ---
  def testCreateControllerCreatesDefaultMeters(self):
    self.client.create_controller.return_value = {'id': 7}
    result = self.wb.CreateController('kegboard')
    self.assertEqual({'id': 7}, result)
    self.assertEqual(2, self.client.create_flow_meter.call_count)
    self.client.create_flow_meter.assert_any_call(7, 'flow0')
    self.client.create_flow_meter.assert_any_call(7, 'flow1')

  def testCreateControllerError(self):
    self.client.create_controller.side_effect = kbapi.Error('boom')
    with self.assertRaises(backend.BackendException):
      self.wb.CreateController('kegboard')

  # --- CancelDrink ---
  def testCancelDrinkSuccess(self):
    self.client.cancel_drink.return_value = 'ok'
    self.assertEqual('ok', self.wb.CancelDrink(5))

  def testCancelDrinkError(self):
    self.client.cancel_drink.side_effect = kbapi.Error('boom')
    with self.assertRaises(backend.BackendException):
      self.wb.CancelDrink(5)

  # --- pass-throughs ---
  def testGetStatus(self):
    self.client.status.return_value = {'ok': True}
    self.assertEqual({'ok': True}, self.wb.GetStatus())

  def testGetAllTaps(self):
    self.client.taps.return_value = ['a', 'b']
    self.assertEqual(['a', 'b'], self.wb.GetAllTaps())


if __name__ == '__main__':
  unittest.main()
