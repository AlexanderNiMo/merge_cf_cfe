import configparser
import pathlib
import typing


class Config:

    def __init__(self, conf_parser: configparser.ConfigParser):

        self.extension_dir = pathlib.Path(conf_parser.get('path', 'extension_dir')).absolute().resolve()
        self.temp_dir = pathlib.Path(conf_parser.get('path', 'temp_dir')).absolute().resolve()
        self.base_xml = pathlib.Path(conf_parser.get('path', 'base_xml')).absolute().resolve()

        self.base_user = conf_parser.get('base', 'user')
        self.base_password = conf_parser.get('base', 'password')
        self.base_path = conf_parser.get('base', 'path')
        self.base_server = conf_parser.get('base', 'server')
        self.base_ref = conf_parser.get('base', 'ref')

        self.repo_path = conf_parser.get('repo', 'path')
        self.repo_user = conf_parser.get('repo', 'user')
        self.repo_password = conf_parser.get('repo', 'password')

        self.platform_version = conf_parser.get('1c', 'version')


def get_config(conf_file: typing.Optional[pathlib.Path] = None):

    conf_path = str(conf_file)
    if conf_file is None or not conf_file.exists():
        conf_path = '../../config.example.ini'

    parser = configparser.ConfigParser()
    parser.read(pathlib.Path(conf_path).resolve(), encoding='utf-8')

    return Config(parser)
