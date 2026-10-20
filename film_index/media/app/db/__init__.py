import os
from film_index.media import log
from film_index.media.config import Config
from .main_db import MainDb
from .main_db import DbPersist
from .media_db import MediaDb
from alembic.config import Config as AlembicConfig
from alembic.command import upgrade as alembic_upgrade, stamp as alembic_stamp
from sqlalchemy import inspect
from sqlalchemy.schema import CreateColumn
from .models import Base
from .main_db import _Engine


def init_db():
    """
    初始化数据库
    """
    log.console('开始初始化数据库...')
    MediaDb().init_db()
    MainDb().init_db()
    log.console('数据库初始化完成')


def init_data():
    """
    初始化数据
    """
    log.console('开始初始化数据...')
    MainDb().init_data()
    log.console('数据初始化完成')


def update_db():
    """
    更新数据库
    """
    db_location = os.path.join(Config().get_config_path(), 'user.db')
    script_location = os.path.join(Config().get_root_path(), 'db_scripts')
    log.console('开始更新数据库...')
    try:
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option('script_location', script_location)
        alembic_cfg.set_main_option('sqlalchemy.url', f"sqlite:///{db_location}")
        # Upgrade additively: never run the old migration's DROP TABLE/column steps.
        with _Engine.begin() as connection:
            schema = inspect(connection)
            quote = connection.dialect.identifier_preparer.quote
            for table in Base.metadata.sorted_tables:
                existing = {c['name'] for c in schema.get_columns(table.name)}
                for column in table.columns:
                    if column.name not in existing:
                        if column.primary_key:
                            raise ValueError('原媒体表缺少主键：' + table.name)
                        definition = str(CreateColumn(column).compile(dialect=connection.dialect))
                        connection.exec_driver_sql('ALTER TABLE ' + quote(table.name) + ' ADD COLUMN ' + definition)
                if table.name == 'TRANSFER_HISTORY':
                    for old, new in (('FILE_PATH','SOURCE_PATH'), ('FILE_NAME','SOURCE_FILENAME'), ('SE','SEASON_EPISODE')):
                        if old in existing:
                            connection.exec_driver_sql('UPDATE ' + quote(table.name) + ' SET ' + quote(new) + '=' + quote(old) + ' WHERE ' + quote(new) + ' IS NULL')
        alembic_stamp(alembic_cfg, 'head')
    except Exception as e:
        raise RuntimeError("媒体数据库升级失败，原数据已备份，停止启动") from e
    log.console('数据库更新完成')
