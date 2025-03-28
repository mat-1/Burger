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

from burger.util import get_enum_constants

from .topping import Topping


def packet_name(packet):
    return '%s_%s_%02X' % (packet['state'], packet['direction'], packet['id'])


class PacketsTopping(Topping):
    """Provides minimal information on all network packets."""

    PROVIDES = ['packets.ids', 'packets.classes', 'packets.directions']

    DEPENDS = ['identify.packet.connectionstate', 'identify.packet.packetbuffer']

    @staticmethod
    def act(aggregate, classloader, verbose=False):
        packets = aggregate.setdefault('packets', {})
        packet = packets.setdefault('packet', {})
        states = packets.setdefault('states', {})
        directions = packets.setdefault('directions', {})

        PacketsTopping.parse(
            classloader,
            aggregate['classes'],
            directions,
            states,
            packet,
            verbose,
        )

        info = packets.setdefault('info', {})
        info['count'] = len(packet)

    @staticmethod
    def parse(classloader, classes, directions, states, packets, verbose):
        # The relevant code looks like this:
        """
        public enum ProtocolType {
            HANDSHAKING("handshaking"),
            PLAY("play"),
            STATUS("status"),
            LOGIN("login"),
            CONFIGURATION("configuration");

            private final String textId;
            ProtocolType(String textId) { this.textId = textId; }
            public String getTextId() { return this.textId; }
        }
        """
        # ... which does not contain packets at all. Instead, there are a bunch of different
        # things like this:
        """
        public class LoginPackets {
            public static final PacketRegistration<CustomQueryClientboundPacket> CUSTOM_QUERY_CLIENTBOUND = registerClientbound("custom_query");
            public static final PacketRegistration<GameProfileClientboundPacket> GAME_PROFILE_CLIENTBOUND = registerClientbound("game_profile");
            public static final PacketRegistration<HelloClientboundPacket> HELLO_CLIENTBOUND = registerClientbound("hello");
            public static final PacketRegistration<LoginCompressionClientboundPacket> LOGIN_COMPRESSION_CLIENTBOUND = registerClientbound("login_compression");
            public static final PacketRegistration<LoginDisconnectClientboundPacket> LOGIN_DISCONNECT_CLIENTBOUND = registerClientbound("login_disconnect");
            public static final PacketRegistration<CustomQueryAnswerServerboundPacket> CUSTOM_QUERY_ANSWER_SERVERBOUND = registerServerbound("custom_query_answer");
            public static final PacketRegistration<HelloServerboundPacket> HELLO_SERVERBOUND = registerServerbound("hello");
            public static final PacketRegistration<KeyServerboundPacket> KEY_SERVERBOUND = registerServerbound("key");
            public static final PacketRegistration<LoginAcknowledgedServerboundPacket> LOGIN_ACKNOWLEDGED_SERVERBOUND = registerServerbound("login_acknowledged");

            private static <T extends Packet<IClientLoginNetHandler>> PacketRegistration<T> registerClientbound(String name) {
                return (PacketRegistration)new PacketRegistration<>(PacketDirection.CLIENTBOUND, new ResourceLocation(name));
            }

            private static <T extends Packet<IServerLoginNetHandler>> PacketRegistration<T> registerServerbound(String name) {
                return (PacketRegistration)new PacketRegistration<>(PacketDirection.SERVERBOUND, new ResourceLocation(name));
            }
        }
        """
        # Note that StatusPackets and PingPackets are separate in this, but there is still only one ProtocolType for them.
        protocol_type_cf = classloader[classes['packet.connectionstate']]

        # Identify the enum constants:
        states.update(get_enum_constants(protocol_type_cf, verbose))
        # All 1.21 versions have CONFIGURATION
        assert states.keys() == set(
            ('HANDSHAKING', 'PLAY', 'STATUS', 'LOGIN', 'CONFIGURATION')
        )

        # The handshake class only has serverbound packets (the rest have both)
        handshake_list_cf = classloader[classes['packet.list.handshake']]
        assert len(handshake_list_cf.methods) == 3
        assert len(list(handshake_list_cf.methods.find(args='Ljava/lang/String;'))) == 1

        def check_register_method_insts(insts):
            # NOTE: simple_swap transform (from classloader configuration in munch.py) changes aload_0 to aload

            expected_instructions = (
                'new',
                'dup',
                'getstatic',
                'aload',
                'invokestatic',
                'invokespecial',
                'areturn',
            )
            assert len(insts) == len(expected_instructions)
            given_instructions = tuple(inst.mnemonic for inst in insts)
            assert given_instructions == expected_instructions, (
                f'Expected {expected_instructions}, got {given_instructions}'
            )

        handshake_register_method = handshake_list_cf.methods.find_one(
            args='Ljava/lang/String;'
        )
        handshake_register_insts = list(handshake_register_method.code.disassemble())
        check_register_method_insts(handshake_register_insts)

        direction_class = handshake_register_insts[2].operands[0].class_.name.value

        directions.update(get_enum_constants(classloader[direction_class], verbose))
        directions_by_field = {
            direction['field']: direction for direction in directions.values()
        }

        def get_register_method_direction(insts):
            return directions_by_field[insts[2].operands[0].name_and_type.name.value][
                'name'
            ]

        assert get_register_method_direction(handshake_register_insts) == 'SERVERBOUND'

        handshake_clinit_method = handshake_list_cf.methods.find_one(name='<clinit>')
        handshake_clinit_insts = list(handshake_clinit_method.code.disassemble())
        assert len(handshake_clinit_insts) == 4
        assert (
            handshake_clinit_insts[0].mnemonic == 'ldc'
            and handshake_clinit_insts[1].mnemonic == 'invokestatic'
            and handshake_clinit_insts[2].mnemonic == 'putstatic'
            and handshake_clinit_insts[3].mnemonic == 'return'
        )

        state_counter = {}

        def process_packet_list(name, state, num_register_methods=2):
            list_cf = classloader[name]
            assert len(list_cf.methods) == 2 + num_register_methods
            assert (
                len(list(list_cf.methods.find(args='Ljava/lang/String;')))
                == num_register_methods
            )

            register_method_dirs_by_method_name = {}
            for m in list_cf.methods.find(args='Ljava/lang/String;'):
                insts = list(m.code.disassemble())
                check_register_method_insts(insts)
                register_method_dirs_by_method_name[m.name.value] = (
                    get_register_method_direction(insts)
                )

            field_to_class = {}
            for f in list_cf.fields:
                # e.g. Lxz<Lagr;>; becomes agr.class (packetinstructions expects
                # .class for some reason, and that also ends up in the final JSON)
                signature = f.attributes.find_one(name='Signature').signature.value
                inner_type = signature[
                    signature.index('<') + 2 : signature.rindex('>') - 1
                ]
                field_to_class[f.name.value] = inner_type + '.class'

            clinit_insts = list(
                list_cf.methods.find_one(name='<clinit>').code.disassemble()
            )
            assert clinit_insts[-1].mnemonic == 'return'
            # Groups of 3 instructions: ldc, invokestatic, then putstatic
            assert (len(clinit_insts) - 1) % 3 == 0
            for i in range(0, len(clinit_insts) - 1, 3):
                assert (
                    clinit_insts[i + 0].mnemonic == 'ldc'
                    or clinit_insts[i + 0].mnemonic == 'ldc_w'
                )
                assert clinit_insts[i + 1].mnemonic == 'invokestatic'
                assert clinit_insts[i + 2].mnemonic == 'putstatic'

                packet_name = clinit_insts[i + 0].operands[0].string.value
                packet_dir = register_method_dirs_by_method_name[
                    clinit_insts[i + 1].operands[0].name_and_type.name.value
                ]
                packet_field_name = (
                    clinit_insts[i + 2].operands[0].name_and_type.name.value
                )
                packet_class = field_to_class[packet_field_name]

                if state not in state_counter:
                    state_counter[state] = {}
                if packet_dir in state_counter[state]:
                    id = state_counter[state][packet_dir]
                else:
                    id = 0
                state_counter[state][packet_dir] = id + 1

                from_client = packet_dir == 'SERVERBOUND'
                from_server = packet_dir == 'CLIENTBOUND'
                packet = {
                    # "id": id,  - disabled since I'm pretty sure this is the wrong way of calculating things
                    'id': -1,
                    'class': packet_class,
                    'direction': packet_dir,
                    'from_client': from_client,
                    'from_server': from_server,
                    'state': state,
                }
                packets[state + '_' + packet['direction'] + '_' + packet_name] = packet

        process_packet_list(
            classes['packet.list.handshake'], 'HANDSHAKING', num_register_methods=1
        )
        process_packet_list(classes['packet.list.login'], 'LOGIN')
        process_packet_list(classes['packet.list.cookie'], 'CONFIGURATION')
        process_packet_list(classes['packet.list.common'], 'PLAY')
        process_packet_list(classes['packet.list.game'], 'PLAY')
        process_packet_list(classes['packet.list.ping'], 'STATUS')
        process_packet_list(classes['packet.list.status'], 'STATUS')
