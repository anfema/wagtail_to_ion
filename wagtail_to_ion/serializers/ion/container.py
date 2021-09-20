from __future__ import annotations
from typing import List, Any, Optional, Dict, Type
from collections.abc import Iterable

from .base import IonSerializer, IonSerializationError


class IonContainerSerializer(IonSerializer):
    """
    This is most probably the main serializer you will call directly. This serializes
    down to a ``containercontent`` but takes an optional sub-type and a list of children.

    See the ``add_child`` function to run the automatic type detection on a child item.
    """

    def __init__(self, name: str, subtype: Optional[str]=None, children: Optional[List[IonSerializer]]=None) -> None:
        """
        Initialize a new container content.

        :param name: the outlet name for the item
        :param subtype: optional, the sub-type of this container, usually something like
                        ``structblock`` or ``list``, defaults to ``generic``
        :param children: optional, the child-serializer items to append initially, leave out for an empty list
        """
        super().__init__(name)
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
        for child in self.children:
            resulting_child = child.serialize()
            if resulting_child is not None:
                resulting_children.append(resulting_child)

        result.update({
            "type": "containercontent",
            "subtype": self.subtype if self.subtype is not None else 'generic',
            "children": resulting_children,
        })
        return result

    def add_child(self, name: str, item: Any) -> IonSerializer:
        """
        Add a child to a container with auto-type detection over all registered serializers
        """
        serializer = IonSerializer.find_serializer(item.__class__, data=item)
        if serializer is None:
            raise IonSerializationError('No serializer found for type "{}"'.format(item.__class__.__name__))
        wrapped_item = serializer(name, item)
        self.children.append(wrapped_item)
        return wrapped_item


IonSerializer.register(IonContainerSerializer)


class IonListSerializer(IonContainerSerializer):
    """
    This serializer handles lists and serializes its children automatically.
    It runs the auto-type-detection on all list items and picks the correct serializer
    from the list of registered serializers
    """

    def __init__(self, name:str, data: List[Any]) -> None:
        super().__init__(name, subtype='list')
        for idx, item in enumerate(data):
            child = self.add_child(name + "_item", item)
            child.index = idx

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [Iterable]


IonSerializer.register(IonListSerializer)
