"""
Examples how to run these tests::

  $ inv test
  $ python setup.py test
  $ python setup.py test -s tests.DocsTests
  $ python setup.py test -s tests.DocsTests.test_debts
  $ python setup.py test -s tests.DocsTests.test_docs
"""
import unittest
from setuptools import find_packages
from appy.setup_info import SETUP_INFO


class PackagesTests(unittest.TestCase):

    def test_packages(self):
        # same as in atelier.test.TestCase.run_pages_test but we don't
        # want appy to depend on atelier.
        declared_packages = SETUP_INFO['packages']
        found_packages = find_packages()
        # if tests exists, remove it:
        if 'tests' in found_packages:
            found_packages.remove('tests')
        found_packages.sort()
        declared_packages.sort()
        self.assertEqual(found_packages, declared_packages)
        


