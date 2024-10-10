import argparse, os
import struct

import logging
import coloredlogs

coloredlogs.install(level=logging.CRITICAL)

from ctypes import *

from unicorn import *
from unicorn.arm_const import *

from .androidemu.emulator import Emulator
from .androidemu.const.emu_const import ARCH_ARM64

logger = logging.getLogger(__name__)

from tqdm import tqdm


class runtime_emulated(Emulator):
    ARCH = "emulated-android-aarch64"

    libcpp: object

    def c_alloc_memory(self, size: int) -> int:
        """operator new()"""
        return self.call_symbol(self.libcpp, "_Znwm", int(size))

    def c_read_memory(self, addr: int, size: int) -> bytes:
        return self.mu.mem_read(addr, size)

    def c_read_as_int(self, addr: int, size: int) -> int:
        return int.from_bytes(self.c_read_memory(addr, size), byteorder="little")

    def c_write_memory(self, addr: int, data: bytes):
        self.mu.mem_write(addr, data)

    def c_call_symbol(self, lib, symbol, *args):
        return self.call_symbol(lib, symbol, *args)

    def c_load_library(self, lib_file: str):
        return self.load_library(lib_file, do_init=False)

    def __init__(self, *a, **kw):
        data_root = os.path.dirname(__file__)
        data_root = os.path.relpath(data_root, os.getcwd())
        vfs_root = os.path.join(data_root, "vfs")
        super().__init__(
            vfs_root=vfs_root,
            config_path=os.path.join(data_root, "emu_cfg/default.json"),
            arch=ARCH_ARM64,
        )
        self.libcpp = self.c_load_library(
            os.path.join(vfs_root, "system/lib64/libc++.so")
        )


class runtime_native:
    ARCH = "native-ffi"

    def c_alloc_memory(self, size: int):
        return create_string_buffer(size)

    def c_read_memory(self, addr: int, size: int):
        return string_at(addr, size)

    def c_read_as_int(self, addr: int, size: int):
        return int.from_bytes(self.c_read_memory(addr, size), byteorder="little")

    def c_write_memory(self, addr: int, data: bytes):
        memmove(addr, data, len(data))

    def c_call_symbol(self, lib, symbol, *args):
        func = getattr(lib, symbol)
        return func(*args)

    def c_load_library(self, lib_file: str):
        return CDLL(lib_file)


class libcri_ware_unity:
    BUFFER_SIZE = int(1e5)

    libcriware: object

    handle: int
    input_buffer: int
    output_buffer: int
    p_processedLength: int
    p_outputSampleCount: int

    channelCount: int
    samplingRate: int
    bitRate: int

    def __init__(
        self,
        lib_file: str,
        c_ffi: bool,
        channelCount: int,
        samplingRate: int,
        bitRate: int,
    ):
        print("running on arch", self.ARCH)
        self.channelCount = channelCount
        self.samplingRate = samplingRate
        self.bitRate = bitRate
        self.libcriware = self.c_load_library(lib_file)
        if c_ffi:
            self.libcriware.criHcaDecoderUnity_Create.restype = c_void_p
            self.libcriware.criHcaDecoderUnity_Reset.argtypes = [
                c_void_p,
                c_uint32,
                c_uint32,
                c_uint32,
            ]
            self.libcriware.criHcaDecoderUnity_DecodeHcaToInterleavedPcm.argtypes = [
                c_void_p,
                c_void_p,
                c_uint32,
                c_uint32,
                c_void_p,
                c_void_p,
                c_void_p,
            ]
        self.c_call_symbol(self.libcriware, "criHcaDecoderUnity_Initialize")
        self.handle = self.c_call_symbol(
            self.libcriware, "criHcaDecoderUnity_Create", channelCount
        )  # number of channels
        self.c_call_symbol(
            self.libcriware,
            "criHcaDecoderUnity_Reset",
            self.handle,
            channelCount,
            samplingRate,
            bitRate,
        )  # handle, number of channels, sampling rate, bit rate
        self.input_buffer = self.c_alloc_memory(self.BUFFER_SIZE)
        self.output_buffer = self.c_alloc_memory(self.BUFFER_SIZE)
        self.p_processedLength = self.c_alloc_memory(4)
        self.p_outputSampleCount = self.c_alloc_memory(4)

    def DecodeHcaToInterleavedPcm(self, hca_data: bytes) -> bytes:
        self.c_write_memory(self.input_buffer, hca_data)
        self.c_call_symbol(
            self.libcriware,
            "criHcaDecoderUnity_DecodeHcaToInterleavedPcm",
            self.handle,
            self.input_buffer,
            0,
            len(hca_data),
            self.output_buffer,
            self.p_processedLength,
            self.p_outputSampleCount,
        )
        processedLength = self.c_read_as_int(self.p_processedLength, 4)
        outputSampleCount = self.c_read_as_int(self.p_outputSampleCount, 4)
        outputBuffer = self.c_read_memory(
            self.output_buffer, outputSampleCount * 4
        )  # float32
        return outputBuffer


