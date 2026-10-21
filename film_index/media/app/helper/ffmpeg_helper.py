"""Bounded, low-resource thumbnails without shell invocation."""
import os
from pathlib import Path
import subprocess
import uuid

class FfmpegHelper:
    TIMEOUT_SECONDS = 15

    @staticmethod
    def get_thumb_image_from_video(video_path, image_path, frames="00:03:01"):
        if not video_path or not image_path:
            return False
        target = Path(image_path)
        temporary = target.with_name('.' + target.stem + '.' + uuid.uuid4().hex + '.jpg')
        try:
            if target.is_file() and target.stat().st_size > 0:
                return True
            # Input seeking avoids decoding the first three minutes, especially
            # costly for a cloud-mounted video. Limit both decoder and encoder.
            command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                       '-ss', str(frames), '-threads', '1', '-i', str(video_path),
                       '-map', '0:v:0', '-frames:v', '1', '-an', '-sn',
                       '-vf', "scale='min(640,iw)':-2", '-threads', '1', '-q:v', '3',
                       '-f', 'image2', str(temporary)]
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, timeout=FfmpegHelper.TIMEOUT_SECONDS,
                                    check=False)
            if result.returncode != 0 or not temporary.is_file():
                return False
            with temporary.open('rb') as image:
                if image.read(2) != b'\xff\xd8':
                    return False
                image.seek(-2, os.SEEK_END)
                if image.read(2) != b'\xff\xd9':
                    return False
            # Do not replace an image another worker completed while decoding.
            if not target.exists() or target.stat().st_size == 0:
                os.replace(temporary, target)
            return target.is_file() and target.stat().st_size > 0
        except (OSError, subprocess.TimeoutExpired):
            return False
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
