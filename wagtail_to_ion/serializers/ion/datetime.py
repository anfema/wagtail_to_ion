from __future__ import annotations
from typing import List, Any, Union, Dict, Optional, Type
from datetime import date, datetime

from wagtail_to_ion.utils import isoDate
from .base import IonSerializer


class IonDateTimeSerializer(IonSerializer):
    """
    This serializer handles ``date`` and ``datetime`` objects
    """

    def __init__(self, name: str, data: Union[date, datetime], **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result['type'] = 'datetimecontent'

        if isinstance(self.data, date) and not isinstance(date, datetime):
            result['datetime'] = isoDate(datetime(self.data.year, month=self.data.month, day=self.data.day))
        else:
            result['datetime'] = isoDate(self.data)

        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [date, datetime]


IonSerializer.register(IonDateTimeSerializer)