class libcri_ware_unity_emulated(runtime_emulated, libcri_ware_unity):
    def __init__(
        self, lib_file: str, channelCount: int, samplingRate: int, bitRate: int
    ):
        runtime_emulated.__init__(self)
        libcri_ware_unity.__init__(
            self, lib_file, False, channelCount, samplingRate, bitRate
        )


class libcri_ware_unity_native(runtime_native, libcri_ware_unity):
    def __init__(
        self, lib_file: str, channelCount: int, samplingRate: int, bitRate: int
    ):
        runtime_native.__init__(self)
        libcri_ware_unity.__init__(
            self, lib_file, True, channelCount, samplingRate, bitRate
        )


ARCHS = [libcri_ware_unity_emulated, libcri_ware_unity_native]
ARCHS = {a.ARCH: a for a in ARCHS}


def __main__():
    parser = argparse.ArgumentParser(
        description="Project SEKAI custom streaming CRIWARE HCA Decoder"
    )
    parser.add_argument(
        "input",
        help="Path to the HCA segment, or a directory containing HCA segments (filenames must end with .hca)",
    )
    parser.add_argument("output", help="Output WAV file")
    parser.add_argument("--lib", help="Path to the CRIWARE library", required=True)
    parser.add_argument(
        "--arch",
        help="Architecture of the CRIWARE library",
        choices=ARCHS,
        default=libcri_ware_unity_emulated.ARCH,
    )
    args = parser.parse_args()
    lib = ARCHS[args.arch](args.lib, 1, 44100, 128000)
    files = []
    if os.path.isdir(args.input):
        files = [
            os.path.join(args.input, f)
            for f in os.listdir(args.input)
            if f.lower().endswith(".hca")
        ]
    else:
        files = [args.input]
    files = sorted(files)
    print("input dir:", args.input)
    print("output file:", args.output)
    with open(args.output, "wb") as out:
        out.seek(44)
        for idx, file in tqdm(enumerate(files), total=len(files)):
            hca_data = open(file, "rb").read()
            assert (
                len(hca_data) < 32768
            ), "file (%s) size too big (size=%d, max 32768)" % (file, len(hca_data))
            pcm_data = lib.DecodeHcaToInterleavedPcm(hca_data)
            out.write(pcm_data)
        data_size = out.tell() - 44
        out.seek(0)
        out.write(
            b"RIFF$\xd0\xdf\x07WAVEfmt \x10\x00\x00\x00\x03\x00\x01\x00D\xac\x00\x00\x10\xb1\x02\x00\x04\x00 \x00data\x00\xd0\xdf\x07"
        )
        out.seek(4)
        out.write(struct.pack("<I", data_size + 36))
        out.seek(40)
        out.write(struct.pack("<I", data_size))

    print("all done. going home.")


if __name__ == "__main__":
    __main__()
