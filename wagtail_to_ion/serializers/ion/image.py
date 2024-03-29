from __future__ import annotations

import logging
from typing import List, Any, Dict, Optional, Type, Iterable

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models.file_based_models import AbstractIonImage, IonFileContainerInterface

from .base import IonSerializer, IonSerializerAttachedFileInterface


logger = logging.getLogger(__name__)


class IonImageSerializer(IonSerializerAttachedFileInterface, IonSerializer):
    """
    This serializer handles `AbstractIonImage` instances, you want to override
    this serializer if you use a ``IonImage`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonImage, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data
        self.archive = data.archive_rendition

    def get_files(self) -> Iterable[IonFileContainerInterface]:
        return [self.archive] if self.data.include_in_archive else []

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result['type'] = 'imagecontent'

        try:
            result['mime_type'] = self.archive.mime_type
            result['image'] = self.context['request'].build_absolute_uri(self.archive.file.url)
            result['file_size'] = self.archive.file_size
            result['original_image'] = self.context['request'].build_absolute_uri(self.data.file.url)
            result['checksum'] = self.archive.checksum
            result['width'] = self.archive.width
            result['height'] = self.archive.height
            result['original_mime_type'] = self.data.mime_type
            result['original_checksum'] = self.data.checksum
            result['original_width'] = self.data.width
            result['original_height'] = self.data.height
            result['original_file_size'] = self.data.file_size
            self.attach_files()
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
                self.clear_files()
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
