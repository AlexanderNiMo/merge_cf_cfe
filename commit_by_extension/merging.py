import pathlib
import mdclasses
from typing import Optional, Union
from commit_by_extension.utils import clear_folder
import shutil
from lxml import etree
import re


class MergeError(Exception):
    pass


class Merger:

    def __init__(self, cf_xml_path: pathlib.Path,
                 cfe_xml_path: pathlib.Path,
                 temp_dir: pathlib.Path):

        self._cfe_xml_path = cfe_xml_path
        self._cf_xml_path = cf_xml_path

        self._extension_name = self._cfe_xml_path.stem

        self._temp_dir = temp_dir.joinpath(self._extension_name)
        if not self._temp_dir.exists():
            self._temp_dir.mkdir()

        self.merge_settings = temp_dir.joinpath(f'{self._extension_name}_merge_settings.xml')
        self.object_list = temp_dir.joinpath(f'{self._extension_name}_object_list.xml')
        self.list_files = temp_dir.joinpath(f'{self._extension_name}_changed_files.lst')

        self.version = '1.2'
        self.platform_version = '8.3.11'

        self._main_conf: Optional[mdclasses.Configuration] = None
        self._extension: Optional[mdclasses.Configuration] = None

    def read_data(self):
        if self._main_conf is None:
            self._main_conf = mdclasses.read_configuration(str(self._cf_xml_path))

        if self._extension is None:
            self._extension = mdclasses.read_configuration(str(self._cfe_xml_path))

    def merge(self) -> (pathlib.Path, pathlib.Path, pathlib.Path):

        self.read_data()

        try:

            for obj in self._extension.conf_objects:
                if obj.obj_type == mdclasses.ObjectType.LANGUAGE:
                    continue
                try:
                    main_obj = self._main_conf.get_object(obj.name, obj.obj_type)
                except IndexError:
                    if obj.obj_type != mdclasses.ObjectType.ROLE:
                        add_object_to_conf(self._main_conf, obj)
                        self.add_object_to_confs(obj)
                    continue

                self.merge_objects(main_obj, obj)
                self.add_object_to_confs(main_obj)

        except NotImplementedError as ex:
            raise MergeError(f'Ошибка объединения модулей {ex.args[0]}')

        return self.merge_settings, self.object_list, self.list_files

    def merge_objects(self, main_obj: mdclasses.ConfObject, obj: mdclasses.ConfObject):
        obj_modules = get_obj_module(obj)
        main_modules = get_obj_module(main_obj)

        for module in obj_modules:
            try:
                main_module = next(filter(lambda m: m.name == module.name, main_modules))
                self.merge_module(main_module, module)
                main_module.save_to_file()
            except StopIteration:
                main_module = None
                self.add_module(main_obj, module)

    def add_object_to_confs(self, obj: mdclasses.ConfObject):
        """
        Добавляет описание объекта в настройки (merge_settings, object_list)
        :param obj:
        :return:
        """

        self.add_obj_to_merge(obj)
        self.add_obj_to_list(obj)

    def add_obj_to_merge(self, obj: mdclasses.ConfObject):
        data_settings = self.get_xml_struct_merge_setting()
        objects = data_settings.find('Objects')

        object = etree.Element(
            'Object',
            attrib={
                'fullName': obj.full_name
            }
        )
        merge_rule = etree.Element('MergeRule')
        merge_rule.text = 'GetFromSecondConfiguration'
        object.append(
            merge_rule
        )
        objects.append(object)
        self.merge_settings.write_bytes(
            etree.tostring(data_settings, xml_declaration=False, encoding='utf-8')
        )

    def get_xml_struct_merge_setting(self) -> etree.ElementBase:
        if self.merge_settings.exists():
            return etree.fromstring(self.merge_settings.read_text('utf-8'))
        else:
            element = etree.Element(
                'Settings',
                attrib={
                    "version": self.version,
                    "platformVersion": str(self.platform_version)
                },
                nsmap={
                    None: "http://v8.1c.ru/8.3/config/merge/settings",
                    "xs": "http://www.w3.org/2001/XMLSchema",
                    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                }
            )
            e_params = etree.Element('Parameters')

            e_param = etree.Element('ConfigurationsRelation')
            e_param.text = 'SecondConfigurationIsDescendantOfMainConfiguration'
            e_params.append(e_param)

            e_param = etree.Element('AllowMainConfigurationObjectDeletion')
            e_param.text = 'true'
            e_params.append(e_param)

            e_param = etree.Element('CopyObjectsMode')
            e_param.text = 'false'
            e_params.append(e_param)

            element.append(e_params)

            e_objects = etree.Element('Objects')
            element.append(e_objects)
            self.merge_settings.write_bytes(
                etree.tostring(element, xml_declaration=True, encoding='utf-8')
            )
            return element

    def add_obj_to_list(self, obj: mdclasses.ConfObject):
        data_obj_list = self.get_xml_struct_object_list()
        objects = data_obj_list

        objects.append(etree.Element(
            'Object',
            attrib={
                'fullName': obj.full_name,
                'includeChildObjects': 'true'
            }
        ))
        self.object_list.write_bytes(
            etree.tostring(data_obj_list, xml_declaration=False, encoding='utf-8')
        )

    def get_xml_struct_object_list(self) -> etree.ElementBase:
        if self.object_list.exists():
            return etree.fromstring(self.object_list.read_bytes())
        else:
            element = etree.Element(
                'Objects',
                attrib={
                    "version": '1.0',
                },
                nsmap={
                    None: "http://v8.1c.ru/8.3/config/objects"
                }
            )

            self.object_list.write_bytes(
                etree.tostring(element, xml_declaration=False, encoding='utf-8')
            )
            return element

    def merge_module(self, receiver: mdclasses.Module, source: mdclasses.Module):
        for proc in source.procedures():
            if proc.expansion_modifier is None:
                continue
            main_proc = receiver.find_sub_program(proc.expansion_modifier.sub_program_name)
            self.merge_procedure(main_proc, proc)

        for func in source.functions():
            if func.expansion_modifier is None:
                continue

        insert_text_to_module(
            receiver,
            f'\n#Область ИмпортИзРасширения_{self._extension_name}',
            source.module_main_text
        )

        if source.module_variables_text == '':
            return

        insert_text_to_module(
            receiver,
            f'\n#Область Переменные_ИмпортИзРасширения_{self._extension_name}',
            source.module_variables_text,
            0,
            0
        )

    def merge_procedure(self, resiver: mdclasses.Procedure, sourse: mdclasses.Procedure):
        modifier_type = sourse.expansion_modifier.modifier_type
        sourse.expansion_modifier = None
        if modifier_type.upper() == 'После'.upper():
            insert_text_to_module(
                resiver,
                f'#Область {resiver.name}_ИмпортИзРасширения_{self._extension_name}',
                f'\t{sourse.call_text}\n',
                1
            )
        elif modifier_type.upper() == 'Перед'.upper():
            insert_text_to_module(
                resiver,
                f'#Область {resiver.name}_ИмпортИзРасширения_{self._extension_name}',
                f'\t{sourse.call_text}\n',
                1,
                0
            )
        else:
            self.merge_union(resiver, sourse)

    def merge_function(self, resiver: mdclasses.Procedure, sourse: mdclasses.Procedure):
        modifier_type = sourse.expansion_modifier.modifier_type
        sourse.expansion_modifier = None

        if modifier_type.upper() == 'Вместо'.upper():
            self.merge_union(resiver, sourse)
        else:
            raise NotImplementedError(f'Функции поддерживают только режим Вместо, найден режим {modifier_type}')

    def merge_union(self, resiver: mdclasses.Procedure, sourse: mdclasses.Procedure):
        continue_all = 'ПродолжитьВызов('
        continue_call_re = re.compile('', re.IGNORECASE)

        if continue_all.upper() in sourse.text.upper():
            sourse.name = resiver.name
            resiver.name = f'changed_{resiver.name}'
            for el in sourse.elements:
                if isinstance(el, mdclasses.TextData) and continue_all.upper() in el.text:
                    el.text_data = continue_call_re.sub(el.text, f'{resiver.name}(')
        else:
            resiver.clear_sub_elements()
            insert_text_to_module(
                resiver,
                f'#Область {resiver.name}_ИмпортИзРасширения_{self._extension_name}',
                f'\t{sourse.call_text}\n',
                1
            )

    def add_module(self, obj: mdclasses.ConfObject, module: mdclasses.Module):
        """
        Добавляет модуль в объект
        :param obj:
        :param module:
        :return:
        """
        if not obj.ext_path.exists():
            obj.ext_path.mkdir()
        shutil.copyfile(module.file_name, obj.ext_path.joinpath(module.file_name.name))
        self.list_files.write_text(str(obj.ext_path.joinpath(module.file_name.name)))

    def clear_temp(self):
        clear_folder(self._temp_dir)
        self._temp_dir.rmdir()


