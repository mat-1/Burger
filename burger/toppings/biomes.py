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

from jawa.constants import String

from .topping import Topping


class BiomeTopping(Topping):
    """Gets most biome types."""

    PROVIDES = ['identify.biome.superclass', 'biomes']

    DEPENDS = [
        'identify.biome.register',
        'identify.biome.list',
        'version.data',
        'language',
    ]

    @staticmethod
    def act(aggregate, classloader, verbose=False):
        if 'biome.register' not in aggregate['classes']:
            return
        BiomeTopping._process(aggregate, classloader, verbose)

    @staticmethod
    def _process(aggregate, classloader, verbose):
        # Processes biomes for Minecraft 1.14
        listclass = aggregate['classes']['biome.list']
        lcf = classloader[listclass]
        superclass = next(
            lcf.fields.find()
        ).type.name  # The first field in the list is a biome
        aggregate['classes']['biome.superclass'] = superclass

        biomes_base = aggregate.setdefault('biomes', {})
        biomes = biomes_base.setdefault('biome', {})
        biome_fields = biomes_base.setdefault('biome_fields', {})

        method = lcf.methods.find_one(name='<clinit>')

        # First pass: identify all the biomes.
        stack = []
        for ins in method.code.disassemble():
            if ins.mnemonic in ('bipush', 'sipush'):
                stack.append(ins.operands[0].value)
            elif ins.mnemonic in ('ldc', 'ldc_w'):
                const = ins.operands[0]
                if isinstance(const, String):
                    stack.append(const.string.value)
            elif ins.mnemonic == 'new':
                const = ins.operands[0]
                stack.append(const.name.value)
            elif ins.mnemonic == 'invokestatic':
                # Registration
                assert len(stack) == 3
                # NOTE: the default values there aren't present
                # in the actual code
                tmp_biome = {
                    'id': stack[0],
                    'text_id': stack[1],
                    'rainfall': 0.5,
                    'height': [0.1, 0.2],
                    'temperature': 0.5,
                    'class': stack[2],
                }
                biomes[stack[1]] = tmp_biome
                stack = [tmp_biome]  # Registration returns the biome
            elif ins.mnemonic == 'anewarray':
                # End of biome initialization; now creating the list of biomes
                # for the explore all biomes achievement but we don't need
                # that info.
                break
            elif ins.mnemonic == 'getstatic':
                const = ins.operands[0]
                if const.class_.name.value == listclass:
                    stack.append(biomes[biome_fields[const.name_and_type.name.value]])
                else:
                    stack.append(object())
            elif ins.mnemonic == 'putstatic':
                const = ins.operands[0]
                field = const.name_and_type.name.value
                stack[0]['field'] = field
                biome_fields[field] = stack[0]['text_id']
                stack.pop()

        # Second pass: check the biome constructors and fill in data from there.
        BiomeTopping._process_113_classes_new(aggregate, classloader, verbose)
