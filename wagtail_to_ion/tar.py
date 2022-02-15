# Copyright © 2017 anfema GmbH. All rights reserved.
from typing import Optional, Generator, List, Iterable
import os
import calendar
from itertools import islice
from datetime import datetime
from math import ceil

from multiprocessing.pool import ThreadPool

from django.http.response import StreamingHttpResponse
from django.conf import settings

from wagtail_to_ion.fields.files import IonFieldFile

PARALLEL_THREADS = 16


def chunk(it: Iterable, size: int):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())


def calc_header_checksum(data):
    checksum = 0
    for i in range(0, 512):
        checksum += data[i]
    return checksum


def write_header(archive_filename: str, size: int, date: Optional[datetime]=None, item_type: bytes=b'0'):
    if not date:
        date = datetime.utcnow()

    cutoff_filename = archive_filename[-100:]
    header = bytearray()

    # name (100 bytes)
    header += cutoff_filename.encode('utf-8')
    for i in range(len(header), 100):
        header += b"\0"

    # mode (8 bytes)
    if item_type == b'0':
        header += b"000644 \0"
    elif item_type == b'5':
        header += b"000755 \0"
    else:
        header += b"000644 \0"

    # uid (8 bytes)
    header += b"001750 \0"

    # gid (8 bytes)
    header += b"001750 \0"

    # size (12 bytes)
    size_string = oct(size).encode("ascii")[2:]
    for i in range(len(size_string), 11):
        header += b"0"
    header += size_string
    header += b" "

    # mtime (12 bytes)
    timestamp = calendar.timegm(date.utctimetuple())
    date_string = oct(timestamp).encode("ascii")[2:]
    for i in range(len(date_string), 11):
        header += b"0"
    header += date_string
    header += b" "

    # cksum (8 bytes)
    header += b"        "

    # type flag (1 byte)
    header += item_type

    # fill to padding
    for i in range(len(header), 512):
        header += b"\0"

    # add magic
    header[257:265] = b"ustar\0" + b"00"
    header[265:269] = b"user"
    header[297:302] = b"users"

    # empty device id fields
    header[329:336] = b"000000 "
    header[337:344] = b"000000 "

    # update checksum
    checksum = oct(calc_header_checksum(header)).encode("ascii")[2:]
    header[148] = 48
    for i in range(149, 149 + len(checksum)):
        header[i] = checksum[i - 149]
    header[149 + len(checksum)] = 0

    return header


class TarData:
    def __init__(self, archive_filename: str, content: bytearray, date: Optional[datetime]=None) -> None:
        self.header = write_header(archive_filename, len(content), date=date)
        self.content = self._padded(content)

    def _padded(self, content: bytearray):
        if not len(content) % 512 == 0:
            for _ in range(len(content) % 512, 512):
                content += b"\0"
        return content

    def data(self, block_size: int=512) -> Generator[bytes, None, None]:
        yield bytes(self.header)
        for i in range(ceil(len(self.content)/block_size)):
            yield bytes(self.content[i * block_size:(i + 1) * block_size])

    def prepare(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    @property
    def size(self) -> int:
        return len(self.header) + len(self.content)


class TarFile(TarData):
    def __init__(self, filename: str, archive_filename: Optional[str]=None, date: Optional[datetime]=None) -> None:
        self.filename = filename.encode("utf-8")
        self.fp = None

        self.filesize = 0
        try:
            file_stat = os.stat(self.filename)
            self.filesize = file_stat.st_size
        except FileNotFoundError:
            if settings.ION_ALLOW_MISSING_FILES:
                pass
            else:
                raise

        if not date:
            date = datetime.fromtimestamp(file_stat.st_mtime)

        self.header = write_header(archive_filename, self.filesize, date=date)

    def data(self, block_size: int = 512) -> Generator[bytes, None, None]:
        yield bytes(self.header)

        if self.fp is not None:
            for i in range(ceil(self.filesize/block_size)):
                yield self.fp.read(block_size)

        if self.filesize % 512 != 0:
            yield b"\0" * (512 - (self.filesize % 512))

    def prepare(self) -> None:
        try:
            self.fp = open(self.filename, 'rb')
        except FileNotFoundError:
            if settings.ION_ALLOW_MISSING_FILES:
                pass
            else:
                raise

    def cleanup(self) -> None:
        self.fp.close()
        self.fp = None

    @property
    def size(self) -> int:
        if self.filesize % 512 != 0:
            return len(self.header) + self.filesize + (512 - (self.filesize % 512))
        else:
            return len(self.header) + self.filesize


class TarStorageFile(TarData):
    def __init__(self, file: IonFieldFile, archive_filename: str) -> None:
        self.fp = None
        self.file = file
        self.archive_filename = archive_filename

    def data(self, block_size: int = 512) -> Generator[bytes, None, None]:
        if self.file is not None and self.fp is not None:
            yield bytes(write_header(self.archive_filename, self.file.size, date=self.file.last_modified))  # Try to use the already open connection to avoid head call
            for i in range(ceil(self.file.size/block_size)):
                yield self.fp.read(block_size)
            if self.file.size % 512 != 0:
                yield b"\0" * (512 - (self.file.size % 512))
        else:
            # Fill with zeroes
            for i in range(ceil(self.file.size/block_size)):
                yield b"\0" * 512

    def prepare(self) -> None:
        try:
            self.fp = self.file.open('rb')
        except Exception:  # noqa (storage backends might raise an unknown exception)
            if settings.ION_ALLOW_MISSING_FILES:
                pass
            else:
                raise

    def cleanup(self) -> None:
        if self.fp:
            self.fp.close()
        self.fp = None

    @property
    def size(self) -> int:
        if self.file.size % 512 != 0:
            return 512 + self.file.size + (512 - (self.file.size % 512))
        else:
            return 512 + self.file.size


class TarDir(TarData):
    def __init__(self, archive_path: str, date: Optional[datetime]=None) -> None:
        self.header = write_header(archive_path, 0, item_type=b'5', date=date)
        self.content = bytearray()


class TarWriter(StreamingHttpResponse):
    def __init__(self):
        super().__init__(content_type='application/x-tar', status=200)
        self._items: List[TarData] = []

    def add_item(self, item: TarData):
        self._items.append(item)

    def data(self, block_size: int=1024*16) -> Generator[bytes, None, None]:
        with ThreadPool(processes=PARALLEL_THREADS) as pool:
            for c in chunk(self._items, PARALLEL_THREADS):
                pool.map(self.prepare, c)

                for item in c:
                    for data in item.data(block_size=block_size):
                        yield data

                pool.map(self.cleanup, c)

        yield b"\0" * 1024

    def prepare(self, item: TarData, *args):
        item.prepare()

    def cleanup(self, item: TarData, *args):
        item.cleanup()

    @property
    def size(self) -> int:
        sz = 0
        for item in self._items:
            sz += item.size
        return sz

    @property
    def streaming_content(self):
        return self.data()

    @streaming_content.setter
    def streaming_content(self, value):
        pass
