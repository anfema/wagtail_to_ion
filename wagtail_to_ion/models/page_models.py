# Copyright © 2017 anfema GmbH. All rights reserved.
from django.core.exceptions import ImproperlyConfigured
from django.apps import apps
from django.utils.text import slugify
from django.db import models

from wagtail.core.models import Page
from wagtail.admin.edit_handlers import FieldPanel, MultiFieldPanel
from wagtail_to_ion.conf import settings
from .abstract import AbstractCollection
from .utils import PageMixinMeta


if settings.ION_COLLECTION_MODEL == 'wagtail_to_ion.Collection':
    class Collection(AbstractCollection):
        pass


class Language(Page, metaclass=PageMixinMeta):
    is_default = models.BooleanField(default=False)
    is_rtl = models.BooleanField(default=False)
    code = models.CharField(max_length=32)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.slug.startswith('to-be-filled'):
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    parent_page_types = [settings.ION_COLLECTION_MODEL]

    content_panels = [
        MultiFieldPanel([
            FieldPanel('title'),
            FieldPanel('code'),
            FieldPanel('is_default'),
            FieldPanel('is_rtl'),
        ])
    ]


def get_collection_model():
    """
    Return the Collection model that is active in this project.
    """
    try:
        return apps.get_model(settings.ION_COLLECTION_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "ION_COLLECTION_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "ION_COLLECTION_MODEL refers to model '%s' "
            "that has not been installed" % settings.ION_COLLECTION_MODEL
        )
