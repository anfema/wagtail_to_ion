from __future__ import annotations
from typing import List, Any, Optional, Dict, Type, Mapping
from collections.abc import Iterable

from .base import IonSerializer, IonSerializationError


class IonContainerSerializer(IonSerializer):
    """
    This is most probably the main serializer you will call directly. This serializes
    down to a ``containercontent`` but takes an optional sub-type and a list of children.

    See the ``add_child`` function to run the automatic type detection on a child item.
    """

    def __init__(
        self,
        name: str,
        subtype: Optional[str] = None,
        children: Optional[List[IonSerializer]] = None,
        **kwargs,
    ) -> None:
        """
        Initialize a new container content.

        :param name: the outlet name for the item
        :param subtype: optional, the sub-type of this container, usually something like
                        ``structblock`` or ``list``, defaults to ``generic``
        :param children: optional, the child-serializer items to append initially, leave out for an empty list
        """
        super().__init__(name, **kwargs)
        self.subtype = subtype
        if children is not None:
            self.children = children
        else:
            self.children = []

    def serialize(self) -> Optional[Dict[str, Any]]:
        """
        Serialize the container recursively into a simple ``dict``
        """
        result = super().serialize()
        if result is None:
            return None
        resulting_children = []
        child_index = 0
        for child in self.children:
            resulting_child = child.serialize()
            if resulting_child is not None:
                if self.index_children:
                    resulting_child = {
                        'index': child_index,
                        **resulting_child,
                    }
                    child_index += 1
                resulting_children.append(resulting_child)

        result.update({
            "type": "containercontent",
            "subtype": self.subtype if self.subtype is not None else 'generic',
            "children": resulting_children,
        })
        return result

    def add_child(self, name: str, item: Any, context: Optional[Mapping] = None) -> IonSerializer:
        """
        Add a child to a container with auto-type detection over all registered serializers
        """
        serializer = IonSerializer.find_serializer(item.__class__, data=item)
        if serializer is None:
            raise IonSerializationError('No serializer found for type "{}"'.format(item.__class__.__name__))
        wrapped_item = serializer(name, item, context=context, parent=self)
        self.children.append(wrapped_item)
        return wrapped_item


IonSerializer.register(IonContainerSerializer)


class IonListSerializer(IonContainerSerializer):
    """
    This serializer handles lists and serializes its children automatically.
    It runs the auto-type-detection on all list items and picks the correct serializer
    from the list of registered serializers
    """

    index_children = True

    def __init__(self, name: str, data: List[Any], **kwargs) -> None:
        super().__init__(name, subtype='list', **kwargs)
        for idx, item in enumerate(data):
            self.add_child(name + "_item", item)

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [Iterable]


IonSerializer.register(IonListSerializer)


class IonMappingSerializer(IonContainerSerializer):
    """
    This serializer handles generic mappings. It will always render a container of sub-type
    ``structblock`` and will contain items without an index value as a single value in
    a mapping is always named uniquely
    """

    def __init__(self, name: str, data: Mapping, **kwargs) -> None:
        super().__init__(name, subtype='structblock', **kwargs)
        for item_name, sub_data in data.items():
            self.add_child(item_name, sub_data)

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [Mapping]


IonSerializer.register(IonMappingSerializer)
