from __future__ import annotations

import datetime
import hashlib
from typing import Optional, Tuple

from django.core.files import File
from django.db.models import FileField, ImageField, Model, signals
from django.db.models.fields.files import FieldFile, FileDescriptor, ImageFieldFile, ImageFileDescriptor

import magic


def get_file_metadata(file: File, detect_mime_type: bool = True) -> Tuple[str, Optional[str]]:
    """Calculate checksum and detect mime type in one go."""
    sha256 = hashlib.sha256()
    mime_type = None
    closed = file.closed

    if closed:
        file_pos = 0
        file.open()
    else:
        file_pos = file.tell()
        file.seek(0)

    for i, chunk in enumerate(file.chunks()):
        sha256.update(chunk)
        if i == 0 and detect_mime_type:
            mime_type = magic.from_buffer(chunk, mime=True)

    if closed:
        file.close()
    else:
        file.seek(file_pos)

    return f'sha256:{sha256.hexdigest()}', mime_type


class IonFieldFile(FieldFile):
    """
    Ion specific field file.

    Provides additional properties for the files checksum, mime type and/or last modification time.

    It's implemented like django's `ImageFieldFile.height/width` properties.
    """
    _file_meta_cache: dict
    field: IonFileField

    @property
    def checksum(self) -> Optional[str]:
        """Returns the sha256 checksum of the file or `None` if the file is not available."""
        self._require_file()
        return self._get_file_meta('checksum')

    @property
    def mime_type(self) -> Optional[str]:
        """Returns the detected mime type of the file or `None` if the file is not available."""
        self._require_file()
        return self._get_file_meta('mime_type')

    @property
    def size(self) -> Optional[int]:
        """Returns the size of the file or `None` if the file is not available."""
        self._require_file()
        if not self._committed:
            return self.file.size
        return self._get_file_meta('size')

    @property
    def last_modified(self) -> Optional[datetime.datetime]:
        """Returns the last modification time of the file or `None` if the file is not available."""
        self._require_file()
        return self._get_file_meta('last_modified')

    @property
    def has_changed(self) -> bool:
        """
        Returns `True` if the file on the model instance was added or changed else `False`.

        The status is stored on the model instance and is available before and after a model.save().
        """
        return self.field.attname in self.instance._ion_uploaded_file_fields

    def _get_file_meta(self, field):
        if not hasattr(self, '_file_meta_cache'):
            self._file_meta_cache = {}
        if field in ('checksum', 'mime_type') and field not in self._file_meta_cache:
            try:
                checksum, mime_type = get_file_metadata(self)
                self._file_meta_cache['checksum'] = checksum
                self._file_meta_cache['mime_type'] = mime_type
            except Exception:  # noqa
                pass
        if field == 'size' and field not in self._file_meta_cache:
            try:
                self._file_meta_cache['size'] = self.storage.size(self.name)
            except Exception:  # noqa
                pass
        if field == 'last_modified' and field not in self._file_meta_cache:
            try:
                self._file_meta_cache['last_modified'] = self.storage.get_modified_time(self.name)
            except Exception:  # noqa
                pass
        return self._file_meta_cache.get(field)

    def save(self, name, content, save=True):
        super().save(name, content, save=False)
        # get `last_modified` value from storage backend after saving the file
        if hasattr(self, '_file_meta_cache') and 'last_modified' in self._file_meta_cache:
            del self._file_meta_cache['last_modified']
        if save:
            self.instance.save()

    def delete(self, save=True):
        # Clear the file meta cache
        if hasattr(self, '_file_meta_cache'):
            del self._file_meta_cache
        super().delete(save)


class IonFileDescriptor(FileDescriptor):
    def __set__(self, instance: Model, value):
        previous_file = instance.__dict__.get(self.field.attname)
        super().__set__(instance, value)

        if previous_file is not None:
            self.field.update_file_meta_fields(instance, force=True)
            # add field name to instance._ion_uploaded_file_fields set() if the file was added or changed
            if previous_file != getattr(instance, self.field.attname):
                instance.__dict__['_ion_uploaded_file_fields'].add(self.field.attname)