def get_obj_module(obj: mdclasses.ConfObject):
    obj.read_modules()
    obj_modules = obj.modules
    try:
        obj.read_forms()
        obj_modules.extend([form.module for form in obj.forms])
    except ValueError:
        pass
    return obj_modules


def add_object_to_conf(main_conf: mdclasses.Configuration, obj: mdclasses.ConfObject) -> list:
    """
    Модификация файла Configuration.xml
    :param main_conf:
    :param obj:
    :return:
    """

    main_conf.expansion_modifier = None
    pass


def insert_text_to_module(receiver: Union[mdclasses.Module, mdclasses.Procedure],
                          region_name: str, text: str, level: int = 0, index: int = -1):
    tabs = '\t'*level
    new_lines = [f'{tabs}{region_name}',
                 '',
                 tabs.join(text.splitlines(keepends=True)),
                 f'{tabs}#КонецОбласти',
                 '']
    new_text = '\n'.join(new_lines)

    start_line = receiver.text_range.end_line + 1
    end_line = start_line + len(new_lines)
    if index != -1:
        start_line = receiver.elements[index].text_range.end_line + 1
        end_line = start_line + len(new_lines)

    ext_text_block = mdclasses.TextData(new_text, start_line,end_line)

    if index == -1:
        receiver.add_sub_element(ext_text_block)
    else:
        receiver.insert_sub_element(ext_text_block, 0)