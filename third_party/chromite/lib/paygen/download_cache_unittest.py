#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test download_cache library.

DEPRECATED: Should be migrated to chromite.lib.cache_unittest.
"""

from __future__ import print_function

import mox
import multiprocessing
import os
import pickle
import traceback

import fixup_path
fixup_path.FixupPath()

from chromite.lib import cros_test_lib
from chromite.lib import osutils
from chromite.lib.paygen import download_cache
from chromite.lib.paygen import gslib
from chromite.lib.paygen import unittest_lib


# We access a lot of protected members during testing.
# pylint: disable-msg=W0212

# The inProcess methods have to be standalone to be pickleable.
def _inProcessFetchIntoCache(uri_tempdir):
  """In a sub-process, call DownloadCache._UriToCacheFile."""
  try:
    uri, tempdir = uri_tempdir
    process_cache = download_cache.DownloadCache(tempdir)
    file_name = process_cache._UriToCacheFile(uri)
    with process_cache._PurgeLock(shared=True, blocking=True):
      return process_cache._FetchIntoCache(uri, file_name)
  except Exception:
    traceback.print_exc()
    raise


def _inProcessGetFile(uri_tempdir):
  """In a sub-process, call DownloadCache.GetFile."""

  try:
    uri, tempdir = uri_tempdir
    process_cache = download_cache.DownloadCache(tempdir, cache_size=0)

    # If there is a URI, fetch it, else wipe.
    if uri:
      with process_cache.GetFileObject(uri) as f:
        return f.read()
    else:
      process_cache.Purge()
      return None
  except Exception:
    traceback.print_exc()
    raise


class DownloadCachePickleTest(unittest_lib.TestCase):
  """Test pickle/unpickle the download cache."""

  @osutils.TempDirDecorator
  def testPickleUnpickle(self):
    # pylint: disable-msg=E1101
    cache = download_cache.DownloadCache(self.tempdir)
    pickle_path = os.path.join(self.tempdir, 'cache.pickle')

    # Do pickle dump.
    with open(pickle_path, 'w') as pickle_fh:
      pickle.dump(cache, pickle_fh)

    # Load pickle file.
    with open(pickle_path, 'r') as pickle_fh:
      pickle.load(pickle_fh)


class DownloadCacheTest(mox.MoxTestBase):
  """Test DownloadCache helper class."""

  def __init__(self, testCaseNames):
    self.tempdir = None
    mox.MoxTestBase.__init__(self, testCaseNames)

    self.uri_large = 'gs://chromeos-releases-test/download_cache/file_large'
    self.uri_a = 'gs://chromeos-releases-test/download_cache/file_a'
    self.uri_b = 'gs://chromeos-releases-test/download_cache/file_b'


    self.hash_large = 'ce11166b2742c12c93efa307c4c4adbf'
    self.hash_a = '591430f83b55355d9233babd172baea5'
    self.hash_b = '22317eb6cccea8c87f960c45ecec3478'

  def setUp(self):
    """Prepare for each test."""
    self.mox = mox.Mox()

    # To make certain we don't self update while running tests.
    os.environ['CROSTOOLS_NO_SOURCE_UPDATE'] = '1'

  def tearDown(self):
    """Cleanup after each test."""
    self.mox.UnsetStubs()

  def _verifyFileContents(self, cache, uri):
    """Test helper to make sure a cached file contains correct contents."""

    # Fetch it
    with cache.GetFileObject(uri) as f:
      contents = f.read()

    # Make sure the contents are valid.
    self.assertEqual(contents, gslib.Cat(uri))

    # Make sure the cache file exists where expected.
    cache_file = cache._UriToCacheFile(uri)

    self.assertTrue(cache_file.startswith(self.tempdir))
    self.assertTrue(os.path.exists(cache_file))

  def _validateCacheContents(self, cache, expected_contents):
    """Test helper to make sure the cache holds what we expect."""

    expected_contents = set(expected_contents)
    expected_top_contents = set(['cache', 'cache.lock', 'lock'])

    cache_top_contents = set(os.listdir(cache._cache_dir))
    file_dir_contents = set(os.listdir(cache._file_dir))
    lock_dir_contents = set(os.listdir(cache._lock_dir))

    # We should always have exactly the expected files in the top dir.
    self.assertEqual(cache_top_contents, expected_top_contents)

    # Cache contents should match the expected list.
    self.assertEqual(file_dir_contents, expected_contents)

    # The lock directory should contain no files not in the file_dir.
    self.assertTrue(lock_dir_contents.issubset(file_dir_contents))

  @osutils.TempDirDecorator
  def testCacheFileNames(self):
    """Make sure that some of the files we create have the expected names."""
    cache = download_cache.DownloadCache(self.tempdir)

    expected_cache_lock = os.path.join(self.tempdir, 'cache.lock')
    expected_cache = os.path.join(self.tempdir,
                                  'cache/3ba505fc7774455169af6f50b7964dff')

    expected_lock = os.path.join(self.tempdir,
                                 'lock/3ba505fc7774455169af6f50b7964dff')

    # Make sure a cache content file is named as expected.
    self.assertEqual(cache._UriToCacheFile('gs://bucket/of/awesome'),
                     expected_cache)

    # Make sure the lock file for a cache content file is named as expected.
    file_lock = cache._CacheFileLock(expected_cache)
    self.assertEqual(file_lock.lock_file, expected_lock)

    purge_lock = cache._PurgeLock()
    self.assertEqual(purge_lock.lock_file, expected_cache_lock)

    cache_file_lock = cache._CacheFileLock(expected_cache)
    self.assertEqual(cache_file_lock.lock_file, expected_lock)

  @osutils.TempDirDecorator
  def testSetupCacheClean(self):
    """Test _SetupCache with a clean directory."""
    # Create a cache, and see if it has expected contents.
    cache = download_cache.DownloadCache(self.tempdir)
    self._validateCacheContents(cache, ())

  @osutils.TempDirDecorator
  def testSetupCacheDirty(self):
    """Test _SetupCache with a dirty directory."""
    # Create some unexpected directories.
    for make_dir in ['foo/bar/stuff', 'bar']:
      os.makedirs(os.path.join(self.tempdir, make_dir))

    # Touch some unexpected files.
    for touch_file in ['bogus', 'foo/bogus']:
      file(os.path.join(self.tempdir, touch_file), 'w').close()

    # Create a cache, and see
    cache = download_cache.DownloadCache(self.tempdir)
    self._validateCacheContents(cache, ())

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testGetFileObject(self):
    """Just create a download cache, and GetFile on it."""

    cache = download_cache.DownloadCache(self.tempdir)

    # Fetch a file
    with cache.GetFileObject(self.uri_a) as f:
      self.assertIsInstance(f, file)
    self._verifyFileContents(cache, self.uri_a)
    self._validateCacheContents(cache, (self.hash_a,))

    # Fetch a different file
    with cache.GetFileObject(self.uri_b) as f:
      self.assertIsInstance(f, file)
    self._verifyFileContents(cache, self.uri_b)
    self._validateCacheContents(cache, (self.hash_a, self.hash_b))

    # Fetch the first file a second time.
    cache.GetFileObject(self.uri_a).close()
    self._verifyFileContents(cache, self.uri_a)

    # There should be only 2 files in the cache.
    self._validateCacheContents(cache, (self.hash_a, self.hash_b))

    # Fetch a larger file
    cache.GetFileObject(self.uri_large).close()
    self._verifyFileContents(cache, self.uri_large)

    # There should be 3 files in the cache.
    self._validateCacheContents(cache,
                                (self.hash_a, self.hash_b, self.hash_large))

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testGetFileCopy(self):
    """Just create a download cache, and GetFileCopy from it."""

    file_a = os.path.join(self.tempdir, 'foo')
    file_b = os.path.join(self.tempdir, 'bar')
    cache_dir = os.path.join(self.tempdir, 'cache')

    cache = download_cache.DownloadCache(cache_dir)

    # Fetch non-existent files.
    cache.GetFileCopy(self.uri_a, file_a)
    cache.GetFileCopy(self.uri_a, file_b)

    with open(file_a, 'r') as f:
      contents_a = f.read()

    with open(file_b, 'r') as f:
      contents_b = f.read()

    self.assertEqual(contents_a, contents_b)

    # Fetch and overwrite existent files.
    cache.GetFileCopy(self.uri_b, file_a)
    cache.GetFileCopy(self.uri_b, file_b)

    with open(file_a, 'r') as f:
      contents_a = f.read()

    with open(file_b, 'r') as f:
      contents_b = f.read()

    self.assertEqual(contents_a, contents_b)

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testGetFileInTempFile(self):
    """Just create a download cache, and GetFileInTempFile on it."""

    cache = download_cache.DownloadCache(self.tempdir)

    # Fetch a file
    file_t = cache.GetFileInTempFile(self.uri_a)

    with cache.GetFileObject(self.uri_a) as f:
      contents_a = f.read()

    with file_t as f:
      contents_t = f.read()

    self.assertEqual(contents_t, contents_a)
    self.assertEqual(contents_t, gslib.Cat(self.uri_a))

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testPurgeLogic(self):
    cache = download_cache.DownloadCache(self.tempdir)

    cache.GetFileObject(self.uri_a).close()
    cache.GetFileObject(self.uri_b).close()

    # The default cache logic should leave these files untouched, since
    # they are less than a day old.
    cache.Purge()
    self._validateCacheContents(cache, (self.hash_a, self.hash_b))

    # Purge until the cache is empty.
    cache.Purge(cache_size=0)
    self._validateCacheContents(cache, ())

    # Refetch two files.
    cache.GetFileObject(self.uri_a).close()
    cache.GetFileObject(self.uri_b).close()

    # Change the timestamp so uri_a hasn't been used for a very long time.
    os.utime(os.path.join(self.tempdir, 'cache', self.hash_a),
             (2, 2))

    # Purge files that haven't been used recently.
    cache.Purge(max_age=1000)
    self._validateCacheContents(cache, (self.hash_b,))

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testContextMgr(self):
    """Make sure we behave properly with 'with'."""

    # Create an instance, and use it in a with
    precache = download_cache.DownloadCache(self.tempdir, cache_size=0)

    with precache as cache:
      # Assert the instance didn't change.
      self.assertIs(precache, cache)

      # Download a file.
      cache.GetFileObject(self.uri_a).close()

      self._validateCacheContents(cache, (self.hash_a,))

    # After the with exited, which should have purged everything.
    self._validateCacheContents(cache, ())

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testThreadedDownloads(self):
    """Spin off multiple processes and fetch a file.

       Ensure the process locking allows the file to be downloaded exactly
       once.
    """
    pool = multiprocessing.Pool(processes=10)

    # Create a tuple of the three args we want to pass to inProcess test,
    # use map semantics as a convenient way to run in parallel.
    results = pool.map(_inProcessFetchIntoCache,
                       [(self.uri_large, self.tempdir)] * 20)

    # Results contains a list of booleans showing which instances actually
    # performed the download. Exactly one of them should have. The list could
    # also contain exceptions if one of the downloads failed.
    results.sort()
    self.assertEqual(results, [False] * 19 + [True])

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testThreadedGetFile(self):
    """Spin off multiple processes and call GetFile.

       Ensure all processes complete, and return the same local file.
    """
    pool = multiprocessing.Pool(processes=10)

    # Create a tuple of the three args we want to pass to inProcess test,
    # use map semantics as a convenient way to run in parallel.
    results = pool.map(_inProcessGetFile,
                       [(self.uri_a, self.tempdir)] * 20)

    # Fetch it ourselves and verify the results.
    cache = download_cache.DownloadCache(self.tempdir)
    self._verifyFileContents(cache, self.uri_a)

    with cache.GetFileObject(self.uri_a) as f:
      contents_a = f.read()

    # Ensure that every process gave back the expected result.
    expected = [contents_a] * 20
    self.assertEqual(results, expected)

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testThreadedGetFileMultiple(self):
    """Spin off multiple processes and call GetFile with multiple uris.

       Ensure all processes complete, and return the right local file.
    """
    pool = multiprocessing.Pool(processes=20)

    # Create a tuple of the three args we want to pass to inProcess test,
    # use map semantics as a convenient way to run in parallel.
    results = pool.map(_inProcessGetFile,
                       [(self.uri_a, self.tempdir),
                        (self.uri_b, self.tempdir)] * 10)

    # Fetch it ourselves and verify the results.
    cache = download_cache.DownloadCache(self.tempdir)

    with cache.GetFileObject(self.uri_a) as f:
      contents_a = f.read()

    with cache.GetFileObject(self.uri_b) as f:
      contents_b = f.read()

    self._verifyFileContents(cache, self.uri_a)
    self._verifyFileContents(cache, self.uri_b)

    # Ensure that every process gave back the expected result.
    expected = [contents_a, contents_b] * 10
    self.assertEqual(results, expected)

  @cros_test_lib.NetworkTest()
  @osutils.TempDirDecorator
  def testThreadedGetFileMultiplePurge(self):
    """Do fetches and purges in a multiprocess environment.

       Ensure all processes complete, and return the right local file.
    """
    pool = multiprocessing.Pool(processes=30)

    requests = [(self.uri_a, self.tempdir),
                (self.uri_b, self.tempdir),
                (None, self.tempdir)] * 10

    # Create a tuple of the three args we want to pass to inProcess test,
    # use map semantics as a convenient way to run in parallel.
    results = pool.map(_inProcessGetFile, requests)

    # Fetch it ourselves and verify the results.
    cache = download_cache.DownloadCache(self.tempdir)

    with cache.GetFileObject(self.uri_a) as f:
      contents_a = f.read()

    with cache.GetFileObject(self.uri_b) as f:
      contents_b = f.read()

    self._verifyFileContents(cache, self.uri_a)
    self._verifyFileContents(cache, self.uri_b)

    # Ensure that every process gave back the expected result.
    expected = [contents_a, contents_b, None] * 10
    self.assertEqual(results, expected)


if __name__ == '__main__':
  cros_test_lib.main()