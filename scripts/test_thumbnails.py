"""Check the FFmpeg actually shipped in the image, using only synthetic video."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import film_index
spec=importlib.util.spec_from_file_location('film_ffmpeg_image_test',Path(film_index.__file__).parent/'media/app/helper/ffmpeg_helper.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);video=root/'test video.mp4';image=root/'test thumb.jpg'
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=1280x720:d=3','-c:v','mpeg4','-threads','1',str(video)],check=True,timeout=15)
    assert module.FfmpegHelper.get_thumb_image_from_video(video,image,frames='00:00:01')
    from PIL import Image
    with Image.open(image) as thumb:
        assert thumb.format=='JPEG' and thumb.width<=640 and thumb.height>0
    assert len(list(root.iterdir()))==2
    print('PASS: bundled FFmpeg fast-seek generates a real bounded JPEG from synthetic video')
