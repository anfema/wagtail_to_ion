from __future__ import annotations
from typing import List, Any, Union, Dict, Optional

from .base import IonSerializer, T


class IonNoneSerializer(IonSerializer):
    """
    This is the ``None`` serializer, currently it returns ``None`` on it's serialize
    call so the object to serialize is silently skipped and not included in the resulting json.
    You can override this behaviour by registering another serializer that handles the same
    datatype and returns something other in ``serialize``
    """

    def __init__(self, name: str, data: None) -> None:
        super().__init__(name)

    def serialize(self) -> Optional[Dict[str, Any]]:
        return None

    @classmethod
    def supported_types(cls) -> List[T]:
        return [type(None)]


IonSerializer.register(IonNoneSerializer)