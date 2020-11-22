from designer_cmd import api
from commit_by_extension import config as conf
import pathlib
import logging
import os
from typing import List
from commit_by_extension.merging import Merger
from multiprocessing import Process

logging.basicConfig(filename='./working.log', level=logging.INFO)
logger = logging.getLogger(__file__)


def main(config: conf.Config):

    extensions = get_extensions(config.extension_dir)

    if not extensions:
        logger.info('Файлы расширений не обнаруженны.')
        return

    designer = create_designer(config)

    tmp_designer, extension_xml_dir = prepare_env(config.temp_dir, config.platform_version)
    main_xml_path = config.base_xml

    p = Process(target=update_main_base_from_repo, args=(designer, main_xml_path))
    p.start()

    xml_extension_paths = []

    for extension in extensions:
        tmp_designer.load_extension_from_file(str(extension.absolute().resolve()), extension.name)
        xml_extension_paths.append(extension_xml_dir.joinpath(extension.name))
    tmp_designer.dump_extensions_to_files(extension_xml_dir)

    result = p.join()

    os.remove(main_xml_path.joinpath('ConfigDumpInfo.xml'))

    p = None

    for xml_extension_path in xml_extension_paths:
        merger = Merger(main_xml_path, xml_extension_path, config.temp_dir)
        merge_settings, object_list, list_files = merger.merge()

        cf_path = config.temp_dir.joinpath(f'{xml_extension_path.name}.cf')
        convert_xml_to_cf(tmp_designer, main_xml_path, cf_path, list_files)

        if p is not None:
            result = p.join()
        p = Process(target=make_commit, args=(designer, cf_path, merge_settings, object_list))
        p.start()

    if p is not None:
        result = p.join()


def update_main_base_from_repo(designer: api.Designer, main_xml_path: pathlib.Path):
    designer.update_conf_from_repo()
    designer.dump_config_to_files(str(main_xml_path))


def convert_xml_to_cf(designer, xml_path: pathlib.Path, cf_path: pathlib.Path, list_files: pathlib.Path):
    designer.load_config_from_files(str(xml_path), str(list_files))
    designer.dump_config_to_file(str(cf_path))


def make_commit(designer: api.Designer, cf_path: pathlib.Path, merge_settings: pathlib.Path, object_list: pathlib.Path):
    designer.lock_objects_in_repository(str(object_list))
    designer.merge_config_with_file(str(cf_path), str(merge_settings))
    designer.commit_config_to_repo(f'Слияние c расширением {cf_path.name}', str(object_list))
    designer.unlock_objects_in_repository(str(object_list))


def prepare_env(temp_dir_path: str, v8_version: str) -> (api.Designer, pathlib.Path, pathlib.Path):
    temp_dir = pathlib.Path(temp_dir_path)
    if not temp_dir.exists():
        temp_dir.mkdir()

    extension_xml_dir = temp_dir.joinpath('extension_xml')
    if not extension_xml_dir.exists():
        extension_xml_dir.mkdir()

    temp_base_path = temp_dir.joinpath('tmp_base')
    if not temp_base_path.exists():
        temp_base_path.mkdir()

    tmp_connection = api.Connection(file_path=temp_base_path)
    tmp_designer = api.Designer(platform_version=v8_version, connection=tmp_connection)

    return tmp_designer, extension_xml_dir


def get_extensions(path: str) -> List[pathlib.Path]:

    res = []

    ext_dir = pathlib.Path(path)
    if not ext_dir.exists():
        logger.error('Не существует папка с расширениями!')
        raise ValueError(f'Папка с расширениями {ext_dir} не существует!')

    for element in ext_dir.iterdir():
        if element.is_file() and element.suffix == '.cfe':
            logger.debug(f'Добавление расширения из файла {element} в обработку')
            res.append(element)

    return res


def create_designer(config: conf.Config) -> api.Designer:
    repo_connection = api.RepositoryConnection(config.repo_path, config.repo_user, config.repo_password)
    conn = None
    if config.base_server != '':
        logger.debug(f'Формирование подключения к БД с параметрами: '
                     f'server_path:{config.base_server} server_base_ref:{config.base_ref}')
        conn = api.Connection(
            config.base_user, config.base_password, server_path=config.base_server, server_base_ref=config.base_ref)
    elif config.base_path != '':
        logger.debug(f'Формирование подключения к БД с параметрами: '
                     f'file_path:{config.base_path}')
        conn = api.Connection(
            config.base_user, config.base_password, file_path=config.base_path)

    if conn is None:
        logger.error('Не удалось определить парметры подключения к БД!')
        raise ValueError('Не удалось определить парметры подключения к БД')

    return api.Designer(config.platform_version, connection=conn, repo_connection=repo_connection)
