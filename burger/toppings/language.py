import json
import logging

import six
from jawa.classloader import ClassLoader

from .topping import Topping


class LanguageTopping(Topping):
    """Provides the contents of the English language files."""

    PROVIDES = ['language']

    DEPENDS = []

    @staticmethod
    def act(aggregate, classloader):
        aggregate['language'] = {}
        LanguageTopping.load_language(aggregate, classloader, 'lang/stats_US.lang')
        LanguageTopping.load_language(aggregate, classloader, 'lang/en_US.lang')
        LanguageTopping.load_language(
            aggregate, classloader, 'assets/minecraft/lang/en_US.lang'
        )
        LanguageTopping.load_language(
            aggregate, classloader, 'assets/minecraft/lang/en_us.lang'
        )
        LanguageTopping.load_language(
            aggregate, classloader, 'assets/minecraft/lang/en_us.json', True
        )

    @staticmethod
    def load_language(aggregate, classloader: ClassLoader, path, is_json: bool = False):
        try:
            with classloader.open(path) as fin:
                contents = fin.read().decode('utf-8')
        except Exception:
            logging.debug(f"Can't find file {path} in jar")
            return

        for category, name, value in LanguageTopping.parse_lang(contents, is_json):
            cat = aggregate['language'].setdefault(category, {})
            cat[name] = value

    @staticmethod
    def parse_lang(contents, is_json: bool):
        if is_json:
            contents = json.loads(contents)
            for tag, value in six.iteritems(contents):
                category, name = tag.split('.', 1)

                yield (category, name, value)
        else:
            contents = contents.split('\n')
            lineno = 0
            for line in contents:
                lineno = lineno + 1
                line = line.strip()

                if not line:
                    continue
                if line[0] == '#':
                    continue

                if '=' not in line or '.' not in line:
                    logging.debug(f'Language file line {lineno} is malformed: {line}')
                    continue

                tag, value = line.split('=', 1)
                category, name = tag.split('.', 1)

                yield (category, name, value)
