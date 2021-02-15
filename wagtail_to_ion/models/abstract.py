# Copyright © 2017 anfema GmbH. All rights reserved.
from typing import Optional

from django.conf import settings
from django.utils.text import slugify

from wagtail.core.models import Page, Site


class AbstractIonPage(Page):

    @classmethod
    def ion_metadata(cls):
        """
        Returns additional metadata for the page.

        See `DynamicPageSerializer.get_meta()`
        """
        return ()

    @classmethod
    def ion_extra_fields(cls):
        """
        Add extra fields (not part of `content_panels`) for serialization with ION.

        Returns an iterable of tuples containing two strings:
            - the outlet name
            - the path to the extra field

        Example: to add the value of `self.some_related_model.some_field` use:
            return (
                ('outlet_name', 'some_related_model.some_field'),
            )
        """
        return ()

    @classmethod
    def get_layout_name(cls, api_version: Optional[int] = None):  # TODO: rename to `get_ion_layout_name`?
        return cls.__name__.lower()  # TODO: use `cls._meta.model_name`?

    #
    # wagtail attributes/methods
    #

    # ion pages have no preview currently; clear wagtail preview modes
    preview_modes = ()

    # ion pages have no public url (disables wagtail "live view" buttons too)
    def get_url_parts(self, request=None):
        site = Site.find_for_request(request)
        return site, None, None  # return only the site to silence the "no site configured" warning

    #
    # django model setup
    #

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.slug.startswith('to-be-filled'):
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class AbstractIonCollection(AbstractIonPage):
    ion_api_object_name = 'collection'

    parent_page_types = ['wagtailcore.Page']
    subpage_types = [settings.ION_LANGUAGE_MODEL]

    class Meta:
        abstract = True
