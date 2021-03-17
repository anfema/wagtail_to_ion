# Copyright © 2017 anfema GmbH. All rights reserved.
from datetime import datetime, date
from typing import Iterable, Tuple
from wagtail_to_ion.serializers.ion.container import IonContainerSerializer

from django.db import models
from django.urls import reverse

from rest_framework import serializers
from rest_framework.fields import empty

from wagtail.core.models import Page, PageViewRestriction

from wagtail_to_ion.conf import settings
from wagtail_to_ion.utils import isoDate, get_collection_for_page

from .base import DataObject


def get_wagtail_panels_and_extra_fields(obj) -> Iterable[Tuple[str, str, models.Model]]:
    """
    Get all page panels and other fields from `page.ion_extra_fields` to include.

    :returns: tuple of ``outlet_name``, ``attribute_name``, ``object``
    """
    if hasattr(obj.specific_class, 'ion_extra_fields'):
        for item in obj.specific_class.ion_extra_fields():
            if isinstance(item, str):
                field_path = item
                outlet_name = item
            elif isinstance(item, (tuple, list)):
                outlet_name, field_path = item
            else:
                raise NotImplementedError()

            if '.' not in field_path:
                yield outlet_name, field_path, obj.specific
            else:
                if len(field_path.split('.')) > 2:
                    raise NotImplementedError()
                relation, field_name = field_path.split('.')
                related_obj = getattr(obj.specific, relation)
                yield outlet_name, field_name, related_obj

    for field in obj.specific.content_panels:
        if hasattr(field, 'field_name'):
            yield field.field_name, field.field_name, obj.specific


class DynamicPageSerializer(serializers.ModelSerializer):
    identifier = serializers.SerializerMethodField()
    last_changed = serializers.SerializerMethodField()
    layout = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()
    meta = serializers.SerializerMethodField()

    def __init__(self, instance=None, data=empty, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(instance, data, **kwargs)

    def get_identifier(self, obj):
        return obj.slug

    def get_last_changed(self, obj):
        return isoDate(obj.last_published_at)

    def get_layout(self, obj):
        try:
            api_version = int(self.context['request'].META['HTTP_API_VERSION']) or None
        except (KeyError, ValueError):
            api_version = None

        return obj.specific_class.get_layout_name(api_version)

    def get_parent(self, obj):
        if obj.depth <= 4:
            return None
        return obj.get_parent().slug

    def get_meta(self, obj):
        """
        This function generated meta-data from a tuple that is returned by a class-function
        named `metadata`. The tuple returned is a list of strings usually to define which fields
        should be serialized into the meta structure.

        If the list contains tuples they are parsed as following:
        - tuple of 2 strings: first is the name of the field in meta, second is the real
          model field name.
        - tuple of a string and a callable: the callable is called with the field name and the
          specific object to generate the value for the meta struct
        """
        result = {}
        if hasattr(obj.specific_class, 'ion_metadata'):
            for item in obj.specific_class.ion_metadata():
                if isinstance(item, tuple) or isinstance(item, list):
                    field_name = item[0]
                    generator = item[1]
                    if callable(generator):
                        value = generator(field_name, obj.specific)
                    else:
                        value = getattr(obj.specific, generator, None)
                else:
                    field_name = item
                    value = getattr(obj.specific, item, None)
                if value is not None:
                    if not isinstance(value, datetime) and isinstance(value, date):
                        value = datetime(value.year, month=value.month, day=value.day)
                    if isinstance(value, datetime):
                        value = isoDate(value)
                    result[field_name] = value
        return result

    class Meta:
        model = Page
        fields = ('identifier', 'parent', 'last_changed', 'layout', 'meta')


def fill_contents(content, wrapping):
    content['variation'] = 'default'
    content['is_searchable'] = False
    wrapping['children'].append(content)


class DynamicPageDetailSerializer(DynamicPageSerializer, DataObject):
    collection = serializers.SerializerMethodField()
    archive = serializers.SerializerMethodField()
    locale = serializers.SerializerMethodField()
    contents = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    def get_collection(self, obj):
        return get_collection_for_page(obj)

    def get_archive(self, obj):
        locale = self.context['request'].resolver_match.kwargs['locale']
        url = reverse('v1:archive-page', kwargs={
            'locale': locale,
            'collection': self.get_collection(obj),
            'slug': obj.slug,
        })

        url = self.context['request'].build_absolute_uri(url) + '?variation={}'.format(
            self.context['request'].GET.get(
                'variation', 'default'
            )
        )

        return url

    def get_locale(self, obj):
        return getattr(obj, 'locale_code', getattr(obj.specific, 'locale_code', None))

    def get_contents_for_user(self, obj, request):
        # Just returns the content vanilla as user specific content is
        # a thing for the implementer of special page types
        return obj, True

    def remap_outlet_name(self, outlet_path):
        # just returns the outlet name unaltered as remapping
        # usually happens in specialized serializers
        return outlet_path[-1]

    def remap_outlet_names_recursive(self, struct, path):
        if 'outlet' not in struct:
            return
        struct['outlet'] = self.remap_outlet_name(path + [struct['outlet']])

        if 'children' not in struct:
            return
        for item in struct['children']:
            self.remap_outlet_names_recursive(item, path + [struct['outlet']])

    def get_contents(self, obj):
        request = self.context['request']

        # Create a top-level container
        container = IonContainerSerializer('container_0')

        # check if we want to render this page
        render_page = True
        if settings.GET_PAGES_BY_USER:
            # Special case to render user specific pages, the function may return a new ``obj`` to render
            obj, render_page = self.get_contents_for_user(obj, request)

        # if we want to render, add all outlets to the container
        if render_page:
            for outlet_name, field_name, instance in get_wagtail_panels_and_extra_fields(obj):
                field_data = getattr(instance, field_name)
                if field_data is None:  # If field_data is None, the serializer can not do anything, skip this
                    continue
                container.add_child(outlet_name, field_data) # This will auto-detect the serializers to use

        # serialize into a ``dict`` with simple data types
        data = container.serialize()

        # optionally remap outlet names if needed (e.g. outlet should be called like a reserved word in python)
        self.remap_outlet_names_recursive(data, [])

        return [data]

    def get_children(self, obj):
        if settings.GET_PAGES_BY_USER:
            user = self.context['request'].user
            tree = obj.get_children().filter(live=True)
            public_tree = tree.public()
            non_public_tree = tree.not_public().filter(
                view_restrictions__restriction_type=PageViewRestriction.GROUPS,
                view_restrictions__groups__in=user.groups.all()
            )
            return list(public_tree.values_list('slug', flat=True)) + list(non_public_tree.values_list('slug', flat=True))
        else:
            return list(obj.get_children().filter(live=True).values_list('slug', flat=True))

    class Meta(DynamicPageSerializer.Meta):
        fields = ('parent', 'identifier', 'collection', 'last_changed', 'archive', 'locale', 'layout', 'contents', 'children')
