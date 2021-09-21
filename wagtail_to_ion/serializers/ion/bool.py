from __future__ import annotations
from typing import List, Any, Dict, Optional, Type

from .base import IonSerializer


class IonBoolSerializer(IonSerializer):
    """
    Serializes bool values as ``flagcontent``
    """

    def __init__(self, name: str, data: bool) -> None:
        super().__init__(name)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'flagcontent',
            'is_enabled': self.data
        })
        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [bool]


IonSerializer.register(IonBoolSerializer)
