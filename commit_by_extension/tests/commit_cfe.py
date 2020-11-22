import unittest
from commit_by_extension import config, commit, utils, merging
import mdclasses
from pathlib import Path
from designer_cmd import api
import shutil


class MainTest(unittest.TestCase):

    def setUp(self) -> None:

        self.dt_path = Path('test_data').joinpath('1Cv8.dt')
        self.cf_path = Path('test_data').joinpath('1Cv8.cf')

        self.config = config.get_config()

        self.obj_list_all = Path('test_data/obj_list_all_objects').resolve()
        self.merge_settings = Path('test_data/MergeSettings.xml').resolve()

        repo_connection = api.RepositoryConnection(self.config.repo_path,
                                                   self.config.repo_user,
                                                   self.config.repo_password)
        self.prepare_repo(repo_connection)
        self.prepare_base(repo_connection)

    def prepare_repo(self, repo_connection):

        tmp_base = self.config.temp_dir.joinpath('tmp_base').resolve()
        connection = api.Connection('', '', str(tmp_base))
        designer = api.Designer(self.config.platform_version, connection, repo_connection)

        designer.create_base()
        if 'data' not in [e.name for e in  Path(self.config.repo_path).iterdir()]:
            designer.create_repository()

        designer.lock_objects_in_repository(str(self.obj_list_all))
        designer.merge_config_with_file(self.cf_path, self.merge_settings)
        designer.commit_config_to_repo('test', str(self.obj_list_all))
        designer.unlock_objects_in_repository(str(self.obj_list_all))

        utils.clear_folder(str(tmp_base))
        tmp_base.rmdir()

    def prepare_base(self, repo_connection):
        connection = api.Connection(self.config.base_user, self.config.base_password, str(self.config.base_path))
        designer = api.Designer(self.config.platform_version, connection, repo_connection)
        designer.create_base()
        designer.bind_cfg_to_repo()
        designer.update_conf_from_repo()
        designer.update_db_config()

    def test_get_extension(self):
        extensions = commit.get_extensions(self.config.extension_dir)

        self.assertEqual(
            [e.name for e in extensions], ['catalog_module.cfe', 'form_default.cfe', 'form_method.cfe', 'module.cfe']
        )

    def test_prepare_env(self):
        tmp_designer, extension_xml_dir, main_xml_path = commit.prepare_env(
            self.config.temp_dir, self.config.platform_version)

        self.assertTrue(Path(main_xml_path).exists(), 'Не создана папка для выгрузки'
                                                      ' основной конфы в xml')
        self.assertTrue(Path(extension_xml_dir).exists(), 'Не создана папка для выгрузки'
                                                          ' основной конфы в xml')
        self.assertTrue(Path(f'{self.config.temp_dir}/tmp_base').exists(), 'Не создана папка для базы'
                                                                           ' основной конфы в xml')

    def test_main(self):
        commit.main(self.config)
        a=1

    def tearDown(self) -> None:
        utils.clear_folder(self.config.temp_dir)
        utils.clear_folder(self.config.repo_path)
        utils.clear_folder(self.config.base_path)


class TestMerging(unittest.TestCase):

    def setUp(self) -> None:
        self.cf_xml = Path('test_data/xml_data/main_xml').absolute().resolve()
        self.cfe_xml = Path('test_data/xml_data/extension_xml').absolute().resolve()
        self.tmp_cf_xml = Path('test_data/xml_data/tmp').absolute().resolve()
        self.xml_data_path = Path('test_data/xml_data').absolute().resolve()
        shutil.copytree(self.cf_xml, self.tmp_cf_xml)

        self.encoding = 'utf-8-sig'

        self.temp_dir = Path('test_data/xml_data/tmp_settings')
        self.temp_dir.mkdir()

    def test_merge_cf_cfe(self):

        merger = merging.Merger(self.tmp_cf_xml, self.cfe_xml, self.temp_dir)
        merger.merge()
        module_path = self.tmp_cf_xml.joinpath('Catalogs', 'Справочник1', 'Ext', 'ManagerModule.bsl')
        example_module = self.xml_data_path.joinpath('ExampleMergeModule.bsl')

        self.assertEqual(example_module.read_text(self.encoding),
                         module_path.read_text(self.encoding),
                         'Данные перенесены не верно')

    def test_add_module(self):

        merger = merging.Merger(self.tmp_cf_xml, self.cfe_xml, self.temp_dir)
        merger.read_data()
        obj = merger._main_conf.get_object('Справочник3', mdclasses.ObjectType.CATALOG)

        ext_module = merger._extension.get_object('Справочник1', mdclasses.ObjectType.CATALOG)
        ext_module.read_modules()
        test_module = ext_module.modules[0]

        merger.add_module(obj, test_module)

        new_path = obj.ext_path.joinpath(test_module.file_name.name)

        self.assertTrue(new_path.exists(), 'Не перенсен модуль.')
        self.assertIn(test_module.file_name.name, merger.list_files.read_text(), 'Измененный файл не отражен в списке файлов')

    def tearDown(self) -> None:
        utils.clear_folder(self.tmp_cf_xml)
        self.tmp_cf_xml.rmdir()
        utils.clear_folder(self.temp_dir)
        self.temp_dir.rmdir()


if __name__ == '__main__':
    unittest.main()
