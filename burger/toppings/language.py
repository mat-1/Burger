#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
Copyright (c) 2011 Tyler Kenendy <tk@tkte.ch>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

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
