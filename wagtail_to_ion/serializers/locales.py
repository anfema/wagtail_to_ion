# Copyright © 2019 anfema GmbH. All rights reserved.
from .base import DataObject
from wagtail_to_ion.models import get_ion_language_model


class LocaleSerializer(DataObject):

    class Meta:
        model = get_ion_language_model()
        fields = ('title', 'code', 'is_default', 'is_rtl')
