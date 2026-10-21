import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
import film_index
spec=importlib.util.spec_from_file_location('film_ffmpeg_helper_test',Path(film_index.__file__).parent/'media/app/helper/ffmpeg_helper.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
FfmpegHelper=module.FfmpegHelper

class ThumbnailTests(unittest.TestCase):
    def test_input_seek_timeout_and_atomic_success(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'含空格 thumb.jpg'
            def generate(command, **kwargs):
                self.assertLess(command.index('-ss'),command.index('-i'))
                self.assertEqual(command[command.index('-i')+1],'/media/片名 $(literal).mkv')
                self.assertEqual(kwargs['timeout'],15)
                self.assertNotIn('shell',kwargs)
                self.assertNotEqual(command[-1],str(target))
                Path(command[-1]).write_bytes(b'\xff\xd8fixture\xff\xd9')
                return Mock(returncode=0)
            with patch.object(module.subprocess,'run',side_effect=generate):
                self.assertTrue(FfmpegHelper.get_thumb_image_from_video('/media/片名 $(literal).mkv',target))
            self.assertEqual(target.read_bytes(),b'\xff\xd8fixture\xff\xd9')
            self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_timeout_failure_and_partial_output_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'thumb.jpg'
            def timeout(command,**kwargs):
                Path(command[-1]).write_bytes(b'partial')
                raise subprocess.TimeoutExpired(command,15)
            with patch.object(module.subprocess,'run',side_effect=timeout):
                self.assertFalse(FfmpegHelper.get_thumb_image_from_video('file.mkv',target))
            self.assertEqual(list(Path(directory).iterdir()),[])
            with patch.object(module.subprocess,'run',return_value=Mock(returncode=1)):
                self.assertFalse(FfmpegHelper.get_thumb_image_from_video('file.mkv',target))

    def test_existing_thumbnail_is_not_decoded_or_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'thumb.jpg';target.write_bytes(b'existing-image')
            with patch.object(module.subprocess,'run') as run:
                self.assertTrue(FfmpegHelper.get_thumb_image_from_video('file.mkv',target))
                run.assert_not_called()
            self.assertEqual(target.read_bytes(),b'existing-image')
