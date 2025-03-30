import logging

from jawa.classloader import ClassLoader
from jawa.util.descriptor import method_descriptor

from burger.util import WalkerCallback, walk_method

from .topping import Topping


class ItemsTopping(Topping):
    """Provides some information on most available items."""

    PROVIDES = ['identify.item.superclass', 'items']

    DEPENDS = [
        'identify.block.superclass',
        'identify.block.list',
        'identify.item.register',
        'identify.item.list',
        'language',
        'blocks',
        'version.protocol',
        'version.is_flattened',
    ]

    @staticmethod
    def act(aggregate, classloader: ClassLoader):
        ItemsTopping._process(aggregate, classloader)

    @staticmethod
    def _process(aggregate, classloader: ClassLoader):
        # All of the registration happens in the list class
        listclass = aggregate['classes']['item.list']
        lcf = classloader[listclass]
        superclass = next(
            lcf.fields.find()
        ).type.name  # The first field in the list class is an item
        cf = classloader[superclass]
        aggregate['classes']['item.superclass'] = superclass
        blockclass = aggregate['classes']['block.superclass']
        blocklist = aggregate['classes']['block.list']

        cf = classloader[superclass]

        if 'item' in aggregate['language']:
            language = aggregate['language']['item']
        else:
            language = None

        # 23w40a+ (1.20.3) has a references class that defines the IDs for some items
        references_class = aggregate['classes'].get('item.references')
        references_class_fields_to_item_ids = {}
        if references_class:
            # process the references class
            references_cf = classloader[references_class]
            for method in references_cf.methods.find(name='<clinit>'):
                item_id = None
                for ins in method.code.disassemble():
                    if ins.mnemonic == 'ldc':
                        item_id = ins.operands[0].string.value
                    if ins.mnemonic == 'putstatic':
                        field = ins.operands[0].name_and_type.name.value
                        references_class_fields_to_item_ids[field] = item_id

        # Figure out what the builder class is
        ctor = cf.methods.find_one(name='<init>')
        builder_class = ctor.args[0].name
        builder_cf = classloader[builder_class]

        # Find the max stack size method
        # public Item.Properties stacksTo(int var1) {
        #     return this.component(DataComponents.MAX_STACK_SIZE, var1);
        # }
        max_stack_method = None
        for method in builder_cf.methods.find(args='I'):
            expected_instructions = (
                'aload',
                'getstatic',
                'iload',
                'invokestatic',
                'invokevirtual',
                'areturn',
            )
            insts = method.code.disassemble()
            given_instructions = tuple(ins.mnemonic for ins in insts)
            if given_instructions == expected_instructions:
                max_stack_method = method
                break
        if not max_stack_method:
            raise Exception("Couldn't find max stack size setter in " + builder_class)

        register_item_block_method = lcf.methods.find_one(
            args='L' + blockclass + ';', returns='L' + superclass + ';'
        )
        item_block_class = None
        # Find the class used that represents an item that is a block
        for ins in register_item_block_method.code.disassemble():
            if ins.mnemonic == 'new':
                const = ins.operands[0]
                item_block_class = const.name.value
                break

        items = aggregate.setdefault('items', {})
        item_list = items.setdefault('item', {})
        item_fields = items.setdefault('item_fields', {})

        is_item_class_cache = {superclass: True}

        def is_item_class(name):
            if name in is_item_class_cache:
                return is_item_class_cache
            elif name == 'java/lang/Object':
                return True
            elif '/' in name:
                return False
            elif name == 'int':
                return False

            cf = classloader[name]
            result = is_item_class(cf.super_.name.value)
            is_item_class_cache[name] = result
            return result

        # Find the static block registration method
        method = lcf.methods.find_one(name='<clinit>')

        class Walker(WalkerCallback):
            def __init__(self):
                self.cur_id = 0

            def on_new(self, ins, const):
                class_name = const.name.value
                return {'class': class_name}

            def on_invoke(self, ins, const, obj, args):
                method_name = const.name_and_type.name.value
                method_desc = const.name_and_type.descriptor.value
                desc = method_descriptor(method_desc)

                if ins.mnemonic == 'invokestatic':
                    if const.class_.name.value == listclass:
                        current_item = {}

                        text_id = None
                        for idx, arg in enumerate(desc.args):
                            if arg.name == blockclass:
                                if isinstance(args[idx], list):
                                    continue
                                block = args[idx]
                                text_id = block['text_id']
                                if 'name' in block:
                                    current_item['name'] = block['name']
                                if 'display_name' in block:
                                    current_item['display_name'] = block['display_name']
                            elif arg.name == superclass:
                                current_item.update(args[idx])
                            elif arg.name == item_block_class:
                                current_item.update(args[idx])
                                text_id = current_item['text_id']
                            elif arg.name == 'java/lang/String':
                                text_id = args[idx]
                            elif arg.name == aggregate['classes'].get('resourcekey'):
                                text_id = args[idx]

                        if current_item == {} and not text_id:
                            logging.debug(
                                f"Couldn't find any identifying information for the call to {method_desc} with {args}"
                            )
                            return

                        if not text_id:
                            logging.debug(
                                f'Could not find text_id for call to {method_desc} with {args}'
                            )
                            return

                        # Call to the static register method.
                        current_item['text_id'] = text_id
                        current_item['numeric_id'] = self.cur_id
                        self.cur_id += 1
                        lang_key = 'minecraft.%s' % text_id
                        if language is not None and lang_key in language:
                            current_item['display_name'] = language[lang_key]
                        if 'max_stack_size' not in current_item:
                            current_item['max_stack_size'] = 64
                        item_list[text_id] = current_item

                        return current_item
                else:
                    if method_name == '<init>':
                        # Call to a constructor.  Check if the builder is in the args,
                        # and if so update the item with it
                        idx = 0
                        for arg in desc.args:
                            if arg.name == builder_class:
                                # Update from the builder
                                if 'max_stack_size' in args[idx]:
                                    obj['max_stack_size'] = args[idx]['max_stack_size']
                            elif arg.name == blockclass and 'text_id' not in obj:
                                block = args[idx]
                                obj['text_id'] = block['text_id']
                                if 'name' in block:
                                    obj['name'] = block['name']
                                if 'display_name' in block:
                                    obj['display_name'] = block['display_name']
                            idx += 1
                    elif (
                        method_name == max_stack_method.name.value
                        and method_desc == max_stack_method.descriptor.value
                    ):
                        obj['max_stack_size'] = args[0]

                if desc.returns.name != 'void':
                    if desc.returns.name == builder_class or is_item_class(
                        desc.returns.name
                    ):
                        if ins.mnemonic == 'invokestatic':
                            if (
                                len(desc.args) > 0
                                and desc.args[0].name == builder_class
                            ):
                                # Probably returning itself, but through a synthetic method
                                # This case doesn't seem to actually happen in practice
                                # (it did exist in 1.13/18w33a, though)
                                return args[0]
                            else:
                                # 23w04a added trimmed armor, which sets up the builder in a static
                                # method in its own class. So, we need to recurse into that...
                                new_cf = classloader[const.class_.name.value]
                                new_method = new_cf.methods.find_one(
                                    name=method_name,
                                    args=desc.args_descriptor,
                                    returns=desc.returns_descriptor,
                                )
                                return walk_method(new_cf, new_method, self)
                        else:
                            # Probably returning itself
                            return obj
                    else:
                        return object()

            def on_get_field(self, ins, const, obj):
                if const.class_.name.value == blocklist:
                    # Getting a block; put it on the stack.
                    block_name = aggregate['blocks']['block_fields'][
                        const.name_and_type.name.value
                    ]
                    if block_name not in aggregate['blocks']['block']:
                        logging.debug(
                            f'No information available for item-block for {const.name_and_type.name.value}/{block_name}'
                        )
                        return {}
                    else:
                        return aggregate['blocks']['block'][block_name]
                elif const.class_.name.value == references_class:
                    # get the block key from the references.Item class
                    if (
                        const.name_and_type.name.value
                        in references_class_fields_to_item_ids
                    ):
                        return references_class_fields_to_item_ids[
                            const.name_and_type.name.value
                        ]
                    else:
                        logging.debug(
                            f'Unknown field {const.name_and_type.name.value} in references class {references_class}'
                        )
                        return None

                elif const.class_.name.value == listclass:
                    return item_list[item_fields[const.name_and_type.name.value]]
                else:
                    return const

            def on_put_field(self, ins, const, obj, value):
                if isinstance(value, dict):
                    field = const.name_and_type.name.value
                    value['field'] = field
                    item_fields[const.name_and_type.name.value] = value['text_id']

            def on_invokedynamic(self, ins, const, args):
                # we can just ignore these
                pass

        walk_method(cf, method, Walker())
