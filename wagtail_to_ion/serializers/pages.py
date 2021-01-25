# Copyright © 2017 anfema GmbH. All rights reserved.
import os
import re
from typing import Iterable, Tuple

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse

from bs4 import BeautifulSoup
from rest_framework import serializers
from rest_framework.fields import empty

from wagtail.core.models import Page, PageViewRestriction

from wagtail_to_ion.conf import settings
from wagtail_to_ion.utils import isoDate
from .base import DataObject


replacements = [
    (re.compile(r'<p>\s*(<br/?>)*</p>'), ''),  # All empty paragraphs filled only with whitespace or <br> tags
    (re.compile(r'<br/?>\s*</li>'), '</li>')   # All lists that end with a <br> tag before the closing </li>
]


def get_collection(page):
    if page.get_parent().specific.__class__.__name__ == settings.ION_COLLECTION_MODEL.split('.')[-1]:
        return page.get_parent().slug
    else:
        return get_collection(page.get_parent())


def get_stream_field_outlet_name(fieldname, block_type, count):
    return "{type}_{fieldname}_{count}".format(fieldname=fieldname, type=block_type, count=str(count))


def parse_correct_html(content_type):
    content = str(content_type)
    for (regex, replacement) in replacements:
        content = regex.sub(replacement, content)
    return content


def get_wagtail_panels_and_extra_fields(obj) -> Iterable[Tuple[str, str, models.Model]]:
    """
    get all panels and other fields to include

    :returns: tuple of ``alias``, ``attribute_name``, ``object``
    """
    if hasattr(obj.specific.__class__, 'extra_fields'):
        for item in obj.specific.__class__.extra_fields():
            if isinstance(item, str):
                field_path = item
                alias = item
            elif isinstance(item, (tuple, list)):
                alias, field_path = item
            else:
                raise NotImplementedError()

            if '.' not in field_path:
                yield alias, item, obj.specific
            else:
                if len(field_path.split('.')) > 2:
                    raise NotImplementedError()
                relation, name = field_path.split('.')
                value = getattr(obj.specific, relation)
                yield alias, name, value

    for field in obj.specific.content_panels:
        if hasattr(field, 'field_name'):
            yield field.field_name, field.field_name, obj.specific


