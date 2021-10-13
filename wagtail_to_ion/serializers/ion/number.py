from __future__ import annotations
from typing import List, Any, Union, Dict, Optional, Type
from decimal import Decimal

from .base import IonSerializer


class IonNumberSerializer(IonSerializer):
    """
    This serializer handles all kinds of numbers, be it an ``int``, a ``float`` or even
    a ``Decimal``. Be sure to have in mind that Javascript and in extension JSON only uses
    64 bit floating point numbers, so if you're using this as an ``int`` the max value you
    want to use is about 2^53 - 1 and the safe minimum is -(2^53 - 1)
    """

    def __init__(self, name: str, data: Union[int, float, Decimal], **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'numbercontent',
            'value': self.data,
        })
        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [int, float, Decimal]

    @classmethod
    def can_serialize(cls, data: Any) -> bool:
        return not isinstance(data, bool)  # don't handle `bool` (which is a subclass of `int`)


IonSerializer.register(IonNumberSerializer)
