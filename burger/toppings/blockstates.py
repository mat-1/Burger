#!/usr/bin/env python
# -*- coding: utf8 -*-

from .topping import Topping

from jawa.constants import *
from jawa.util.descriptor import method_descriptor, field_descriptor

import traceback
import six
import six.moves

# EnumFacing.Plane.  Needed because this is also a predicate, which is used
# to get certain facings
class Plane:
    def __init__(self, directions):
        self.directions = directions
HORIZONTAL = Plane(["NORTH", "EAST", "SOUTH", "WEST"])
VERTICAL = Plane(["UP", "DOWN"])
PLANES = { "HORIZONTAL": HORIZONTAL, "VERTICAL": VERTICAL }

# Classes that represent predicates in various versions
PREDICATE_CLASSES = ("com/google/common/base/Predicate", "java/util/function/Predicate")

class BlockStateTopping(Topping):
    """Gets tile entity (block entity) types."""

    PROVIDES = [
        "blocks.states"
    ]

    DEPENDS = [
        "blocks",
        "version.data",
        "version.is_flattened",
        "identify.blockstatecontainer",
        "identify.sounds.list",
        "identify.enumfacing.plane"
    ]

    @staticmethod
    def act(aggregate, classloader, verbose=False):
        if "blockstatecontainer" not in aggregate["classes"]:
            if verbose:
                print("blockstatecontainer not found; skipping blockstates")
            return

        is_flattened = aggregate["version"]["is_flattened"]

        blockstatecontainer = aggregate["classes"]["blockstatecontainer"]
        block_cf = classloader[aggregate["classes"]["block.superclass"]]
        plane = aggregate["classes"]["enumfacing.plane"]

        # Part 1: build up a list of property fields, by class.  Also build a set of property types.
        # 18w19a and above use a builder to register states; before that they just directly returned a container.
        # Note that blockstatecontainer is the builder class in 18w19a.
        is_18w19a = aggregate["version"]["data"] >= 1484
        is_protected = lambda m: m.access_flags.acc_protected
        if is_18w19a:
            base_method = block_cf.methods.find_one(returns="V", args="L" + blockstatecontainer + ";", f=is_protected)
        else:
            base_method = block_cf.methods.find_one(returns="L" + blockstatecontainer + ";", args="",  f=is_protected)

        def matches(other_method):
            return (other_method.name.value == base_method.name.value and
                    other_method.descriptor.value == base_method.descriptor.value)

        _property_types = set()
        # Properties that are used by each block class
        properties_by_class = {}
        def process_class(name):
            """
            Gets the properties for the given block class, checking the parent
            class if none are defined.  Returns the properties, and also adds
            them to properties_by_class
            """
            if name in properties_by_class:
                # Caching - avoid reading the same class multiple times
                return properties_by_class[name]

            cf = classloader[name]
            method = cf.methods.find_one(f=matches)

            if not method:
                properties = process_class(cf.super_.name.value)
                properties_by_class[name] = properties
                return properties

            properties = None
            if_pos = None
            stack = []
            for ins in method.code.disassemble():
                # This could _almost_ just be checking for getstatic, but
                # brewing stands use an array of properties as the field,
                # so we need some stupid extra logic.
                if ins == "new":
                    assert not is_18w19a # In 18w19a this should be a parameter
                    const = ins.operands[0]
                    type_name = const.name.value
                    assert type_name == blockstatecontainer
                    stack.append(object())
                elif ins == "aload" and ins.operands[0].value == 1:
                    assert is_18w19a # The parameter is only used in 18w19a and above
                    stack.append(object())
                elif ins in ("sipush", "bipush"):
                    stack.append(ins.operands[0].value)
                elif ins in ("anewarray", "newarray"):
                    length = stack.pop()
                    val = [None] * length
                    stack.append(val)
                elif ins == "getstatic":
                    const = ins.operands[0]
                    desc = field_descriptor(const.name_and_type.descriptor.value)
                    if desc.name == "java/util/List":
                        # Special-casing for chiseled bookshelves in 22w46a,
                        # which use a list for slot_0_occupied through slot_5_occupied.
                        # This code is very brittle and hacky.
                        init = cf.methods.find_one(name="<clinit>")
                        stack2 = []
                        for ins2 in init.code.disassemble():
                            # return appears too, but we break before it
                            assert ins2 in ("getstatic", "invokestatic", "putstatic")
                            if ins2 == "getstatic":
                                const2 = ins2.operands[0]
                                prop = {
                                    "field_name": const2.name_and_type.name.value,
                                    "field_class": const2.class_.name.value
                                }
                                desc2 = field_descriptor(const2.name_and_type.descriptor.value)
                                _property_types.add(desc2.name)
                                stack2.append(prop)
                            elif ins2 == "invokestatic":
                                assert ins2.operands[0].class_.name == "java/util/List"
                                assert ins2.operands[0].name_and_type.name == "of"
                                assert ins2.operands[0].name_and_type.descriptor == "(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)Ljava/util/List;"
                                # Put the last 6 items onto the stack as an array
                                # (this should be equivalent to stack2 = [stack2] in practice)
                                stack2 = stack2[:-6] + [stack2[-6:]]
                            elif ins2 == "putstatic":
                                # We should be storing to the same field as the one we're searching for
                                assert ins2.operands[0] == const
                                # So, we can treat this as handling the original getfield.
                                stack.append(stack2.pop())
                                break
                        else:
                            raise Exception("Failed to hackily find list for getfield ins " + str(ins))
                    else:
                        # The normal path for everything else
                        prop = {
                            "field_name": const.name_and_type.name.value,
                            "field_class": const.class_.name.value
                        }
                        _property_types.add(desc.name)
                        stack.append(prop)
                elif ins == "aaload":
                    index = stack.pop()
                    array = stack.pop()
                    prop = array.copy()
                    prop["array_index"] = index
                    stack.append(prop)
                elif ins == "aastore":
                    value = stack.pop()
                    index = stack.pop()
                    array = stack.pop()
                    array[index] = value
                elif ins == "dup":
                    stack.append(stack[-1])
                elif ins == "invokespecial":
                    const = ins.operands[0]
                    assert const.name_and_type.name == "<init>"
                    desc = method_descriptor(const.name_and_type.descriptor.value)
                    assert len(desc.args) == 2

                    # Normally this constructor call would return nothing, but
                    # in this case we'd rather remove the object it's called on
                    # and keep the properties array (its parameter)
                    arg = stack.pop()
                    stack.pop() # Block
                    stack.pop() # Invocation target
                    stack.append(arg)
                elif ins == "invokevirtual":
                    # Two possibilities (both only present pre-flattening):
                    # 1. It's isDouble() for a slab.  Two different sets of
                    #    properties in that case.
                    # 2. It's getTypeProperty() for flowers.  Only one
                    #    set of properties, but other hacking is needed.
                    # We can differentiate these cases based off of the return
                    # type.
                    # There is a third option post 18w19a:
                    # 3. It's calling the state container's register method.
                    # We can check this just by the type.
                    const = ins.operands[0]
                    desc = method_descriptor(const.name_and_type.descriptor.value)

                    if const.class_.name == blockstatecontainer:
                        # Case 3.
                        # Note that the register method actually adds multiple
                        # states. The only block that calls it multiple times
                        # is Chain in 1.16.2-pre1+ though, with everything else
                        # using only 1 varargs call.  (There also are no calls
                        # to the superclass' register states method.)
                        if properties is None:
                            properties = stack.pop()
                        else:
                            properties.extend(stack.pop())
                        assert desc.returns.name == blockstatecontainer
                        # Don't pop anything, since we'd just pop and re-add the builder
                    elif desc.returns.name == "boolean":
                        # Case 2.
                        properties = [None, None]
                        stack.pop() # Target object
                        # XXX shouldn't something be returned here?
                    else:
                        # Case 1.
                        # Assume that the return type is the base interface
                        # for properties
                        stack.pop() # Target object
                        stack.append(None)
                elif ins == "ifeq":
                    assert if_pos is None
                    if_pos = ins.pos + ins.operands[0].value
                elif ins == "pop":
                    stack.pop()
                elif ins == "areturn":
                    assert not is_18w19a # In 18w19a we don't return a container
                    if if_pos == None:
                        assert properties == None
                        properties = stack.pop()
                    else:
                        assert isinstance(properties, list)
                        index = 0 if ins.pos < if_pos else 1
                        assert properties[index] == None
                        properties[index] = stack.pop()
                elif ins == "return":
                    assert is_18w19a # We only return void in 18w19a
                elif ins == "aload":
                    assert ins.operands[0].value == 0 # Should be aload_0 (this)
                    stack.append(object())
                elif ins == "invokestatic":
                    # Added in 22w46a: the chiseled bookshelf uses a list to store
                    # slot_0_occupied through slot_5_occupied, and also checks that the
                    # object block states are being registered to is non-null for some reason
                    # (_after_ already using it? This seems to be automatic for lambdas, I guess?)
                    assert ins.operands[0].class_.name == "java/util/Objects"
                    assert ins.operands[0].name_and_type.name == "requireNonNull"
                    assert ins.operands[0].name_and_type.descriptor == "(Ljava/lang/Object;)Ljava/lang/Object;"
                    # requireNonNull just returns its parameter, so we don't need to do anything
                elif ins == "invokedynamic":
                    # As implied above, this is used in 22w46a for chiseled bookshelves,
                    # as something like this:
                    """
                    void registerStates(BlockStateContainer instance) {
                        instance.register(BlockStates.LAST_INTERACTION_BOOK_SLOT)
                                .register(BlockAbstractBookshelf.FACING);
                        // compiler-generated for instance::register some reason, and like this and
                        // not making use of requireNonNull's return value.
                        Objects.requireNonNull(instance);
                        BlockChiseledBookshelf.SLOT_OCCUPIED.forEach(instance::register);
                    }
                    """
                    # We can just ignore this and assume any invokedynamic is for this purpose.
                    desc = method_descriptor(ins.operands[0].name_and_type.descriptor.value)
                    assert ins.operands[0].name_and_type.name == 'accept'
                    assert desc.returns.name == 'java/util/function/Consumer'
                elif ins == "invokeinterface":
                    # This is the forEach in 22w46a for chiseled bookshelves.
                    assert ins.operands[0].class_.name == "java/util/List"
                    assert ins.operands[0].name_and_type.name == "forEach"
                    assert ins.operands[0].name_and_type.descriptor == "(Ljava/util/function/Consumer;)V"
                    stack.pop()  # removing the consumer argument
                    properties.extend(stack.pop())  # And this is the field.
                elif verbose:
                    print("%s createBlockState contains unimplemented ins %s" % (name, ins))

            if properties is None:
                # If we never set properties, warn; however, this is normal for
                # the base implementation in Block in 18w19a
                if verbose and name != aggregate["classes"]["block.superclass"]:
                    print("Didn't find anything that set properties for %s" % name)
                properties = []
            properties_by_class[name] = properties
            return properties

        for block in six.itervalues(aggregate["blocks"]["block"]):
            cls = block["class"]
            try:
                process_class(cls)
            except:
                if verbose:
                    print("Failed to process properties for %s (for %s)" % (cls, block["text_id"]))
                    traceback.print_exc()
                properties_by_class[cls] = []

        assert len(_property_types) == 4
        property_types = {}
        for type in _property_types:
            cf = classloader[type]
            if cf.super_.name.value in _property_types:
                property_types[type] = "direction"
            else:
                attribute = cf.attributes.find_one(name='Signature')
                signature = attribute.signature.value
                # Somewhat ugly behavior until an actual parser is added for these
                if "Enum" in signature:
                    property_types[type] = "enum"
                elif "Integer" in signature:
                    property_types[type] = "int"
                elif "Boolean" in signature:
                    property_types[type] = "bool"
                elif verbose:
                    print("Unknown property type %s with signature %s" % (type, signature))

        # Part 2: figure out what each field is.
        is_enum_cache = {}
        def is_enum(cls):
            """
            Checks if the given class is an enum.
            This needs to be recursive due to inner classes for enums.
            """
            if cls in is_enum_cache:
                return is_enum_cache[cls]
            if cls not in classloader:
                is_enum_cache[cls] = False
                return False

            cf = classloader[cls]
            super = cf.super_.name.value
            if super == "java/lang/Enum":
                is_enum_cache[cls] = True
            elif super == "java/lang/Object":
                is_enum_cache[cls] = False
            else:
                is_enum_cache[cls] = is_enum(super)

            return is_enum_cache[cls]

        fields_by_class = {}

        def find_field(cls, field_name):
            """
            This function exists to deal with a javac quirk: static fields in superclasses
            are treated as if they were static fields in the current class. This also
            applies to invokestatic, but it's particularly weird for fields. For example:

            ```java
            interface Iface {
                public static final Object FOO = "foo";  // Note: Object to prevent inlining
            }
            class Parent implements Iface {
                public static final Object BAR = "bar";
            }
            class Child extends Parent implements Iface {
                public static void test() {
                    System.out.println(FOO);  // getstatic uses Child.FOO
                    System.out.println(Iface.FOO);  // uses Iface.FOO
                    System.out.println(Parent.FOO);  // uses Parent.FOO
                    System.out.println(Child.FOO);  // uses Child.FOO
                    System.out.println(BAR);  // uses Child.BAR
                    System.out.println(Parent.BAR);  // uses Parent.BAR
                    System.out.println(Child.BAR);  // uses Child.BAR
                }
            }
            ```

            As a practical example:

            ```java
            public class Block { /* ... */ }
            public abstract class BlockHorizontal extends Block {
                public static final Property FACING = Properties.FACING;
                // ... also supports mirroring and rotating ...
            }
            public class BlockCocoaBeans {
                public static final Property AGE = Properties.AGE_0_TO_2;
                @Override
                void registerProperties(BlockStateContainer container) {
                    container.register(FACING, AGE);
                    // looks the same bytecode-wise as:
                    // container.register(BlockCocoaBeans.FACING, BlockCocoaBeans.AGE);
                }
            }
            ```

            99% of blocks register without using a specific class name, and thus use getstatic
            on the current class. The exceptions are infested deepslate, which uses the same
            AXIS field used by regular deepslate (and other pillar-like blocks) but does not
            directly inherit the same class, and the chiseled bookshelf in 22w46a+ which uses
            a list that contains direct references to the class containing all block state
            properties without re-declaring them in its own class.

            cls: name of the class
            field_name: name of the field to find.  If None, returns all fields
            """
            if cls in fields_by_class:
                if field_name is not None:
                    if field_name not in fields_by_class[cls] and verbose:
                        print("Requested field %s.%s but that wasn't found last time" % (cls, field_name))
                    return fields_by_class[cls][field_name]
                else:
                    return fields_by_class[cls]
            elif cls == aggregate["classes"].get("sounds.list"):
                # If we already know what the sounds list class is, just ignore it
                # as going through it would take a while for no reason
                return object()

            cf = classloader[cls]

            fields_by_class[cls] = {}
            super_name = cf.super_.name.value
            if not super_name.startswith("java/"):
                # Add fields from superclass
                fields_by_class[cls].update(find_field(super_name, None))
            for iface in cf.interfaces:
                # Relevant for cave vines (glowberries), which have separate blocks for cave_vines
                # and cave_vines_plant, but the berries property is declared in a shared interface.
                iface_name = iface.name.value
                if not iface_name.startswith("java/") and not iface_name.startswith('com/google/'):
                    fields_by_class[cls].update(find_field(iface_name, None))

            init = cf.methods.find_one(name="<clinit>")
            if not init:
                if field_name is not None:
                    return fields_by_class[cls][field_name]
                else:
                    return fields_by_class[cls]

            stack = []
            locals = {}

            for ins in init.code.disassemble():
                if ins == "putstatic":
                    const = ins.operands[0]
                    name = const.name_and_type.name.value
                    value = stack.pop()

                    if isinstance(value, dict):
                        if "declared_in" not in value:
                            # If there's already a declared_in, this is a field
                            # loaded with getstatic, and we don't want to change
                            # the true location of it
                            value["declared_in"] = cls
                        if value["class"] == plane:
                            # Convert to an instance of Plane
                            # Now is the easiest time to do this, and for
                            # Plane itself it doesn't matter since it's never
                            # used on the stack
                            assert "enum_name" in value
                            assert value["enum_name"] in PLANES
                            value = PLANES[value["enum_name"]]
                    fields_by_class[cls][name] = value
                elif ins == "getstatic":
                    const = ins.operands[0]
                    target = const.class_.name.value
                    type = field_descriptor(const.name_and_type.descriptor.value).name
                    name = const.name_and_type.name.value
                    if not target.startswith("java/"):
                        stack.append(find_field(target, name))
                    else:
                        stack.append(object())
                elif ins in ("ldc", "ldc_w", "ldc2_w"):
                    const = ins.operands[0]

                    if isinstance(const, ConstantClass):
                        stack.append("%s.class" % const.name.value)
                    elif isinstance(const, String):
                        stack.append(const.string.value)
                    else:
                        stack.append(const.value)
                elif ins.mnemonic.startswith("dconst"):
                    stack.append(float(ins.mnemonic[-1]))
                elif ins in ("bipush", "sipush"):
                    stack.append(ins.operands[0].value)
                elif ins == "aconst_null":
                    stack.append(None)
                elif ins in ("anewarray", "newarray"):
                    length = stack.pop()
                    stack.append([None] * length)
                elif ins in ("aaload", "iaload"):
                    index = stack.pop()
                    array = stack.pop()
                    prop = array[index].copy()
                    prop["array_index"] = index
                    stack.append(prop)
                elif ins in ("aastore", "iastore"):
                    value = stack.pop()
                    index = stack.pop()
                    array = stack.pop()
                    array[index] = value
                elif ins == "arraylength":
                    array = stack.pop()
                    stack.append(len(array))
                elif ins == "dup":
                    stack.append(stack[-1])
                elif ins == "invokedynamic":
                    # Try to get the class that's being created
                    const = ins.operands[0]
                    desc = method_descriptor(const.name_and_type.descriptor.value)
                    stack.append({"dynamic_class": desc.returns.name, "class": cls})
                elif ins.mnemonic.startswith("invoke"):
                    const = ins.operands[0]
                    desc = method_descriptor(const.name_and_type.descriptor.value)
                    num_args = len(desc.args)
                    args = [stack.pop() for _ in six.moves.range(num_args)]
                    args.reverse()

                    if ins == "invokestatic":
                        obj = None
                    else:
                        obj = stack.pop()

                    if desc.returns.name in property_types:
                        prop = {
                            "class": desc.returns.name,
                            "type": property_types[desc.returns.name],
                            "args": args
                        }
                        stack.append(prop)
                    elif const.name_and_type.name == "<init>":
                        if obj["is_enum"]:
                            obj["enum_name"] = args[0]
                            obj["enum_ordinal"] = args[1]
                        else:
                            obj["args"] = args
                    elif const.name_and_type.name == "values":
                        # Enum values
                        fields = find_field(const.class_.name.value, None)
                        stack.append([fld for fld in fields
                                      if isinstance(fld, dict) and fld["is_enum"]])
                    elif desc.returns.name != "void":
                        if isinstance(obj, Plane):
                            # One special case, where EnumFacing.Plane is used
                            # to get a list of directions
                            stack.append(obj.directions)
                        elif (isinstance(obj, dict) and obj["is_enum"] and
                                desc.returns.name == "int"):
                            # Assume it's the enum ordinal, even if it really
                            # isn't
                            stack.append(obj["enum_ordinal"])
                        else:
                            o = object()
                            stack.append(o)
                elif ins in ("istore", "lstore", "fstore", "dstore", "astore"):
                    # Store other than array store
                    locals[ins.operands[0].value] = stack.pop()
                elif ins in ("iload", "lload", "fload", "dload", "aload"):
                    # Load other than array load
                    stack.append(locals[ins.operands[0].value])
                elif ins == "new":
                    const = ins.operands[0]
                    type_name = const.name.value
                    obj = {
                        "class": type_name,
                        "is_enum": is_enum(type_name)
                    }
                    stack.append(obj)
                elif ins == "checkcast":
                    # We don't have type information, so no checking or casting
                    pass
                elif ins == "return":
                    break
                elif ins == "if_icmpge":
                    # Code in stairs that loops over state combinations for hitboxes
                    break
                elif verbose:
                    print("%s initializer contains unimplemented ins %s" % (cls, ins))

            if field_name is not None:
                return fields_by_class[cls][field_name]
            else:
                return fields_by_class[cls]

        # Part 3: convert those fields into actual well-formed properties.
        # Property handlers.
        def base_handle_property(prop):
            field = prop["field"]
            args = field["args"]
            assert len(args) >= 1
            assert isinstance(args[0], six.string_types)
            ret = {
                "type": field["type"],
                "name": args[0],
                "field_name": prop["field_name"]
            }
            if "array_index" in prop:
                ret["array_index"] = prop["array_index"]
            else:
                # Unfortunately we don't have a declared_in field for arrays at this time
                ret["declared_in"] = field["declared_in"]
            return ret

        def handle_boolean_property(prop):
            ret = base_handle_property(prop)

            assert len(prop["field"]["args"]) == 1
            ret["num_values"] = 2
            return ret

        def handle_int_property(prop):
            ret = base_handle_property(prop)

            args = prop["field"]["args"]
            assert len(args) == 3
            assert isinstance(args[1], int)

            ret["min"] = args[1]
            if isinstance(args[2], int):
                ret["max"] = args[2]
            else:
                # For whatever reason, the number of rotation angles for signs and banners is not a
                # compile-time constant, but instead the result of a static function (which returns
                # a compile-time constant). Let's just hardcode that constant instead.
                assert ret["name"] == "rotation"
                ret["max"] = 15
            ret["num_values"] = ret["max"] - ret["min"] + 1
            return ret

        def handle_enum_property(prop):
            ret = base_handle_property(prop)

            args = prop["field"]["args"]
            assert len(args) in (2, 3)
            assert isinstance(args[1], six.string_types)
            assert args[1].endswith(".class") # Should be a class
            class_name = args[1][:-len(".class")]

            ret["enum_class"] = class_name
            if len(args) == 2:
                values = [c["enum_name"] for c
                          in six.itervalues(find_field(class_name, None))
                          if isinstance(c, dict) and c["is_enum"]]
            elif isinstance(args[2], list):
                values = [c["enum_name"] for c in args[2]]
            elif isinstance(args[2], dict):
                # Possibly a predicate (used for powered and activator rails)
                if "dynamic_class" in args[2]:
                    predicate_type = args[2]["dynamic_class"]
                    predicate_class = args[2]["dynamic_class"]
                else:
                    cf = classloader[args[2]["class"]]
                    if len(cf.interfaces) == 1:
                        predicate_type = cf.interfaces[0].name.value
                        predicate_class = args[2]["class"]
                    else:
                        if verbose:
                            print("Could not find predicate class for args %s and interfaces %s" % (args, cf.interfaces))
                        predicate_type = None
                        predicate_class = None

                if predicate_type in PREDICATE_CLASSES:
                    ret["predicate"] = predicate_class
                    # Will be trimmed later
                    values = [c["enum_name"] for c
                          in six.itervalues(find_field(class_name, None))
                          if isinstance(c, dict) and c["is_enum"]]
                elif verbose:
                    print("Unhandled args for %s" % prop)
                    values = []
            else:
                # Regular Collection (unused)
                if verbose:
                    print("Unhandled args for %s" % prop)
                values = []
            ret["values"] = values
            ret["num_values"] = len(values)
            return ret

        def handle_direction_property(prop):
            ret = base_handle_property(prop)

            args = prop["field"]["args"]
            assert len(args) in (1, 2)
            if len(args) == 1:
                # No restrictions
                values = ["DOWN", "UP", "NORTH", "SOUTH", "EAST", "WEST"]
            elif isinstance(args[1], list):
                if isinstance(args[1][0], str):
                    # A Plane's facings
                    values = args[1]
                else:
                    # Fields
                    values = [c["enum_name"] for c in args[1]]
            elif isinstance(args[1], Plane):
                # Plane used as a predicate
                values = args[1].directions
            elif isinstance(args[1], dict):
                # Possibly a predicate (used for hoppers)
                if "dynamic_class" in args[1]:
                    predicate_type = args[1]["dynamic_class"]
                    predicate_class = args[1]["dynamic_class"]
                else:
                    cf = classloader[args[1]["class"]]
                    if len(cf.interfaces) == 1:
                        predicate_type = cf.interfaces[0].name.value
                        predicate_class = args[1]["class"]
                    else:
                        if verbose:
                            print("Could not find predicate class for args %s and interfaces %s" % (args, cf.interfaces))
                        predicate_type = None
                        predicate_class = None

                if predicate_type in PREDICATE_CLASSES:
                    ret["predicate"] = predicate_class
                    # Will be filled in later
                    values = ["DOWN", "UP", "NORTH", "SOUTH", "EAST", "WEST"]
                elif verbose:
                    print("Unhandled args for %s" % prop)
                    values = []
            else:
                # Regular Collection (unused)
                if verbose:
                    print("Unhandled args for %s" % prop)
                values = []
            ret["values"] = values
            ret["num_values"] = len(values)
            return ret

        property_handlers = {
            'bool': handle_boolean_property,
            'int': handle_int_property,
            'enum': handle_enum_property,
            'direction': handle_direction_property
        }

        def process_property(property):
            field_name = property["field_name"]
            field_class = property["field_class"]
            try:
                field = find_field(field_class, field_name)
                if "array_index" in property:
                    field = field[property["array_index"]]
                property["field"] = field

                property["data"] = property_handlers[field["type"]](property)
            except:
                if verbose:
                    print("Failed to handle property %s (accessed as %s.%s)" % (property, field_class, field_name))
                    traceback.print_exc()
                property["data"] = None

        for cls, properties in six.iteritems(properties_by_class):
            for property in properties:
                if isinstance(property, dict):
                    process_property(property)
                elif isinstance(property, list):
                    # Slabs
                    for real_property in property:
                        process_property(real_property)
                elif property == None:
                    # Manual handling
                    pass
                elif verbose:
                    print("Skipping odd property %s (accessed from %s)" % (property, cls))

        # Part 4: attach that information to blocks.
        state_id = 0
        for block_id in aggregate["blocks"]["ordered_blocks"]:
            block = aggregate["blocks"]["block"][block_id]
            block["num_states"] = 1
            properties = properties_by_class[block["class"]]
            if len(properties) != 0 and isinstance(properties[0], list) and "slab" in block_id:
                # Convert the double-list of properties for slabs to just 1
                if "double" in block["text_id"]:
                    properties = properties[1]
                else:
                    properties = properties[1]
            block["states"] = []
            for prop in properties:
                if prop == None:
                    # Manually handle a few properties
                    if block_id == "yellow_flower":
                        prop = { "data": {
                            "type": "enum",
                            "name": "type",
                            # no field_name
                            # no enum_class
                            "values": ["DANDELION"],
                            "num_values": 1
                        }}
                    elif block_id == "red_flower":
                        prop = { "data": {
                            "type": "enum",
                            "name": "type",
                            # no field_name
                            # no enum_class
                            "values": ["POPPY", "BLUE_ORCHID", "ALLIUM", "HOUSTONIA", "RED_TULIP", "ORANGE_TULIP", "WHITE_TULIP", "PINK_TULIP", "OXEYE_DAISY"],
                            "num_values": 9
                        }}
                    else:
                        if verbose:
                            print("Skipping missing prop for %s" % block_id)
                        continue

                if not isinstance(prop, dict) or not isinstance(prop["data"], dict):
                    if verbose:
                        print("Skipping bad prop %s for %s" % (prop, block_id))
                    continue
                if "predicate" in prop["data"]:
                    data = prop["data"].copy()
                    # Fun times... guess what the predicate does,
                    # based off of the block
                    if block_id == "hopper":
                        predicate = lambda v: v != "UP"
                    elif block_id in ("powered_rail", "activator_rail", "golden_rail", "detector_rail"):
                        predicate = lambda v: v not in ("NORTH_EAST", "NORTH_WEST", "SOUTH_EAST", "SOUTH_WEST")
                    elif prop["field"]["declared_in"] == aggregate["blocks"]["block"]["torch"]["class"]:
                        # Pre-flattening
                        predicate = lambda v: v != "DOWN"
                    elif block_id == "leaves" or block_id == "log":
                        predicate = lambda v: v in ("OAK", "BIRCH", "SPRUCE", "JUNGLE")
                    elif block_id == "leaves2" or block_id == "log2":
                        predicate = lambda v: v in ("DARK_OAK", "ACACIA")
                    else:
                        if verbose:
                            print("Unhandled predicate for prop %s for %s" % (prop, block_id))
                        predicate = lambda v: False

                    data["values"] = [v for v in data["values"] if predicate(v)]
                    data["num_values"] = len(data["values"])
                else:
                    data = prop["data"]

                block["states"].append(data)
                block["num_states"] *= data["num_values"]

            if not is_flattened:
                # Each block is allocated 16 states for metadata pre-flattening
                block["num_states"] = 16
            block["min_state_id"] = state_id
            state_id += block["num_states"]
            block["max_state_id"] = state_id - 1
