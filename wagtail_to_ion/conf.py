# Copyright © 2017 anfema GmbH. All rights reserved.
from django.conf import settings

settings.GET_PAGES_BY_USER = getattr(
    settings,
    'GET_PAGES_BY_USER',
    False
)

settings.ION_COLLECTION_MODEL = getattr(
    settings,
    'ION_COLLECTION_MODEL',
    'wagtail_to_ion.Collection'
)

settings.ION_ALLOW_MISSING_FILES = getattr(
    settings,
    'ION_ALLOW_MISSING_FILES',
    False

)

settings.ION_ARCHIVE_BUILD_URL_FUNCTION = getattr(
    settings,
    'ION_ARCHIVE_BUILD_URL_FUNCTION',
    None
)