class IonFileField(FileField):
    """
    Ion specific file field.

    The field automatically sets the files checksum, mime type, size and/or last modification time
    on the configured field names of the model instance (like `width_field` & `height_field` of `ImageField`).
    """
    attr_class = IonFieldFile
    descriptor_class = IonFileDescriptor

    def __init__(
        self,
        checksum_field=None, mime_type_field=None, file_size_field=None, last_modified_field=None,
        **kwargs
    ):
        self.checksum_field = checksum_field
        self.mime_type_field = mime_type_field
        self.file_size_field = file_size_field
        self.last_modified_field = last_modified_field
        super().__init__(**kwargs)

    def update_file_meta_fields(self, instance, force=False, *args, **kwargs):
        # initialize attribute to store field names of new/changed files on the model instance
        if '_ion_uploaded_file_fields' not in instance.__dict__:
            instance.__dict__['_ion_uploaded_file_fields'] = set()

        # implementation based on `ImageField.update_dimension_fields()`
        has_file_meta_fields = any([
            self.checksum_field,
            self.mime_type_field,
            self.file_size_field,
            self.last_modified_field,
        ])
        if not has_file_meta_fields or self.attname not in instance.__dict__:
            return

        file = getattr(instance, self.attname)  # get file from file descriptor

        if not file and not force:
            return

        file_meta_fields_filled = not any([
            self.checksum_field and not getattr(instance, self.checksum_field),
            self.mime_type_field and not getattr(instance, self.mime_type_field),
            self.file_size_field and not getattr(instance, self.file_size_field),
            self.last_modified_field and not getattr(instance, self.last_modified_field),
        ])

        if file_meta_fields_filled and not force:
            # all fields are filled and force is not set; we are loading data from the database
            # (see original comments in django.db.models.fields.files.ImageField.update_dimension_fields)
            #
            # prefill the file metadata cache to support access of metadata properties without any network calls
            if file:
                if not hasattr(file, '_file_meta_cache'):
                    file._file_meta_cache = {}
                if self.checksum_field:
                    file._file_meta_cache['checksum'] = getattr(instance, self.checksum_field)
                if self.mime_type_field:
                    file._file_meta_cache['mime_type'] = getattr(instance, self.mime_type_field)
                if self.file_size_field:
                    file._file_meta_cache['size'] = getattr(instance, self.file_size_field)
                if self.last_modified_field:
                    file._file_meta_cache['last_modified'] = getattr(instance, self.last_modified_field)
            return

        if file:
            checksum = file.checksum
            mime_type = file.mime_type
            file_size = file.size
            last_modified = file.last_modified
        else:
            # No file, so clear file meta fields.
            checksum, mime_type, file_size, last_modified = None, None, None, None

        if self.checksum_field:
            setattr(instance, self.checksum_field, checksum)
        if self.mime_type_field:
            setattr(instance, self.mime_type_field, mime_type)
        if self.file_size_field:
            setattr(instance, self.file_size_field, file_size)
        if self.last_modified_field:
            setattr(instance, self.last_modified_field, last_modified)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        for field in ('checksum_field', 'mime_type_field', 'file_size_field', 'last_modified_field'):
            if getattr(self, field, None):
                kwargs[field] = getattr(self, field)
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        if not cls._meta.abstract:
            signals.post_init.connect(self.update_file_meta_fields, sender=cls)


class IonImageFieldFile(IonFieldFile, ImageFieldFile):
    pass


class IonImageFileDescriptor(IonFileDescriptor, ImageFileDescriptor):
    pass


class IonImageField(IonFileField, ImageField):
    attr_class = IonImageFieldFile
    descriptor_class = IonImageFileDescriptor
