# Copyright © 2017 anfema GmbH. All rights reserved.
from functools import partial

from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _get_model_from_settings(setting_name):
    setting_value = getattr(settings, setting_name)
    try:
        return django_apps.get_model(setting_value, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(f"{setting_name} must be of the form 'app_label.model_name'")
    except LookupError:
        raise ImproperlyConfigured(
            f"{setting_name} refers to model '{setting_value}' that has not been installed"
        )


get_ion_collection_model = partial(_get_model_from_settings, 'ION_COLLECTION_MODEL')
get_ion_language_model = partial(_get_model_from_settings, 'ION_LANGUAGE_MODEL')
get_ion_document_model = partial(_get_model_from_settings, 'WAGTAILDOCS_DOCUMENT_MODEL')
get_ion_image_model = partial(_get_model_from_settings, 'WAGTAILIMAGES_IMAGE_MODEL')
get_ion_image_rendition_model = partial(_get_model_from_settings, 'ION_RENDITION_MODEL')
get_ion_media_model = partial(_get_model_from_settings, 'WAGTAILMEDIA_MEDIA_MODEL')
get_ion_media_rendition_model = partial(_get_model_from_settings, 'ION_MEDIA_RENDITION_MODEL')
get_ion_content_type_description_model = partial(_get_model_from_settings, 'ION_CONTENT_TYPE_DESCRIPTION_MODEL')
