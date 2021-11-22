from __future__ import annotations

import weakref
from typing import List, Any, Dict, ClassVar, Optional, Type, Deque, Mapping, Iterable, Set
from collections import deque
import json

from wagtail_to_ion.models.file_based_models import IonFileContainerInterface


class IonSerializationError(Exception):
    """
    This serialization error is thrown when a type in the ION tree can not be serialized because there
    is no serializer registered for its type.
    """
    pass


class IonSerializerAttachedFileInterface:
    """
    Interface for serializers with attached files.
    """

    _attached_files: Set[IonFileContainerInterface] = None  # Set of attached files; attached on successful serialization

    @property
    def attached_files(self):
        if self._attached_files is None:
            raise RuntimeError('Attached files are available after successful serialization')
        return self._attached_files

    def get_files(self) -> Iterable[IonFileContainerInterface]:
        raise NotImplementedError

    def attach_files(self):
        self._attached_files = set(self.get_files())

    def clear_files(self):
        self._attached_files = set()


class IonSerializer:
    """
    This is the base serializer class, you will need to use this class directly
    to register new serializers for new types.
    """

    registry: ClassVar[Deque[Type[IonSerializer]]] = deque()  # This is the serializer registry

    index_children: ClassVar[bool] = False  # flag to indicate if children of this serializer get an index field

    name: str
    index: Optional[int]

    _context: Optional[Mapping] = None
    _parent = None  # type: weakref.ReferenceType[IonSerializer]

    def __init__(
        self,
        name: str,
        *args,
        context: Optional[Mapping] = None,
        parent: Optional[IonSerializer] = None,
    ) -> None:
        """
        By default we only take a name to initialize a serializer (this maps to the outlet name),
        but this will be expanded with a second parameter ``data`` for all subclasses to take the
        actual data to serialize.
        """
        self.name = name  # Outlet name
        self.index = None  # Set to a value to serialize an ``index`` attribute into the output
        if context is not None:
            self.context = context
        if parent is not None:
            self.parent = parent

    def serialize(self) -> Optional[Dict[str, Any]]:
        """
        This serialization function is called to generate a ``dict`` of the contained data.
        This should only contain simple datatypes to be able to serialize to json.
        If this function returns ``None`` the object is silently skipped.
        """

        # Default structure for all items
        result = {
            'outlet': self.name,
            'variation': 'default',
            'is_searchable': False
        }

        # Add index only if not deactivated by setting it to ``None```
        if self.index is not None:
            result['index'] = int(self.index)
        return result

    def json(self):
        """
        Simple debugging function to test if we can serialize to json without problems
        """
        return json.dumps(self.serialize())

    @property
    def context(self) -> Mapping:
        if self._context is not None:
            return self._context
        if self.parent is not None:
            return self.parent.context
        return {}

    @context.setter
    def context(self, context: Mapping) -> None:
        self._context = context

    @property
    def parent(self) -> Optional[IonSerializer]:
        return self._parent() if self._parent is not None else None

    @parent.setter
    def parent(self, parent: IonSerializer) -> None:
        self._parent = weakref.ref(parent)

    @classmethod
    def supported_types(cls) -> List[Type]:
        """
        Subclasses will return the classes of data they can serialize (e.g. ``str`` or ``int`` or custom classes)
        """
        return []

    @classmethod
    def can_serialize(cls, data: Any) -> bool:
        """
        If a simple type-check is not enough a class can implement this function to do a sanity check on the
        data that is to be serialized. (e.g. class takes a ``dict`` as input but needs specific keys)
        """
        return True

    @classmethod
    def find_serializer(cls, target: Any, data: Optional[Any] = None) -> Optional[Type[IonSerializer]]:
        """
        This finds a serializer for a target data type. Optionally you can give the function the object
        that is to be serialized to run a sanity check on the data before even initializing the serializer.
        It returns the serializer class.
        """
        for serializer in cls.registry:
            types = serializer.supported_types()
            for t in types:
                if issubclass(target, t):
                    if data is not None and not serializer.can_serialize(data):
                        continue
                    return serializer
        return None

    @classmethod
    def register(cls, serializer: Type[IonSerializer]) -> None:
        """
        Use this function to register a new serializer class with the system. The serializer will be
        picked automatically when the ``supported_types`` and the ``can_serialize`` checks pass.
        The registry is a stack, so the last registered serializer for a type will win over previuously
        registered serializers.
        """
        cls.registry.appendleft(serializer)
