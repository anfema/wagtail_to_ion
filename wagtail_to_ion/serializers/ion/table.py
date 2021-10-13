from __future__ import annotations
from typing import List, Any, Dict, Optional, Type

from .base import IonSerializer


class IonTableSerializer(IonSerializer):
    """
    This serializer will render tabular data from a ``dict``.
    It will do a sanity check before grabbing the ``dict`` data type.

    Structure should be as following:
        {
            'first_row_is_table_header': [True|False],
            'first_col_is_header': [True|False],
            'data': [
                ['first', 'row', 'columns'],
                ['second', 'row', 'columns']
            ]
        }

    """

    def __init__(self, name: str, data: dict, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data = data

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'tablecontent',
            'cells': self.data['data'],
            'first_row_header': self.data['first_row_is_table_header'],
            'first_col_header': self.data['first_col_is_header'],
        })
        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [dict]

    @classmethod
    def can_serialize(cls, data: Any) -> bool:
        return 'data' in data and 'first_row_is_table_header' in data and 'first_col_is_header' in data


IonSerializer.register(IonTableSerializer)
