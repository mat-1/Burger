import logging

import six
from jawa.classloader import ClassLoader
from jawa.constants import ConstantClass, String
from jawa.util.descriptor import method_descriptor

from burger.mappings import MAPPINGS
from burger.util import WalkerCallback, class_from_invokedynamic, walk_method

from .topping import Topping


class EntityTopping(Topping):
    """Gets most entity types."""

    PROVIDES = ['entities.entity']

    DEPENDS = ['identify.entity.list', 'version.entity_format', 'language']

    @staticmethod
    def act(aggregate, classloader: ClassLoader):
        # Decide which type of entity logic should be used.

        EntityTopping._entities_1point13(aggregate, classloader)

        entities = aggregate['entities']

        entities['info'] = {'entity_count': len(entities['entity'])}

        EntityTopping.abstract_entities(classloader, entities['entity'])

    @staticmethod
    def _entities_1point13(aggregate, classloader: ClassLoader):
        logging.debug('Using 1.13 entity format')

        listclass = aggregate['classes']['entity.list']  # EntityType
        cf = classloader[listclass]

        entities = aggregate.setdefault('entities', {})
        entity = entities.setdefault('entity', {})

        # Find the inner builder class
        inner_classes = cf.attributes.find_one(name='InnerClasses').inner_classes
        builderclass = None
        funcclass = None  # 19w08a+ - a functional interface for creating new entities
        for entry in inner_classes:
            if entry.outer_class_info_index == 0:
                # Ignore anonymous classes
                continue

            outer = cf.constants.get(entry.outer_class_info_index)
            if outer.name == listclass:
                inner = cf.constants.get(entry.inner_class_info_index)
                inner_cf = classloader[inner.name.value]
                if inner_cf.access_flags.acc_interface:
                    if funcclass:
                        raise Exception('Unexpected multiple inner interfaces')
                    funcclass = inner.name.value
                else:
                    if builderclass:
                        raise Exception('Unexpected multiple inner classes')
                    builderclass = inner.name.value

        if not builderclass:
            raise Exception(
                'Failed to find inner class for builder in ' + str(inner_classes)
            )
        # Note that funcclass might not be found since it didn't always exist

        method = cf.methods.find_one(name='<clinit>')

        # Example of what's being parsed:
        # public static final EntityType<EntityAreaEffectCloud> AREA_EFFECT_CLOUD = register("area_effect_cloud", EntityType.Builder.create(EntityAreaEffectCloud::new, EntityCategory.MISC).setSize(6.0F, 0.5F)); // 19w05a+
        # public static final EntityType<EntityAreaEffectCloud> AREA_EFFECT_CLOUD = register("area_effect_cloud", EntityType.Builder.create(EntityAreaEffectCloud.class, EntityAreaEffectCloud::new).setSize(6.0F, 0.5F)); // 19w03a+
        # and in older versions:
        # public static final EntityType<EntityAreaEffectCloud> AREA_EFFECT_CLOUD = register("area_effect_cloud", EntityType.Builder.create(EntityAreaEffectCloud.class, EntityAreaEffectCloud::new)); // 18w06a-19w02a
        # and in even older versions:
        # public static final EntityType<EntityAreaEffectCloud> AREA_EFFECT_CLOUD = register("area_effect_cloud", EntityType.Builder.create(EntityAreaEffectCloud::new)); // through 18w05a

        entity_type_builder_cf = MAPPINGS.get_class_from_classloader(
            classloader,
            'net.minecraft.world.entity.EntityType$Builder',
        )
        set_size_method = MAPPINGS.get_method_from_classfile(
            entity_type_builder_cf, 'sized'
        )
        set_eye_height_method = MAPPINGS.get_method_from_classfile(
            entity_type_builder_cf, 'eyeHeight'
        )
        print('set_eye_height_method', set_eye_height_method)

        class EntityContext(WalkerCallback):
            def __init__(self):
                self.cur_id = 0

            def on_invokedynamic(self, ins, const, args):
                # MC uses EntityZombie::new, similar; return the created class
                return class_from_invokedynamic(ins, cf)

            def on_invoke(self, ins, const, obj, args):
                if const.class_.name == listclass:
                    if len(args) != 2:
                        # probably something like a boatFactory call, don't care
                        return
                    # register call
                    name = args[0]
                    new_entity = args[1]
                    new_entity['name'] = name
                    new_entity['id'] = self.cur_id
                    if 'minecraft.' + name in aggregate['language']['entity']:
                        new_entity['display_name'] = aggregate['language']['entity'][
                            'minecraft.' + name
                        ]
                    self.cur_id += 1

                    entity[name] = new_entity
                    return new_entity
                elif const.class_.name == builderclass:
                    if ins.mnemonic != 'invokestatic':
                        if (
                            const.name_and_type.name.value == set_size_method.name
                            and const.name_and_type.descriptor.value
                            == set_size_method.descriptor
                        ):
                            obj['width'] = args[0]
                            obj['height'] = args[1]
                        if (
                            const.name_and_type.name.value == set_eye_height_method.name
                            and const.name_and_type.descriptor.value
                            == set_eye_height_method.descriptor
                        ):
                            obj['eye_height'] = args[0]

                        # There are other properties on the builder (related to whether the entity can be created)
                        # We don't care about these
                        return obj

                    method_desc = const.name_and_type.descriptor.value
                    desc = method_descriptor(method_desc)

                    if len(args) == 2:
                        if (
                            desc.args[0].name == 'java/lang/Class'
                            and desc.args[1].name == 'java/util/function/Function'
                        ):
                            # Builder.create(Class, Function), 18w06a+
                            # In 18w06a, they added a parameter for the entity class; check consistency
                            assert args[0] == args[1] + '.class'
                            cls = args[1]
                        elif (
                            desc.args[0].name == 'java/util/function/Function'
                            or desc.args[0].name == funcclass
                        ):
                            # Builder.create(Function, EntityCategory), 19w05a+
                            cls = args[0]
                        else:
                            logging.debug(
                                f'Unknown entity type builder creation method {method_desc}'
                            )
                            cls = None
                    elif len(args) == 1:
                        # There is also a format that creates an entity that cannot be serialized.
                        # This might be just with a single argument (its class), in 18w06a+.
                        # Otherwise, in 18w05a and below, it's just the function to build.
                        if desc.args[0].name == 'java/lang/Function':
                            # Builder.create(Function), 18w05a-
                            # Just the function, which was converted into a class name earlier
                            cls = args[0]
                        elif desc.args[0].name == 'java/lang/Class':
                            # Builder.create(Class), 18w06a+
                            # The type that represents something that cannot be serialized
                            cls = None
                        else:
                            # Assume Builder.create(EntityCategory) in 19w05a+,
                            # though it could be hit for other unknown signatures
                            cls = None
                    else:
                        # Assume Builder.create(), though this could be hit for other unknown signatures
                        # In 18w05a and below, nonserializable entities
                        cls = None

                    return {'class': cls} if cls else {'serializable': 'false'}

            def on_put_field(self, ins, const, obj, value):
                if isinstance(value, dict):
                    # Keep track of the field in the entity list too.
                    value['field'] = const.name_and_type.name.value
                    # Also, if this isn't a serializable entity, get the class from the generic signature of the field
                    if 'class' not in value:
                        field = cf.fields.find_one(name=const.name_and_type.name.value)
                        sig = field.attributes.find_one(
                            name='Signature'
                        ).signature.value  # Something like `Laev<Laep;>;`
                        value['class'] = sig[
                            sig.index('<') + 2 : sig.index('>') - 1
                        ]  # Awful way of getting the actual type

            def on_new(self, ins, const):
                # Done once, for the registry, but we don't care
                return object()

            def on_get_field(self, ins, const, obj):
                # 19w05a+: used to set entity types.

                # 23w51a+: used to get tadpole hitbox height (since the register call references Tadpole.HITBOX_HEIGHT)
                class_name = const.class_.name.value
                cf = classloader[class_name]

                field_name = const.name_and_type.name.value
                init_method = cf.methods.find_one(name='<clinit>')
                stack = []
                for ins in init_method.code.disassemble():
                    if ins in ('ldc', 'ldc_w'):
                        const = ins.operands[0]
                        if isinstance(const, ConstantClass):
                            stack.append(const.name.value)
                        elif isinstance(const, String):
                            stack.append(const.string.value)
                        else:
                            stack.append(const.value)
                    elif ins == 'putstatic':
                        const = ins.operands[0]
                        if const.name_and_type.name.value == field_name:
                            if stack != []:
                                # it's possible for this to return an incorrect value, but it
                                # currently doesn't break anything and I think it's unlikely to in
                                # the future since statics are usually pretty simple
                                return stack.pop()

                # fallback
                return object()

        walk_method(cf, method, EntityContext())

    @staticmethod
    def _load_minecart_enum(classloader: ClassLoader, classname, minecart_info):
        """Stores data about the minecart enum in aggregate"""
        minecart_info['class'] = classname

        minecart_types = minecart_info.setdefault('types', {})
        minecart_types_by_field = minecart_info.setdefault('types_by_field', {})

        minecart_cf = classloader[classname]
        init_method = minecart_cf.methods.find_one(name='<clinit>')

        already_has_minecart_name = False
        for ins in init_method.code.disassemble():
            if ins == 'new':
                const = ins.operands[0]
                minecart_class = const.name.value
            elif ins == 'ldc':
                const = ins.operands[0]
                if isinstance(const, String):
                    if already_has_minecart_name:
                        minecart_type = const.string.value
                    else:
                        already_has_minecart_name = True
                        minecart_name = const.string.value
            elif ins == 'putstatic':
                const = ins.operands[0]
                if const.name_and_type.descriptor.value != 'L' + classname + ';':
                    # Other parts of the enum initializer (values array) that we don't care about
                    continue

                minecart_field = const.name_and_type.name.value

                minecart_types[minecart_name] = {
                    'class': minecart_class,
                    'field': minecart_field,
                    'name': minecart_name,
                    'entitytype': minecart_type,
                }
                minecart_types_by_field[minecart_field] = minecart_name

                already_has_minecart_name = False

    @staticmethod
    def abstract_entities(classloader: ClassLoader, entities):
        entity_classes = {e['class']: e['name'] for e in six.itervalues(entities)}

        # Add some abstract classes, to help with metadata, and for reference only;
        # these are not spawnable
        def abstract_entity(abstract_name, *subclass_names):
            for name in subclass_names:
                if name in entities:
                    cf = classloader[entities[name]['class']]
                    parent = cf.super_.name.value
                    if parent not in entity_classes:
                        entities['~abstract_' + abstract_name] = {
                            'class': parent,
                            'name': '~abstract_' + abstract_name,
                        }
                    else:
                        logging.debug(
                            f'Unexpected non-abstract class for parent of {name}: {entity_classes[parent]}'
                        )
                    break
            else:
                logging.debug(
                    f'Failed to find abstract entity {abstract_name} as a superclass of {subclass_names}'
                )

        abstract_entity('entity', 'item', 'Item')
        abstract_entity('minecart', 'minecart')  # AbstractMinecart
        abstract_entity('vehicle', '~abstract_minecart')  # VehicleEntity
        abstract_entity('living', 'armor_stand', 'ArmorStand')  # EntityLivingBase
        abstract_entity('insentient', 'ender_dragon', 'EnderDragon')  # EntityLiving
        abstract_entity('monster', 'enderman', 'Enderman')  # EntityMob
        abstract_entity('tameable', 'wolf', 'Wolf')  # EntityTameable
        abstract_entity('animal', 'sheep', 'Sheep')  # EntityAnimal
        abstract_entity('ageable', '~abstract_animal')  # EntityAgeable
        abstract_entity('creature', '~abstract_ageable')  # EntityCreature
        abstract_entity('display', 'block_display')  # Display.BlockDisplay
        abstract_entity('horse', 'horse')  # AbstractHorse
        abstract_entity('villager', 'villager')  # AbstractVillager
        abstract_entity('arrow', 'arrow')  # AbstractVillager
        abstract_entity('fish', 'cod')  # AbstractVillager
        abstract_entity('boat', 'birch_boat')
        abstract_entity('thrown_item_projectile', 'egg')  # ThrowableItemProjectile
        abstract_entity('raider', 'ravager')  # Raider
        abstract_entity('spellcaster_illager', 'illusioner')  # SpellcasterIllager
        abstract_entity('chested_horse', 'mule')  # AbstractChestedHorse
        abstract_entity('piglin', 'piglin')  # AbstractChestedHorse
