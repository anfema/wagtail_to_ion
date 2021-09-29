# Copyright © 2017 anfema GmbH. All rights reserved.
import os
import calendar
import datetime

from django.conf import settings

from wagtail_to_ion.fields.files import IonFieldFile


class TarWriter:
    def __init__(self):
        self.binary_data = bytearray()

    def add_data(self, content, archive_filename, date=None):
        self.write_header(archive_filename, len(content), date=date)
        self.write_padded(content)

    def add_file(self, filename, archive_filename, date=None):
        file_stat = os.stat(filename.encode("utf-8"))
        if not date:
            date = datetime.datetime.fromtimestamp(file_stat.st_mtime)
        self.write_header(archive_filename, file_stat.st_size, date=date)
        with open(filename.encode("utf-8"), "rb") as fp:
            self.write_padded(fp.read())

    def add_file_from_storage(self, file: IonFieldFile, archive_filename: str):
        self.write_header(archive_filename, file.size or 0, date=file.last_modified)

        try:
            with file.open('rb') as fp:
                self.write_padded(fp.read())
        except Exception as e:
            if settings.ION_ALLOW_MISSING_FILES:
                pass
            else:
                raise

    def add_dir(self, archive_path, date=None):
        self.write_header(archive_path, 0, item_type=b'5', date=date)

    def data(self):
        for _ in range(0, 1024):
            self.binary_data += b"\0"
        return bytes(self.binary_data)

    def write_header(self, archive_filename, size, date=None, item_type=b'0'):
        if not date:
            date = datetime.datetime.utcnow()

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
        size_string = oct(size or 0).encode("ascii")[2:]
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
        checksum = oct(self.calc_checksum(header)).encode("ascii")[2:]
        header[148] = 48
        for i in range(149, 149 + len(checksum)):
            header[i] = checksum[i - 149]
        header[149 + len(checksum)] = 0

        self.binary_data.extend(header)

    def calc_checksum(self, header):
        checksum = 0
        for i in range(0, 512):
            checksum += header[i]
        return checksum

    def write_padded(self, content):
        self.binary_data.extend(content)
        if not len(content) % 512 == 0:
            for _ in range(len(content) % 512, 512):
                self.binary_data += b"\0"
