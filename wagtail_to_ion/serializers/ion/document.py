from __future__ import annotations

import logging
from typing import List, Any, Dict, Optional, Type

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models.file_based_models import AbstractIonDocument
from .base import IonSerializer


logger = logging.getLogger(__name__)


class IonDocumentSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonDocument` instances, you want to override
    this serializer if you use a ``IonDocument`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonDocument, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result['type'] = 'filecontent'
        result['name'] = self.data.title

        try:
            result['file'] = settings.BASE_URL + self.data.file.url
            result['file_size'] = self.data.file_size
            result['checksum'] = self.data.checksum
            result['mime_type'] = self.data.mime_type
        except Exception as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                log_extra = {'document_filename': self.data.file.name}
                logger.warning('Skipped missing document file', extra=log_extra, exc_info=True)

                result['file'] = 'FILE_MISSING'
                result['file_size'] = 0
                result['checksum'] = 'null:'
                result['mime_type'] = 'application/x-empty'
            else:
                raise e

        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [AbstractIonDocument]


IonSerializer.register(IonDocumentSerializer)
