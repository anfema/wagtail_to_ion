# Copyright © 2019 anfema GmbH. All rights reserved.
from .base import DataObject
from wagtail_to_ion.models import Language


class LocaleSerializer(DataObject):

    class Meta:
        model = Language
        fields = ('title', 'code', 'is_default', 'is_rtl')
