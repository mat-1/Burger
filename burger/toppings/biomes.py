from jawa.classloader import ClassLoader
from jawa.constants import Float, Integer, String
from jawa.util.descriptor import method_descriptor

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
    def act(aggregate, classloader: ClassLoader):
        if 'biome.register' not in aggregate['classes']:
            return
        BiomeTopping._process(aggregate, classloader)

    @staticmethod
    def _process(aggregate, classloader: ClassLoader):
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
        BiomeTopping._process_113_classes_new(aggregate, classloader)

    @staticmethod
    def _process_113_classes_new(aggregate, classloader: ClassLoader):
        # After 18w16a, biomes used a builder again.  The name is now also translatable.

        for biome in aggregate['biomes']['biome'].values():
            biome['name'] = aggregate['language']['biome'][
                'minecraft.' + biome['text_id']
            ]

            cf = classloader[biome['class']]
            method = cf.methods.find_one(name='<init>')
            stack = []
            for ins in method.code.disassemble():
                if ins == 'invokespecial':
                    const = ins.operands[0]
                    name = const.name_and_type.name.value
                    if (
                        const.class_.name.value == cf.super_.name.value
                        and name == '<init>'
                    ):
                        # Calling biome init; we're done
                        break
                elif ins == 'invokevirtual':
                    const = ins.operands[0]
                    name = const.name_and_type.name.value
                    desc = method_descriptor(const.name_and_type.descriptor.value)

                    if len(desc.args) == 1:
                        if desc.args[0].name == 'float':
                            # Ugly portion - different methods with different names
                            # Hopefully the order doesn't change
                            if name == 'a':
                                biome['height'][0] = stack.pop()
                            elif name == 'b':
                                biome['height'][1] = stack.pop()
                            elif name == 'c':
                                biome['temperature'] = stack.pop()
                            elif name == 'd':
                                biome['rainfall'] = stack.pop()
                        elif desc.args[0].name == 'java/lang/String':
                            val = stack.pop()
                            if val is not None:
                                biome['mutated_from'] = val

                    stack = []
                # Constants
                elif ins in ('ldc', 'ldc_w'):
                    const = ins.operands[0]
                    if isinstance(const, String):
                        stack.append(const.string.value)
                    if isinstance(const, (Integer, Float)):
                        stack.append(const.value)

                elif ins.mnemonic.startswith('fconst'):
                    stack.append(float(ins.mnemonic[-1]))
                elif ins in ('bipush', 'sipush'):
                    stack.append(ins.operands[0].value)
                elif ins == 'aconst_null':
                    stack.append(None)
