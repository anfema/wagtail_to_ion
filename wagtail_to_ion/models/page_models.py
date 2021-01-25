# Copyright © 2017 anfema GmbH. All rights reserved.
import json

from django.utils.text import slugify
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from wagtail.core.models import Page, PageRevision
from wagtail.admin.edit_handlers import FieldPanel, MultiFieldPanel

from .abstract import AbstractIonPage


class AbstractIonLanguage(AbstractIonPage):
    is_default = models.BooleanField(default=False)
    is_rtl = models.BooleanField(default=False)
    code = models.CharField(max_length=32)

    class Meta:
        abstract = True

    ion_api_object_name = 'language'

    # parent_page_types = [settings.ION_COLLECTION_MODEL]

    content_panels = [
        MultiFieldPanel([
            FieldPanel('title'),
            FieldPanel('code'),
            FieldPanel('is_default'),
            FieldPanel('is_rtl'),
        ])
    ]


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
