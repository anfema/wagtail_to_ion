# Copyright © 2017 anfema GmbH. All rights reserved.
from django.conf import settings
from django.utils.text import slugify

from wagtail.core.models import Page, Site


class AbstractIonPage(Page):

    # ion pages have no preview currently; clear preview modes
    preview_modes = ()

    # ion pages have no public url (disables "live view" buttons too)
    def get_url_parts(self, request=None):
        site = Site.find_for_request(request)
        return site, None, None  # return only the site to silence the "no site configured" warning

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
