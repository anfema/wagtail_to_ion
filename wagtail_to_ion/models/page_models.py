# Copyright © 2017 anfema GmbH. All rights reserved.
import json

from django.core.exceptions import ImproperlyConfigured
from django.apps import apps
from django.utils.text import slugify
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from wagtail.core.models import Page, PageRevision
from wagtail.admin.edit_handlers import FieldPanel, MultiFieldPanel
from wagtail_to_ion.conf import settings
from .abstract import AbstractCollection


if settings.ION_COLLECTION_MODEL == 'wagtail_to_ion.Collection':
    class Collection(AbstractCollection):
        pass


class Language(Page):
    is_default = models.BooleanField(default=False)
    is_rtl = models.BooleanField(default=False)
    code = models.CharField(max_length=32)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.slug.startswith('to-be-filled'):
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    # parent_page_types = [settings.ION_COLLECTION_MODEL]

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


@receiver(pre_save)
def sanitize_slug(sender, **kwargs):
    """
    Make sure all slug fields are actually slugified as wagtail does not enforce that
    """
    if not (issubclass(sender, Page) or issubclass(sender, PageRevision)):
        return
    instance = kwargs.get('instance', None)
    if hasattr(instance, 'slug'):
        instance.slug = slugify(instance.slug)
    if hasattr(instance, 'content_json'):
        data = json.loads(instance.content_json)
        if 'slug' in data:
            data['slug'] = slugify(data['slug'])
        instance.content_json = json.dumps(data)
