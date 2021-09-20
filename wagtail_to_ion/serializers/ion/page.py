from __future__ import annotations
from typing import List, Any, Union, Dict, Optional, Type

from wagtail.core.models import Page
from wagtail_to_ion.models.abstract import AbstractIonPage
from wagtail_to_ion.utils import get_collection_for_page

from .base import IonSerializer


class IonPageSerializer(IonSerializer):
    """
    This serializer handles `AbstractIonPage` instances, you may want to override
    this serializer if you use a ``IonPage`` class that has additional properties,
    but usually this serializes into a link to a page which is defined by it's slug
    and collection only.
    """

    def __init__(self, name: str, data: Union[AbstractIonPage, Page]) -> None:
        super().__init__(name)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'connectioncontent',
            'connection_string': '//{}/{}'.format(get_collection_for_page(self.data), self.data.slug),
        })
        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [AbstractIonPage, Page]


IonSerializer.register(IonPageSerializer)
