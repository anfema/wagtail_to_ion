from __future__ import annotations

import logging
from typing import List, Any, Dict, Optional, Type, Iterable

from wagtail_to_ion.models.file_based_models import AbstractIonMedia, IonFileContainerInterface

from .base import IonSerializer, IonSerializerAttachedFileInterface
from .container import IonContainerSerializer


logger = logging.getLogger(__name__)


class IonAudioSerializer(IonSerializerAttachedFileInterface, IonSerializer):
    """
    This is a sub-serializer to render audio objects, this serializer is not registered
    with the registry as it handles only a part of a media object
    """

    def __init__(self, name: str, data: AbstractIonMedia, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def get_files(self) -> Iterable[IonFileContainerInterface]:
        return [self.data] if self.data.include_in_archive else []

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'mediacontent',
            'mime_type': self.data.mime_type,
            'file': self.context['request'].build_absolute_uri(self.data.file.url),
            'checksum': self.data.checksum,
            'length': self.data.duration,
            'file_size': self.data.file_size,
            'name': self.data.title,
            'original_mime_type': self.data.mime_type,
            'original_file': self.context['request'].build_absolute_uri(self.data.file.url),
            'original_checksum': self.data.checksum,
            'original_length': self.data.duration,
            'original_file_size': self.data.file_size,
        })
        self.attach_files()
        return result


class IonVideoSerializer(IonSerializerAttachedFileInterface, IonSerializer):
    """
    This is a sub-serializer to render video objects, this serializer is not registered
    with the registry as it handles only a part of a media object
    """

    def __init__(self, name: str, data: AbstractIonMedia, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data
        self.rendition = data.archive_rendition or data

    def get_files(self) -> Iterable[IonFileContainerInterface]:
        return [self.rendition] if self.data.include_in_archive else []

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'mediacontent',
            'mime_type': self.data.mime_type,
            'file': self.context['request'].build_absolute_uri(self.rendition.file.url),
            'checksum': self.rendition.checksum,
            'width': self.rendition.width if self.rendition.width else 0,
            'height': self.rendition.height if self.rendition.height else 0,
            'length': self.data.duration,
            'file_size': self.rendition.file_size,
            'name': self.data.title,
            'original_mime_type': self.data.mime_type,
            'original_file': self.context['request'].build_absolute_uri(self.data.file.url),
            'original_checksum': self.data.checksum,
            'original_width': self.data.width if self.data.width else 0,
            'original_height': self.data.height if self.data.height else 0,
            'original_length': self.data.duration,
            'original_file_size': self.data.file_size,
        })
        self.attach_files()
        return result


class IonVideoThumbnailSerializer(IonSerializerAttachedFileInterface, IonSerializer):
    """
    This is a sub-serializer to render thumbnail image objects, this serializer
    is not registered with the registry as it handles only a part of a media object
    """

    def __init__(self, name: str, data: AbstractIonMedia, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data
        self.rendition = data.archive_rendition or data

    def get_files(self) -> Iterable[IonFileContainerInterface]:
        return [self.rendition] if self.data.include_in_archive else []

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'imagecontent',
            'mime_type': self.data.thumbnail_mime_type,
            'image': self.context['request'].build_absolute_uri(self.rendition.thumbnail.url),
            'checksum': self.rendition.thumbnail_checksum,
            'width': self.rendition.width,
            'height': self.rendition.height,
            'file_size': self.rendition.thumbnail.size,
            'original_mime_type': self.data.thumbnail_mime_type,
            'original_image': self.context['request'].build_absolute_uri(self.data.thumbnail.url),
            'original_checksum': self.data.thumbnail_checksum,
            'original_width': self.data.width,
            'original_height': self.data.height,
            'original_file_size': self.data.thumbnail.size,
            'translation_x': 0,
            'translation_y': 0,
            'scale': 1.0,
        })
        self.attach_files()
        return result


class IonMediaSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonMedia` instances, you want to override
    this serializer if you use a ``IonMedia`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonMedia, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        container = IonContainerSerializer('mediacontainer_' + self.name, subtype='media', parent=self.parent)

        if self.data.type == 'audio':
            container.children.append(IonAudioSerializer('audio', self.data, parent=container, context=self.context))
        else:
            container.children.append(IonVideoSerializer('video', self.data, parent=container, context=self.context))
            container.children.append(
                IonVideoThumbnailSerializer('video_thumbnail', self.data, parent=container, context=self.context)
            )

        return container.serialize()

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [AbstractIonMedia]


IonSerializer.register(IonMediaSerializer)
