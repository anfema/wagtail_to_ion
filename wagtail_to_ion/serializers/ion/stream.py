from __future__ import annotations
from typing import List, Type

from wagtail.core.blocks import StreamValue, StructValue
from .base import IonSerializer
from .container import IonContainerSerializer


class IonStreamValueSerializer(IonContainerSerializer):
    """
    This serializer handles wagtail streamfields. A stream-field always results in
    a container of sub-type ``streamblock`` and will contain items with an index value.
    It may contain multiple outlets with the same name if you repeatedly include the
    same block type in the stream field.
    """

    def __init__(self, name:str, data: StreamValue, **kwargs) -> None:
        super().__init__(name, subtype='streamblock', **kwargs)
        for idx, item in enumerate(data):
            item_name = str(item.block_type)
            child = self.add_child(item_name, item.value)
            child.index = idx

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [StreamValue]


IonSerializer.register(IonStreamValueSerializer)


class IonStructValueSerializer(IonContainerSerializer):
    """
    This serializer handles struct blocks. It will always render a container of sub-type
    ``structblock`` and will contain items without an index value as a single value in
    a struct is always named uniquely
    """

    def __init__(self, name: str, data: StructValue, **kwargs) -> None:
        super().__init__(name, subtype='structblock', **kwargs)
        for item_name, sub_data in data.bound_blocks.items():
            self.add_child(item_name, sub_data.value)

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [StructValue]


IonSerializer.register(IonStructValueSerializer)
