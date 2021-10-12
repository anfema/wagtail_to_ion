from __future__ import annotations
from typing import List, Any, Union, Dict, Optional

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models.file_based_models import AbstractIonImage
from .base import IonSerializer, T


class IonImageSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonImage` instances, you want to override
    this serializer if you use a ``IonImage`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonImage) -> None:
        super().__init__(name)
        self.data = data
        self.archive = data.archive_rendition


    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        result['type'] = 'imagecontent'

        try:
            result['mime_type'] = self.archive.mime_type
            result['image'] = settings.BASE_URL + self.archive.file.url
            result['file_size'] = self.archive.file.file.size
            result['original_image'] = settings.BASE_URL + self.data.file.url
            result['checksum'] = self.archive.checksum
            result['width'] = self.archive.width
            result['height'] = self.archive.height
        except (ValueError, AttributeError) as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                result['mime_type'] = 'application/x-empty'
                result['image'] = 'IMAGE_MISSING'
                result['original_image'] = 'IMAGE_MISSING'
                result['file_size'] = 0
                result['checksum'] = 'null:'
                result['width'] = 0
                result['height'] = 0
            else:
                raise e

        result['original_mime_type'] = self.data.mime_type
        result['original_checksum'] = self.data.checksum
        result['original_width'] = self.data.width
        result['original_height'] = self.data.height
        result['original_file_size'] = self.data.get_file_size()
        result['translation_x'] = 0
        result['translation_y'] = 0
        result['scale'] = 1.0

        return result

    @classmethod
    def supported_types(cls) -> List[T]:
        return [AbstractIonImage]


IonSerializer.register(IonImageSerializer)