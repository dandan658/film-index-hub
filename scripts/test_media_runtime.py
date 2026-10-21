"""Exercise real media initialization, HTTP adapter, identification and path format."""
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from film_index.runtime import create_app
os.environ['ADMIN_PASSWORD']='test-only-password'
root=Path(tempfile.mkdtemp(prefix='film-media-runtime-'))
app=create_app(root,start_services=False)
from film_index.subscriptions import web_app
web_app.storage=Mock(config={'tmdb':{'credential':'a'*32}})
from film_index.media.config import Config
config=Config()
config._config['app']['rmt_tmdbkey']=''
config._config['app']['proxies']=None
config._config['app']['tmdb_domain']=''
from film_index.media.app.media import Media
from film_index.media.app.utils.types import MediaType, RmtMode, SyncType
from film_index.media.app.filetransfer import FileTransfer
from film_index.media.app.media.tmdbv3api.tmdb import TMDb
TMDb.cached_request.cache_clear()
media=Media();media.init_config()
assert media.tmdb is not None
fixture={'id':226045,'name':'大主宰','original_name':'大主宰','original_language':'zh','first_air_date':'2023-06-30','genres':[{'id':16,'name':'动画'}],'origin_country':['CN'],'vote_average':8,'overview':'fixture','seasons':[{'season_number':1,'episode_count':100}]}
with patch('requests.request',return_value=Mock(status_code=200,headers={},json=lambda:dict(fixture))) as request:
    info=media.get_tmdb_info(mtype=MediaType.TV,tmdbid=226045,chinese=False)
    assert info and info['name']=='大主宰'
    source=root/'source/大主宰 (2023)/大主宰 - S01E01.mp4'
    source.parent.mkdir(parents=True);source.write_bytes(b'test-only')
    identified=media.get_media_info_on_files([str(source)],tmdb_info=info,media_type=MediaType.TV,chinese=False)
    assert identified, 'media identification returned empty'
    metadata=next(iter(identified.values()))
    folder,season,filename=FileTransfer().get_tv_dest_path(metadata)
    assert '大主宰' in folder and '2023' in folder,(folder,season,filename)
    assert '1' in season and 'S01E01' in filename,(folder,season,filename)
    assert request.call_args.kwargs['proxies'] is None
    if os.name == 'posix':
        config._config.setdefault('media', {})['nfo_poster'] = False
        transfer=FileTransfer();transfer.init_config()
        target=root/'target';target.mkdir()
        result, message=transfer.transfer_media(in_from=SyncType.MON,in_path=str(source),files=[str(source)],target_dir=str(target),tmdb_info=info,media_type=MediaType.TV,rmt_mode=RmtMode.MOVE,min_filesize=0)
        assert result, message
        transferred=list(target.rglob('*.mp4'))
        assert len(transferred)==1 and not source.exists(), (message, transferred)
        assert '大主宰' in str(transferred[0]) and 'S01E01' in transferred[0].name
        print('PASS: real directory-sync move of a synthetic media file',flush=True)
    from film_index.media.web.action import WebAction
    activity=WebAction._WebAction__logging({'source':'DirectorySync','refresh_new':0})
    assert any(item['source']=='Meta' for item in activity['loglist'])
    print('PASS: shared TMDB credential, no proxy, real TV identification, year/season/episode destination',flush=True)

# Exercise the real selection method independently of transport and file moving.
from types import SimpleNamespace
from film_index.media.app.media.tmdbv3api.exceptions import TMDbException
images=Mock(return_value=[{'file_path':'/neutral.jpg','iso_639_1':None}])
with patch.object(media,'episode',SimpleNamespace(images=images)):
    with patch.object(media,'get_tmdb_tv_season_detail',return_value={'episodes':[{'episode_number':1,'still_path':'/wrong-episode.jpg'},{'episode_number':2,'still_path':'/correct-episode.jpg'}]}) as season:
        assert media.get_episode_images(303287,'1','2',True).endswith('/correct-episode.jpg')
        season.assert_called_once_with(tmdbid=303287,season=1)
        images.assert_not_called()
    with patch.object(media,'get_tmdb_tv_season_detail',return_value={'episodes':[{'episode_number':2,'still_path':None}]}):
        assert media.get_episode_images(303287,1,2,True).endswith('/neutral.jpg')
        images.return_value=[]
        assert media.get_episode_images(303287,1,2,True)==''
        images.side_effect=TMDbException('fixture network error')
        try:
            media.get_episode_images(303287,1,2,True)
        except TMDbException:
            pass
        else:
            raise AssertionError('image lookup errors must not be treated as no image')
print('PASS: exact season/episode still_path, neutral image fallback, confirmed no-image and query error distinction',flush=True)

from film_index.media.app.media.scraper import Scraper
from film_index.media.app.helper.ffmpeg_helper import FfmpegHelper
scraper=Scraper()
thumb_dir=root/'thumbnail-selection';thumb_dir.mkdir()
options={'tv':{'episode_thumb':True}}
with patch.object(scraper.media,'get_episode_images',return_value='https://image.tmdb.org/t/p/original/correct.jpg'), patch.object(Scraper,'_Scraper__save_image') as save, patch.object(FfmpegHelper,'get_thumb_image_from_video') as capture:
    scraper.gen_scraper_files(metadata,{'tv':{}},options,str(thumb_dir),'episode','.mp4')
    save.assert_called_once()
    capture.assert_not_called()
with patch.object(scraper.media,'get_episode_images',side_effect=TMDbException('fixture error')), patch.object(FfmpegHelper,'get_thumb_image_from_video') as capture:
    scraper.gen_scraper_files(metadata,{'tv':{}},options,str(thumb_dir),'episode','.mp4')
    capture.assert_not_called()
with patch.object(scraper.media,'get_episode_images',return_value=''), patch.object(FfmpegHelper,'get_thumb_image_from_video',return_value=False) as capture:
    scraper.gen_scraper_files(metadata,{'tv':{}},options,str(thumb_dir),'episode','.mp4')
    capture.assert_called_once()
print('PASS: real scraper downloads TMDB image first and decodes video only on confirmed no-image',flush=True)
