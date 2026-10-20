import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('listing',ROOT/'web/directory_listing.py')
listing=importlib.util.module_from_spec(spec);spec.loader.exec_module(listing)
class ListingTests(unittest.TestCase):
 def setUp(self): listing._cache.clear()
 def test_scandir_result_reused_and_manual_refresh_sees_new_folders(self):
  with tempfile.TemporaryDirectory() as folder:
   (Path(folder)/'season1').mkdir()
   real=listing.os.scandir
   with patch.object(listing.os,'scandir',wraps=real) as scan:
    a=listing.directory_html(folder,True)
    (Path(folder)/'season2').mkdir()
    self.assertEqual(a,listing.directory_html(folder,True))
    self.assertEqual(scan.call_count,1)
    self.assertIn('season2',listing.directory_html(folder,True,refresh=True))
    self.assertEqual(scan.call_count,2)
 def test_filters_files_and_escapes_untrusted_names(self):
  with tempfile.TemporaryDirectory() as folder:
   (Path(folder)/'A & B').mkdir();(Path(folder)/'video.mp4').write_text('fixture')
   html=listing.directory_html(folder,True)
   self.assertIn('A &amp; B',html);self.assertNotIn('video.mp4',html)
   self.assertIn('video.mp4',listing.directory_html(folder,False))
 def test_failure_has_actionable_message(self):
  self.assertIn('fti-path-error',listing.directory_html('/nonexistent-film-index-path'))
 def test_pt_legacy_settings_do_not_restore_features(self):
  import media_profile
  for name in ('indexer','downloader','download_setting','douban','upload'): self.assertIn(name,media_profile.REMOVED_PAGES)
  for name in ('add_downloader','delete_downloader','get_downloader','get_indexers','update_download_setting'):self.assertFalse(media_profile.action_allowed(name,{}))
if __name__=='__main__':unittest.main()
