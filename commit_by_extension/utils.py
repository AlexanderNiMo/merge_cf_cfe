import shutil
import os
import os.path as path
from typing import Union
import pathlib


def clear_folder(dir_path: Union[str, pathlib.Path]):
    if path.exists(dir_path):
        filelist = [f for f in os.listdir(dir_path)]
        for file_name in filelist:
            if '.gitkeep' in file_name:
                continue
            file_path = path.join(dir_path, file_name)
            if path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)