def parse_data(content_data, content, fieldname, block_type=None, streamfield=False, count=None):
    content['variation'] = 'default'
    content['is_searchable'] = False

    if content_data.__class__.__name__ == 'list':
        # this content is (so far) only used by the survey_link JSONField in CandidateSpecificSurvey
        url = content_data[0]['value']
        content['type'] = 'textcontent'
        content['text'] = url
        content['is_multiline'] = False
        content['mime_type'] = 'text/plain'
        content['outlet'] = fieldname
    if content_data.__class__.__name__ in ['str', 'RichText']:
        try:
            # check if text is html
            is_html = bool(BeautifulSoup(content_data, "html.parser").find())
        except TypeError:
            is_html = content_data.__class__.__name__ == 'RichText'
        if is_html:
            content_data = parse_correct_html(content_data)
        content['type'] = 'textcontent'
        content['text'] = content_data.strip()
        content['is_multiline'] = is_html
        content['mime_type'] = 'text/html' if is_html else 'text/plain'
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
        if not content_data:
            # Do not include this outlet in the json if the field is an empty string.
            content = None
    elif content_data.__class__.__name__ == 'IonImage':
        archive = content_data.archive_rendition
        content['type'] = 'imagecontent'
        content['mime_type'] = archive.mime_type
        try:
            content['image'] = settings.BASE_URL + archive.file.url
            content['file_size'] = archive.file.file.size
            content['original_image'] = settings.BASE_URL + content_data.file.url
        except ValueError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                content['image'] = 'IMAGE_MISSING'
                content['original_image'] = 'IMAGE_MISSING'
                content['file_size'] = 0
            else:
                raise e
        content['checksum'] = archive.checksum
        content['width'] = archive.width
        content['height'] = archive.height
        content['original_mime_type'] = content_data.mime_type
        content['original_checksum'] = content_data.checksum
        content['original_width'] = content_data.width
        content['original_height'] = content_data.height
        content['original_file_size'] = content_data.get_file_size()
        content['translation_x'] = 0
        content['translation_y'] = 0
        content['scale'] = 1.0
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    # elif content_data.__class__.__name__ == 'StructValue':#TODO get class name color?
    # 	content['type'] = 'colorcontent'
    # 	content['r'] = content_data['r']
    # 	content['g'] = content_data['g']
    # 	content['b'] = content_data['b']
    # 	content['a'] = content_data['a']
    # 	if streamfield:
    # 		content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
    # 	else:
    # 		content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'datetime':
        content['type'] = 'datetimecontent'
        content['datetime'] = isoDate(content_data)
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'IonDocument':
        content['type'] = 'filecontent'
        content['mime_type'] = content_data.mime_type
        content['name'] = content_data.url
        try:
            content['file'] = settings.BASE_URL + content_data.file.url
            content['file_size'] = content_data.file.size
        except FileNotFoundError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                content['file'] = 'FILE_MISSING'
                content['file_size'] = 0
            else:
                raise e
        content['checksum'] = content_data.checksum
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'bool':
        content['type'] = 'flagcontent'
        content['is_enabled'] = content_data
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'IonMedia':
        media_container = {}
        media_container['variation'] = 'default'
        media_container['is_searchable'] = False
        media_container['type'] = 'containercontent'
        if streamfield:
            media_container['outlet'] = get_stream_field_outlet_name(fieldname, 'mediacontainer', count)
        else:
            media_container['outlet'] = 'mediacontainer_{}'.format(fieldname)
        media_container['children'] = []

        media_slot = {}
        thumbnail_slot = {}

        media_slot['type'] = 'mediacontent'
        thumbnail_slot['type'] = 'imagecontent'

        if os.path.exists(content_data.file.path):
            rendition = content_data.renditions.filter(transcode_finished=True).first()
            if rendition is None:
                rendition = content_data
            media_slot['mime_type'] = content_data.mime_type
            media_slot['file'] = settings.BASE_URL + rendition.file.url
            media_slot['checksum'] = rendition.checksum
            media_slot['width'] = rendition.width if rendition.width else 0
            media_slot['height'] = rendition.height if rendition.height else 0
            media_slot['length'] = content_data.duration
            media_slot['file_size'] = rendition.file.size
            media_slot['name'] = rendition.file.name.split('/')[1]
            media_slot['original_mime_type'] = content_data.mime_type
            media_slot['original_file'] = settings.BASE_URL + content_data.file.url
            media_slot['original_checksum'] = content_data.checksum
            media_slot['original_width'] = content_data.width if content_data.width else 0
            media_slot['original_height'] = content_data.height if content_data.height else 0
            media_slot['original_length'] = content_data.duration
            media_slot['original_file_size'] = content_data.file.size
            media_slot['outlet'] = 'video'

            thumbnail_slot['mime_type'] = content_data.thumbnail_mime_type
            thumbnail_slot['image'] = settings.BASE_URL + rendition.thumbnail.url
            thumbnail_slot['checksum'] = rendition.thumbnail_checksum
            thumbnail_slot['width'] = rendition.width
            thumbnail_slot['height'] = rendition.height
            thumbnail_slot['file_size'] = rendition.thumbnail.size
            thumbnail_slot['original_mime_type'] = content_data.thumbnail_mime_type
            thumbnail_slot['original_image'] = settings.BASE_URL + content_data.thumbnail.url
            thumbnail_slot['original_checksum'] = content_data.thumbnail_checksum
            thumbnail_slot['original_width'] = content_data.width
            thumbnail_slot['original_height'] = content_data.height
            thumbnail_slot['original_file_size'] = content_data.thumbnail.size
            thumbnail_slot['translation_x'] = 0
            thumbnail_slot['translation_y'] = 0
            thumbnail_slot['scale'] = 1.0
            thumbnail_slot['outlet'] = "video_thumbnail"

        fill_contents(media_slot, media_container)
        fill_contents(thumbnail_slot, media_container)
        return media_container
    elif content_data.__class__.__name__ in ['int', 'float', 'Decimal']:
        content['type'] = 'numbercontent'
        content['value'] = content_data
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'dict':
        content['type'] = 'tablecontent'
        content['cells'] = content_data['data']
        content['first_row_header'] = content_data['first_row_is_table_header']
        content['first_col_header'] = content_data['first_col_is_header']
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'Page':
        content['type'] = 'connectioncontent'
        content['connection_string'] = '//{}/{}'.format(get_collection(content_data), content_data.slug)
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_data.__class__.__name__ == 'StreamValue':
        content['type'] = 'containercontent'
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, 'container', count)
        else:
            content['outlet'] = '{}_container'.format(fieldname)

        # parse content for all wagtail streamfield block fields
        children = []
        for idx, item in enumerate(content_data):
            children.append(parse_data(item.value, {}, fieldname, item.block_type, True, idx))

        # flatten
        if len(children) == 1:
            content.update(children[0])
        elif len(children) > 1:
            return children
        else:
            return None
    elif content_data.__class__.__name__ == 'StructValue':
        result = []
        for item in content_data:
            r = parse_data(content_data[item], {}, item)
            if r is None:
                continue
            r['variation'] = 'default'
            r['is_searchable'] = False
            result.append(r)

        content['type'] = 'containercontent'
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, 'container', count)
        else:
            content['outlet'] = '{}_container_{}'.format(fieldname, count)
        content['children'] = result
    return content


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
        return isoDate(obj.latest_revision_created_at)

    def get_layout(self, obj):
        ct = ContentType.objects.get_for_id(obj.content_type_id)

        try:
            api_version = int(self.context['request'].META['HTTP_API_VERSION']) or None
        except (KeyError, ValueError):
            api_version = None

        return ct.model_class().get_layout_name(api_version)

    def get_parent(self, obj):
        if obj.depth <= 4:
            return None
        return obj.get_parent().slug

    def get_meta(self, obj):
        return {}

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
        return get_collection(obj)

    def get_archive(self, obj):
        locale = self.context['request'].resolver_match.kwargs['locale']
        url = reverse('v1:archive-page', kwargs={
            'locale': locale,
            'collection': get_collection(obj),
            'slug': obj.slug,
        })

        url = self.context['request'].build_absolute_uri(url)

        return url

    def get_locale(self, obj):
        return getattr(obj, 'locale_code', getattr(obj.specific, 'locale_code', None))

    def get_contents_for_user(self, obj, wrapping, request):
        # Just returns the content vanilla as user specific content is
        # a thing for the implementer of special page types
        return obj, wrapping, request

    def get_contents(self, obj):
        request = self.context['request']
        result = []
        wrapping = {}
        wrapping['type'] = 'containercontent'
        wrapping['variation'] = 'default'
        wrapping['outlet'] = 'container_0'
        wrapping['children'] = []
        page_filled = True  # TODO: Better name
        if settings.GET_PAGES_BY_USER:
            obj, page_filled, wrapping = self.get_contents_for_user(obj, wrapping, request)
        if page_filled:
            for alias, field_name, instance in get_wagtail_panels_and_extra_fields(obj):
                field_type = getattr(instance, field_name)
                content = {}
                # parse content for all standard django and wagtail fields
                content = parse_data(field_type, content, alias)
                if content:
                    if isinstance(content, list):
                        wrapping['children'].extend(content)
                    else:
                        # content contains at least ``variation`` and ``is_searchable``,
                        # do not add this to children if there are only those two in there
                        # and no ``type``
                        if 'type' in content:
                            wrapping['children'].append(content)

        result.append(wrapping)
        return result

    def get_children(self, obj):
        if settings.GET_PAGES_BY_USER:
            user = self.context['request'].user
            tree = obj.get_children().filter(live=True)
            public_tree = tree.public()
            non_public_tree = tree.not_public().filter(
                view_restrictions__restriction_type=PageViewRestriction.GROUPS,
                view_restrictions__groups__in=user.groups
            )
            return public_tree.values_list('slug', flat=True) + non_public_tree.values_list('slug', flat=True)
        else:
            return list(obj.get_children().filter(live=True).values_list('slug', flat=True))

    class Meta(DynamicPageSerializer.Meta):
        fields = ('parent', 'identifier', 'collection', 'last_changed', 'archive', 'locale', 'layout', 'contents', 'children')
