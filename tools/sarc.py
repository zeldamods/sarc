#!/usr/bin/env python3
# Copyright 2018 leoetlino <leo@leolam.fr>
# Licensed under MIT

import io
import json
from operator import itemgetter
import os
import struct
import sys
import typing
import yaml

import rstb
import yaz0_util

def _get_unpack_endian_character(big_endian: bool):
    return '>' if big_endian else '<'

_NUL_CHAR = b'\x00'

class SARC:
    """A simple SARC reader.

    Original implementation by NWPlayer123. This version has been heavily edited
    to be usable as a library, handle little endian and fix broken yaz0 support.
    """
    def __init__(self, data: typing.Union[memoryview, bytes]) -> None:
        self._data = memoryview(data)
        if data[0:4] != b"SARC":
            raise ValueError("Not a SARC")
        self._be = data[6:8] == b"\xFE\xFF"
        if not self._be and data[6:8] != b"\xFF\xFE":
            raise ValueError("Invalid BOM")

        pos = 12
        self._doff: int = self._read_u32(pos);pos += 8 #Start of data section

        magic2 = self._data[pos:pos + 4];pos += 6
        assert magic2 == b"SFAT"
        nodec = self._read_u16(pos);pos += 6 #Node Count
        nodes: list = []
        for x in range(nodec):
            pos += 8
            srt  = self._read_u32(pos);pos += 4 #File Offset Start
            end  = self._read_u32(pos);pos += 4 #File Offset End
            nodes.append([srt, end])

        magic3 = self._data[pos:pos + 4];pos += 8
        assert magic3 == b"SFNT"
        self._files: dict = dict()
        for node in nodes:
            pos = (pos + 3) & -4
            string = self._read_string(pos)
            pos += len(string) + 1
            self._files[string] = node

    def get_data_offset(self) -> int:
        return self._doff

    def get_file_offsets(self) -> typing.List[typing.Tuple[str, int]]:
        offsets: list = []
        for name, node in self._files.items():
            offsets.append((name, node[0]))
        return sorted(offsets, key=itemgetter(1))

    def list_files(self):
        return self._files.keys()

    def is_archive(self, name: str) -> bool:
        node = self._files[name]
        size = node[1] - node[0]
        if size < 4:
            return False

        magic = self._data[self._doff + node[0]:self._doff + node[0] + 4]
        if magic == b"SARC":
            return True
        if magic == b"Yaz0":
            if size < 0x15:
                return False
            fourcc = self._data[self._doff + node[0] + 0x11:self._doff + node[0] + 0x15]
            return fourcc == b"SARC"
        return False

    def get_file_data(self, name: str) -> memoryview:
        node = self._files[name]
        return memoryview(self._data[self._doff + node[0]:self._doff + node[1]])

    def get_file_size(self, name: str) -> int:
        node = self._files[name]
        return node[1] - node[0]

    def get_file_data_offset(self, name: str) -> int:
        return self._files[name][0]

    def extract(self, archive_name: str) -> None:
        name, ext = os.path.splitext(archive_name)
        try: os.mkdir(name)
        except: pass
        for file_name, node in self._files.items():
            filename = name + "/" + file_name
            if not os.path.exists(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
            filedata = self._data[self._doff + node[0]:self._doff + node[1]]
            print(filename)
            with open(filename, 'wb') as f:
                f.write(filedata) # type: ignore

    def _read_u16(self, offset: int) -> int:
        return struct.unpack_from(_get_unpack_endian_character(self._be) + 'H', self._data, offset)[0]
    def _read_u32(self, offset: int) -> int:
        return struct.unpack_from(_get_unpack_endian_character(self._be) + 'I', self._data, offset)[0]
    def _read_string(self, offset: int) -> str:
        end = self._data.obj.find(_NUL_CHAR, offset) # type: ignore
        return self._data[offset:end].tobytes().decode('utf-8')

class _PlaceholderOffsetWriter:
    """Writes a placeholder offset value that will be filled later."""
    def __init__(self, stream: typing.BinaryIO, parent) -> None:
        self._stream = stream
        self._offset = stream.tell()
        self._parent = parent
    def write_placeholder(self) -> None:
        self._stream.write(self._parent._u32(0xffffffff))
    def write_offset(self, offset: int, base: int = 0) -> None:
        current_offset = self._stream.tell()
        self._stream.seek(self._offset)
        self._stream.write(self._parent._u32(offset - base))
        self._stream.seek(current_offset)
    def write_current_offset(self, base: int = 0) -> None:
        self.write_offset(self._stream.tell(), base)

def _align_up(n: int, alignment: int) -> int:
    return (n + alignment - 1) & -alignment

def _load_aglenv_file_info() -> typing.List[dict]:
    with open(os.path.dirname(os.path.realpath(__file__)) + '/aglenv_file_info.yml', 'r', encoding='utf-8') as f:
        return yaml.load(f, Loader=yaml.CSafeLoader) # type: ignore

def _load_botw_resource_factory_info() -> typing.Dict[str, rstb.SizeCalculator.Factory]:
    return rstb.SizeCalculator().get_factory_info()

class SARCWriter:
    _aglenv_file_info = _load_aglenv_file_info()
    _botw_resource_factory_info = _load_botw_resource_factory_info()

    class File(typing.NamedTuple):
        name: str
        data: typing.Union[memoryview, bytes]

    def __init__(self, be: bool) -> None:
        self._be = be
        self._hash_multiplier = 0x65
        self._files: typing.Dict[int, SARCWriter.File] = dict()
        self._alignment: typing.Dict[str, int] = dict()
        self._default_alignment = 4

    def set_default_alignment(self, value: int) -> None:
        if value == 0 or value & (value - 1) != 0:
            raise ValueError('Alignment must be a non-zero power of 2')
        self._default_alignment = value

    def _refresh_alignment_info(self) -> None:
        self._alignment = dict()
        for entry in self._aglenv_file_info:
            self.add_alignment_requirement(entry['ext'], entry['align'])
            self.add_alignment_requirement(entry['bext'], entry['align'])
        # BotW: Pack/Bootup.pack/Env/env.sgenvb/postfx/*.bksky (AAMP)
        self.add_alignment_requirement('ksky', 8)
        self.add_alignment_requirement('bksky', 8)
        # BotW: Pack/TitleBG.pack/Terrain/System/tera_resource.Nin_NX_NVN.release.ssarc
        self.add_alignment_requirement('gtx', 0x2000)
        self.add_alignment_requirement('sharcb', 0x1000)
        self.add_alignment_requirement('sharc', 0x1000)
        # BotW: Pack/Bootup.pack/Layout/MultiFilter.ssarc/*.baglmf (AAMP)
        self.add_alignment_requirement('baglmf', 0x80)
        # BotW: Event/*.beventpack
        # For some reason, bfevfl are aligned even when they don't need to. But only those
        # that are in beventpacks...
        def has_only_event_packs() -> bool:
            for file in self._files.values():
                if not (file.name.startswith('EventFlow/') and file.name.endswith('.bfevfl')):
                    return False
            return True
        if has_only_event_packs():
            self.add_alignment_requirement('bfevfl', 0x100)
        # BotW: Font/*.bfarc/.bffnt
        self.add_alignment_requirement('bffnt', 0x1000 if not self._be else 0x2000)

    def set_big_endian(self, be: bool) -> None:
        self._be = be

    def add_alignment_requirement(self, extension_without_dot: str, alignment: int) -> None:
        self._alignment[extension_without_dot] = abs(alignment)

    def _get_file_alignment_for_new_binary_file(self, file: File) -> int:
        """Detects alignment requirements for binary files with new nn::util::BinaryFileHeader."""
        if len(file.data) <= 0x20:
            return 0
        bom = file.data[0xc:0xc+2]
        if bom != b'\xff\xfe' and bom != b'\xfe\xff':
            return 0

        be = bom == b'\xfe\xff'
        file_size: int = struct.unpack_from(_get_unpack_endian_character(be) + 'I', file.data, 0x1c)[0]
        if len(file.data) != file_size:
            return 0
        return 1 << file.data[0xe]

    def _get_file_alignment_for_old_bflim(self, file: File) -> int:
        # XXX: should another flag be added for the platform?
        if not self._be:
            return 0
        if len(file.data) <= 0x28 or file.data[-0x28:-0x24] != b'FLIM':
            return 0
        return struct.unpack('>H', file.data[-0x8:-0x6])[0]

    def _get_alignment_for_file_data(self, file: File) -> int:
        ext = os.path.splitext(file.name)[1][1:]
        alignment = self._alignment.get(ext, self._default_alignment)
        if ext not in self._botw_resource_factory_info:
            alignment = max(alignment, self._get_file_alignment_for_new_binary_file(file))
            alignment = max(alignment, self._get_file_alignment_for_old_bflim(file))
        return alignment

    def _hash_file_name(self, name: str) -> int:
        h = 0
        for c in name:
            h = (ord(c) + h * self._hash_multiplier) & 0xffffffff
        return h

    def add_file(self, name: str, data: typing.Union[memoryview, bytes]) -> None:
        self._files[self._hash_file_name(name)] = SARCWriter.File(name, data)

    def delete_file(self, name: str) -> None:
        del self._files[self._hash_file_name(name)]

    def get_file_offsets(self) -> typing.List[typing.Tuple[str, int]]:
        self._refresh_alignment_info()
        offsets: list = []
        data_offset = 0
        for h in sorted(self._files.keys()):
            alignment = self._get_alignment_for_file_data(self._files[h])
            data_offset = _align_up(data_offset, alignment)
            offsets.append((self._files[h].name, data_offset))
            data_offset += len(self._files[h].data)
        return offsets

    def write(self, stream: typing.BinaryIO) -> int:
        self._refresh_alignment_info()

        # SARC header
        stream.write(b'SARC')
        stream.write(self._u16(0x14))
        stream.write(self._u16(0xfeff))
        file_size_writer = self._write_placeholder_offset(stream)
        data_offset_writer = self._write_placeholder_offset(stream)
        stream.write(self._u16(0x100))
        stream.write(self._u16(0)) # Unused.

        # SFAT header
        stream.write(b'SFAT')
        stream.write(self._u16(0xc))
        stream.write(self._u16(len(self._files)))
        stream.write(self._u32(self._hash_multiplier))

        # Node information
        sorted_hashes = sorted(self._files.keys())
        file_alignments: typing.List[int] = []
        string_offset = 0
        data_offset = 0
        # Some files have specific alignment requirements. These must be satisfied by
        # aligning file offsets *and* the data offset to the maximum alignment value
        # since file offsets are always relative to the data offset.
        data_offset_alignment = 1
        for h in sorted_hashes:
            stream.write(self._u32(h))
            stream.write(self._u32(0x01000000 | (string_offset >> 2)))
            alignment = self._get_alignment_for_file_data(self._files[h])
            data_offset_alignment = max(data_offset_alignment, alignment)
            file_alignments.append(alignment)
            data_offset = _align_up(data_offset, alignment)
            stream.write(self._u32(data_offset))
            data_offset += len(self._files[h].data)
            stream.write(self._u32(data_offset))
            string_offset += _align_up(len(self._files[h].name) + 1, 4)

        # File name table
        stream.write(b'SFNT')
        stream.write(self._u16(8))
        stream.write(self._u16(0))
        for h in sorted_hashes:
            stream.write(self._files[h].name.encode())
            stream.write(_NUL_CHAR)
            stream.seek(_align_up(stream.tell(), 4))

        # File data
        stream.seek(_align_up(stream.tell(), data_offset_alignment))
        for i, h in enumerate(sorted_hashes):
            stream.seek(_align_up(stream.tell(), file_alignments[i]))
            if i == 0:
                data_offset_writer.write_current_offset()
            stream.write(self._files[h].data) # type: ignore

        # Write the final file size.
        file_size_writer.write_current_offset()
        return data_offset_alignment

    def _write_placeholder_offset(self, stream) -> _PlaceholderOffsetWriter:
        p = _PlaceholderOffsetWriter(stream, self)
        p.write_placeholder()
        return p

    def _u16(self, value: int) -> bytes:
        return struct.pack(_get_unpack_endian_character(self._be) + 'H', value)
    def _u32(self, value: int) -> bytes:
        return struct.pack(_get_unpack_endian_character(self._be) + 'I', value)

def read_file_and_make_sarc(f: typing.BinaryIO) -> typing.Optional[SARC]:
    f.seek(0)
    magic: bytes = f.read(4)
    if magic == b"Yaz0":
        f.seek(0x11)
        first_data_group_fourcc: bytes = f.read(4)
        f.seek(0)
        if first_data_group_fourcc != b"SARC":
            return None
        data = yaz0_util.decompress(f.read())
    elif magic == b"SARC":
        f.seek(0)
        data = f.read()
    else:
        return None
    return SARC(data)

def make_writer_from_sarc(sarc: SARC, filter_fn: typing.Optional[typing.Callable[[str], bool]]) -> typing.Optional[SARCWriter]:
    writer = SARCWriter(be=sarc._be)
    for file in sarc.list_files():
        if not filter_fn or filter_fn(file):
            writer.add_file(file, sarc.get_file_data(file))

    return writer

def read_sarc_and_make_writer(f: typing.BinaryIO, filter_fn: typing.Optional[typing.Callable[[str], bool]]) -> typing.Optional[SARCWriter]:
    sarc = read_file_and_make_sarc(f)
    if not sarc:
        return None
    return make_writer_from_sarc(sarc, filter_fn)
