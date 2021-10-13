from __future__ import annotations

import logging
from typing import List, Any, Dict, Optional, Type

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models.file_based_models import AbstractIonImage
from .base import IonSerializer


logger = logging.getLogger(__name__)


class IonImageSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonImage` instances, you want to override
    this serializer if you use a ``IonImage`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonImage, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data
        self.archive = data.archive_rendition

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result['type'] = 'imagecontent'

        try:
            result['mime_type'] = self.archive.file.mime_type
            result['image'] = settings.BASE_URL + self.archive.file.url
            result['file_size'] = self.archive.file.size
            result['original_image'] = settings.BASE_URL + self.data.file.url
            result['checksum'] = self.archive.file.checksum
            result['width'] = self.archive.file.width
            result['height'] = self.archive.file.height
            result['original_mime_type'] = self.data.file.mime_type
            result['original_checksum'] = self.data.file.checksum
            result['original_width'] = self.data.file.width
            result['original_height'] = self.data.file.height
            result['original_file_size'] = self.data.file.size
        except Exception as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                log_extra = {
                    'image_filename': self.data.file.name,
                    'rendition_filename': self.archive.file.name if self.archive else None,
                }
                logger.warning('Skipped missing image or rendition file', extra=log_extra, exc_info=True)

                result['mime_type'] = 'application/x-empty'
                result['image'] = 'IMAGE_MISSING'
                result['original_image'] = 'IMAGE_MISSING'
                result['file_size'] = 0
                result['checksum'] = 'null:'
                result['width'] = 0
                result['height'] = 0
                result['original_mime_type'] = 'application/x-empty'
                result['original_checksum'] = 'null:'
                result['original_width'] = 0
                result['original_height'] = 0
                result['original_file_size'] = 0
            else:
                raise e

        result['translation_x'] = 0
        result['translation_y'] = 0
        result['scale'] = 1.0

        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [AbstractIonImage]


IonSerializer.register(IonImageSerializer)
