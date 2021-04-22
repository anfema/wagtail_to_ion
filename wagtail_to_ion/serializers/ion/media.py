from __future__ import annotations
from typing import List, Any, Union, Dict, Optional

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models.file_based_models import AbstractIonMedia
from .base import IonSerializer, T
from .container import IonContainerSerializer


class IonAudioSerializer(IonSerializer):
    """
    This is a sub-serializer to render audio objects, this serializer is not registered
    with the registry as it handles only a part of a media object
    """

    def __init__(self, name: str, data: AbstractIonMedia) -> None:
        super().__init__(name)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        result.update({
            'type': 'mediacontent',
            'mime_type': self.data.mime_type,
            'file': settings.BASE_URL + self.data.file.url,
            'checksum': self.data.checksum,
            'length': self.data.duration,
            'file_size': self.data.file.size,
            'name': self.data.title,
            'original_mime_type': self.data.mime_type,
            'original_file': settings.BASE_URL + self.data.file.url,
            'original_checksum': self.data.checksum,
            'original_length': self.data.duration,
            'original_file_size': self.data.file.size,
        })
        return result


class IonVideoSerializer(IonSerializer):
    """
    This is a sub-serializer to render video objects, this serializer is not registered
    with the registry as it handles only a part of a media object
    """

    def __init__(self, name: str, data: AbstractIonMedia) -> None:
        super().__init__(name)
        self.data = data
        rendition = data.renditions.filter(transcode_finished=True).first()
        if rendition is None:
            self.rendition = data
        else:
            self.rendition = rendition

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        result.update({
            'type': 'mediacontent',
            'mime_type': self.data.mime_type,
            'file': settings.BASE_URL + self.rendition.file.url,
            'checksum': self.rendition.checksum,
            'width': self.rendition.width if self.rendition.width else 0,
            'height': self.rendition.height if self.rendition.height else 0,
            'length': self.data.duration,
            'file_size': self.rendition.file.size,
            'name': self.data.title,
            'original_mime_type': self.data.mime_type,
            'original_file': settings.BASE_URL + self.data.file.url,
            'original_checksum': self.data.checksum,
            'original_width': self.data.width if self.data.width else 0,
            'original_height': self.data.height if self.data.height else 0,
            'original_length': self.data.duration,
            'original_file_size': self.data.file.size,
        })
        return result


class IonVideoThumbnailSerializer(IonSerializer):
    """
    This is a sub-serializer to render thumbnail image objects, this serializer
    is not registered with the registry as it handles only a part of a media object
    """

    def __init__(self, name: str, data: AbstractIonMedia) -> None:
        super().__init__(name)
        self.data = data
        rendition = data.renditions.filter(transcode_finished=True).first()
        if rendition is None:
            self.rendition = data
        else:
            self.rendition = rendition

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        result.update({
            'type': 'imagecontent',
            'mime_type': self.data.thumbnail_mime_type,
            'image': settings.BASE_URL + self.rendition.thumbnail.url,
            'checksum': self.rendition.thumbnail_checksum,
            'width': self.rendition.width,
            'height': self.rendition.height,
            'file_size': self.rendition.thumbnail.size,
            'original_mime_type': self.data.thumbnail_mime_type,
            'original_image': settings.BASE_URL + self.data.thumbnail.url,
            'original_checksum': self.data.thumbnail_checksum,
            'original_width': self.data.width,
            'original_height': self.data.height,
            'original_file_size': self.data.thumbnail.size,
            'translation_x': 0,
            'translation_y': 0,
            'scale': 1.0,
        })
        return result


class IonMediaSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonMedia` instances, you want to override
    this serializer if you use a ``IonMedia`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonMedia) -> None:
        super().__init__(name)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        container = IonContainerSerializer('mediacontainer_' + self.name, subtype='media')

        if self.data.file.storage.exists(self.data.file.name):
            if self.data.type == 'audio':
                container.children.append(IonAudioSerializer('audio', self.data))
            else:
                container.children.append(IonVideoSerializer('video', self.data))
                container.children.append(IonVideoThumbnailSerializer('video_thumbnail', self.data))

        return container.serialize()

    @classmethod
    def supported_types(cls) -> List[T]:
        return [AbstractIonMedia]


IonSerializer.register(IonMediaSerializer)
