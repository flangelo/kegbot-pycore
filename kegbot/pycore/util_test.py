"""Unittest for util module"""

import unittest

from .util import AttrDict


class AttrDictTestCase(unittest.TestCase):
  def testAttributeAccess(self):
    d = AttrDict({'a': 1})
    self.assertEqual(1, d.a)
    self.assertEqual(1, d['a'])

  def testNestedDictBecomesAttrDict(self):
    d = AttrDict({'outer': {'inner': 5}})
    self.assertIsInstance(d.outer, AttrDict)
    self.assertEqual(5, d.outer.inner)

  def testMissingKeyRaisesAttributeError(self):
    d = AttrDict({'a': 1})
    with self.assertRaises(AttributeError):
      d.missing

  def testSetAttribute(self):
    d = AttrDict()
    d.x = 10
    self.assertEqual(10, d['x'])
    self.assertEqual(10, d.x)

  def testEmptyInit(self):
    d = AttrDict()
    self.assertEqual(0, len(d))


if __name__ == '__main__':
  unittest.main()
