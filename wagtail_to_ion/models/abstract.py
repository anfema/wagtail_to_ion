# Copyright © 2017 anfema GmbH. All rights reserved.
from django.utils.text import slugify

from wagtail.core.models import Page, PageBase
from wagtail_to_ion.utils import get_model_mixins


class AbstractCollection(Page):

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.slug.startswith('to-be-filled'):
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    parent_page_types = ['wagtailcore.Page']
    subpage_types = ['wagtail_to_ion.Language']

    class Meta:
        abstract = True
