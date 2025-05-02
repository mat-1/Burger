from typing import Optional
from jawa.classloader import ClassLoader, ClassFile

MAPPINGS: Optional['Mappings'] = None


def set_global_mappings(mappings):
    global MAPPINGS
    MAPPINGS = mappings


class Mappings:
    __slots__ = ('classes', 'fields', 'methods', 'field_types', 'method_types')

    def __init__(self, classes, fields, methods, field_types, method_types):
        self.classes = classes
        self.fields = fields
        self.methods = methods
        self.field_types = field_types
        self.method_types = method_types

    @staticmethod
    def parse(mappings_txt: str):
        classes = {}
        fields = {}
        methods = {}
        field_types = {}
        method_types = {}

        current_obfuscated_class_name = None

        for line in mappings_txt.splitlines():
            if line.startswith('#') or line == '':
                continue

            if line.startswith('    '):
                # if a line starts with 4 spaces, that means it's a method or a field
                if '(' in line:
                    # if it has an opening parenthesis, it's a method
                    real_name_with_parameters_and_line, obfuscated_name = (
                        line.strip().split(' -> ')
                    )
                    real_name_with_parameters = (
                        real_name_with_parameters_and_line.split(':')[-1]
                    )

                    real_type, real_name = real_name_with_parameters.split('(')[
                        0
                    ].split(' ')
                    parameters = real_name_with_parameters.split('(')[1].split(')')[0]

                    if current_obfuscated_class_name not in methods:
                        methods[current_obfuscated_class_name] = {}
                        method_types[current_obfuscated_class_name] = {}
                    methods[current_obfuscated_class_name][
                        f'{obfuscated_name}({parameters})'
                    ] = real_name
                    method_types[current_obfuscated_class_name][
                        f'{obfuscated_name}({parameters})'
                    ] = real_type
                else:
                    # otherwise, it's a field
                    real_name_with_type, obfuscated_name = line.strip().split(' -> ')
                    real_type, real_name = real_name_with_type.split(' ')

                    if current_obfuscated_class_name not in fields:
                        fields[current_obfuscated_class_name] = {}
                        field_types[current_obfuscated_class_name] = {}
                    fields[current_obfuscated_class_name][obfuscated_name] = real_name
                    field_types[current_obfuscated_class_name][obfuscated_name] = (
                        real_type
                    )
            else:
                # otherwise it's a class
                real_name, obfuscated_name = line.strip(':').split(' -> ')
                current_obfuscated_class_name = obfuscated_name

                classes[obfuscated_name] = real_name

        return Mappings(classes, fields, methods, field_types, method_types)

    def deobfuscate_field_name(
        self, obfuscated_class_name: str, obfuscated_field_name: str
    ) -> Optional[str]:
        return self.fields.get(obfuscated_class_name, {}).get(obfuscated_field_name)

    def deobfuscate_class_name(self, obfuscated_class_name: str) -> str:
        if '<' in obfuscated_class_name:
            first_part, args = obfuscated_class_name.split('<')
            args = args.rstrip('>').strip(';').split(';')
            assert len(args) == 1
            arg = self.deobfuscate_class_name(args[0][1:])
            return f'{first_part}<{arg}>'
        return self.classes[obfuscated_class_name]

    def deobfuscate_method_name(
        self, obfuscated_class_name, obfuscated_method_name, obfuscated_signature
    ):
        return self.methods[obfuscated_class_name][
            f'{obfuscated_method_name}({obfuscated_signature})'
        ]

    def obfuscate_method_name(
        self, obfuscated_class_name: str, method_name: str
    ) -> str:
        for method_obfuscated_name, real_name in self.methods[
            obfuscated_class_name
        ].items():
            if real_name == method_name:
                return method_obfuscated_name.split('(')[0]
        raise ValueError(
            f'Method {method_name} not found in class {obfuscated_class_name}'
        )

    def get_field_type(self, obfuscated_class_name, obfuscated_field_name) -> str:
        return self.field_types[obfuscated_class_name][obfuscated_field_name]

    def get_method_type(
        self,
        obfuscated_class_name: str,
        obfuscated_method_name: str,
        obfuscated_signature: str,
    ) -> str:
        return self.method_types[obfuscated_class_name][
            f'{obfuscated_method_name}({obfuscated_signature})'
        ]

    def obfuscate_class_name(self, deobfuscated_name) -> Optional[str]:
        for obfuscated_name, real_name in self.classes.items():
            if real_name == deobfuscated_name:
                return obfuscated_name
        return None

    def get_class_from_classloader(
        self, classloader: ClassLoader, deobfuscated_class_name: str
    ) -> ClassFile:
        obfuscated_name = self.obfuscate_class_name(deobfuscated_class_name)
        return classloader[obfuscated_name]

    def get_method_from_classfile(
        self,
        classfile: ClassFile,
        deobfuscated_method_name: str,
        args: Optional[str] = None,
        returns: Optional[str] = None,
    ) -> Optional[str]:
        obfuscated_class_name = classfile.this.name.value
        obfuscated_name = self.obfuscate_method_name(
            obfuscated_class_name, deobfuscated_method_name
        )
        return classfile.methods.find_one(
            name=obfuscated_name, args=args, returns=returns
        )
