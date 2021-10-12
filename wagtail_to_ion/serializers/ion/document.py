from __future__ import annotations
from typing import List, Any, Union, Dict, Optional

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models.file_based_models import AbstractIonDocument
from .base import IonSerializer, T


class IonDocumentSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonDocument` instances, you want to override
    this serializer if you use a ``IonDocument`` class that has additional properties
    """

    def __init__(self, name: str, data: AbstractIonDocument) -> None:
        super().__init__(name)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        result['type'] = 'filecontent'

        result['mime_type'] = self.data.mime_type
        result['name'] = self.data.title
        try:
            result['file'] = settings.BASE_URL + self.data.file.url
            result['file_size'] = self.data.file.size
        except FileNotFoundError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                result['file'] = 'FILE_MISSING'
                result['file_size'] = 0
            else:
                raise e
        result['checksum'] = self.data.checksum

        return result

    @classmethod
    def supported_types(cls) -> List[T]:
        return [AbstractIonDocument]


IonSerializer.register(IonDocumentSerializer)