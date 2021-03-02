# Copyright © 2017 anfema GmbH. All rights reserved.
from typing import Optional
from uuid import uuid4

from django.conf import settings
from django.utils.text import slugify

from wagtail.core.models import Page, Site


class AbstractIonPage(Page):
    ion_generate_page_title = True

    @classmethod
    def generate_page_title(cls):
        """Generate ION specific page title"""
        return '{class_name}{uuid}'.format(class_name=cls.__name__, uuid=uuid4())

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

    # overwrite Page.copy() to automatically replace the page title & slug if `ion_generate_page_title` flag is set.
    # this method is called for every child page too (on recursive copy).
    def copy(self, *args, **kwargs):
        new_update_attrs = kwargs.get('update_attrs', None) or {}

        if self.ion_generate_page_title:
            new_page_title = self.generate_page_title()
            new_update_attrs.update({
                'title': new_page_title,
                'slug': slugify(new_page_title),
            })

        # Backport: Fix crash when copying an alias page
        # TODO: remove once https://github.com/wagtail/wagtail/pull/6854 is merged & released
        new_update_attrs.update({
            'alias_of': None,
        })
        kwargs['update_attrs'] = new_update_attrs

        return super().copy(*args, **kwargs)

    #
    # django model setup
    #

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

    # overwrite Page.full_clean() to implement ION specific title & slug handling
    def full_clean(self, *args, **kwargs):
        # most ION pages have an auto-generated title (indicated by the `ion_generate_page_title` flag)
        if not self.title and self.ion_generate_page_title:
            self.title = self.generate_page_title()
            self.slug = slugify(self.title)

        super().full_clean(*args, **kwargs)


class AbstractIonCollection(AbstractIonPage):
    ion_api_object_name = 'collection'
    ion_generate_page_title = False

    parent_page_types = ['wagtailcore.Page']
    subpage_types = [settings.ION_LANGUAGE_MODEL]

    class Meta:
        abstract = True
