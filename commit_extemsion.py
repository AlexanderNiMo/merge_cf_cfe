import argparse
import pathlib
from commit_by_extension.commit import main
from commit_by_extension.config import get_config


def main():
    args = parse_args()
    args.func(args)


def parse_args():

    parser = argparse.ArgumentParser(prog='commit_extemsion.py')
    parser.add_argument('--config', aliases=['c'],  required=True, type=str, help='Путь к настройкам')

    parser.set_defaults(func=commit_extensions)

    return parser.parse_args()


def commit_extensions(args):
    config_file = pathlib.Path(args.config)
    if config_file.exists():
        raise FileNotFoundError(f'Не обнаружен файл настроек по пути {config_file}')

    main(get_config(config_file))


if __name__ == '__main__':
    main()
