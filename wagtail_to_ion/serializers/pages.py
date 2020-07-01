# Copyright © 2017 anfema GmbH. All rights reserved.
import re
import os

from datetime import datetime, date

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from bs4 import BeautifulSoup
from rest_framework import serializers
from rest_framework.fields import empty

from wagtail.core.models import Page, PageViewRestriction

from wagtail_to_ion.conf import settings
from wagtail_to_ion.utils import isoDate, get_collection_for_page
from .base import DataObject


replacements = [
    (re.compile(r'<p>\s*(<br/?>)*</p>'), ''),  # All empty paragraphs filled only with whitespace or <br> tags
    (re.compile(r'<br/?>\s*</li>'), '</li>')   # All lists that end with a <br> tag before the closing </li>
]


def get_stream_field_outlet_name(fieldname, block_type, count):
    return "{type}_{fieldname}_{count}".format(fieldname=fieldname, type=block_type, count=str(count))


def parse_correct_html(content_type):
    content = str(content_type)
    for (regex, replacement) in replacements:
        content = regex.sub(replacement, content)
    return content


def parse_data(content_type, content, fieldname, block_type=None, streamfield=False, count=None):
    content['variation'] = 'default'
    content['is_searchable'] = False

    if content_type.__class__.__name__ == 'list':
        # this content is (so far) only used by the survey_link JSONField in CandidateSpecificSurvey
        url = content_type[0]['value']
        content['type'] = 'textcontent'
        content['text'] = url
        content['is_multiline'] = False
        content['mime_type'] = 'text/plain'
        content['outlet'] = fieldname
    if content_type.__class__.__name__ in ['str', 'RichText']:
        try:
            # check if text is html
            is_html = bool(BeautifulSoup(content_type, "html.parser").find())
        except TypeError:
            is_html = True if content_type.__class__.__name__ == 'RichText' else False
        if is_html:
            content_type = parse_correct_html(content_type)
        content['type'] = 'textcontent'
        content['text'] = content_type.strip()
        content['is_multiline'] = is_html
        content['mime_type'] = 'text/html' if is_html else 'text/plain'
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
        if not content_type:
            # Do not include this outlet in the json if the field is an empty string.
            content = None
    elif content_type.__class__.__name__ == 'IonImage':
        archive = content_type.archive_rendition
        content['type'] = 'imagecontent'
        try:
            content['mime_type'] = archive.mime_type
            content['image'] = settings.BASE_URL + archive.file.url
            content['file_size'] = archive.file.file.size
            content['original_image'] = settings.BASE_URL + content_type.file.url
            content['checksum'] = archive.checksum
            content['width'] = archive.width
            content['height'] = archive.height
        except (ValueError, AttributeError) as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                content['mime_type'] = 'application/x-empty'
                content['image'] = 'IMAGE_MISSING'
                content['original_image'] = 'IMAGE_MISSING'
                content['file_size'] = 0
                content['checksum'] = 'null:'
                content['width'] = 0
                content['height'] = 0
            else:
                raise e

        content['original_mime_type'] = content_type.mime_type
        content['original_checksum'] = content_type.checksum
        content['original_width'] = content_type.width
        content['original_height'] = content_type.height
        content['original_file_size'] = content_type.get_file_size()
        content['translation_x'] = 0
        content['translation_y'] = 0
        content['scale'] = 1.0
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    # elif content_type.__class__.__name__ == 'StructValue':#TODO get class name color?
    # 	content['type'] = 'colorcontent'
    # 	content['r'] = content_type['r']
    # 	content['g'] = content_type['g']
    # 	content['b'] = content_type['b']
    # 	content['a'] = content_type['a']
    # 	if streamfield:
    # 		content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
    # 	else:
    # 		content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'datetime':
        content['type'] = 'datetimecontent'
        content['datetime'] = isoDate(content_type)
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'IonDocument':
        content['type'] = 'filecontent'
        content['mime_type'] = content_type.mime_type
        content['name'] = content_type.url
        try:
            content['file'] = settings.BASE_URL + content_type.file.url
            content['file_size'] = content_type.file.size
        except FileNotFoundError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                content['file'] = 'FILE_MISSING'
                content['file_size'] = 0
            else:
                raise e
        content['checksum'] = content_type.checksum
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'bool':
        content['type'] = 'flagcontent'
        content['is_enabled'] = content_type
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'IonMedia':
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

        if os.path.exists(content_type.file.path):
            rendition = content_type.renditions.filter(transcode_finished=True).first()
            if rendition is None:
                rendition = content_type
            media_slot['mime_type'] = content_type.mime_type
            media_slot['file'] = settings.BASE_URL + rendition.file.url
            media_slot['checksum'] = rendition.checksum
            media_slot['width'] = rendition.width if rendition.width else 0
            media_slot['height'] = rendition.height if rendition.height else 0
            media_slot['length'] = content_type.duration
            media_slot['file_size'] = rendition.file.size
            media_slot['name'] = rendition.file.name.split('/')[1]
            media_slot['original_mime_type'] = content_type.mime_type
            media_slot['original_file'] = settings.BASE_URL + content_type.file.url
            media_slot['original_checksum'] = content_type.checksum
            media_slot['original_width'] = content_type.width if content_type.width else 0
            media_slot['original_height'] = content_type.height if content_type.height else 0
            media_slot['original_length'] = content_type.duration
            media_slot['original_file_size'] = content_type.file.size
            media_slot['outlet'] = 'video'

            thumbnail_slot['mime_type'] = content_type.thumbnail_mime_type
            thumbnail_slot['image'] = settings.BASE_URL + rendition.thumbnail.url
            thumbnail_slot['checksum'] = rendition.thumbnail_checksum
            thumbnail_slot['width'] = rendition.width
            thumbnail_slot['height'] = rendition.height
            thumbnail_slot['file_size'] = rendition.thumbnail.size
            thumbnail_slot['original_mime_type'] = content_type.thumbnail_mime_type
            thumbnail_slot['original_image'] = settings.BASE_URL + content_type.thumbnail.url
            thumbnail_slot['original_checksum'] = content_type.thumbnail_checksum
            thumbnail_slot['original_width'] = content_type.width
            thumbnail_slot['original_height'] = content_type.height
            thumbnail_slot['original_file_size'] = content_type.thumbnail.size
            thumbnail_slot['translation_x'] = 0
            thumbnail_slot['translation_y'] = 0
            thumbnail_slot['scale'] = 1.0
            thumbnail_slot['outlet'] = "video_thumbnail"

        fill_contents(media_slot, media_container)
        fill_contents(thumbnail_slot, media_container)
        return media_container
    elif content_type.__class__.__name__ in ['int', 'float', 'Decimal']:
        content['type'] = 'numbercontent'
        content['value'] = content_type
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'dict':
        content['type'] = 'tablecontent'
        content['cells'] = content_type['data']
        content['first_row_header'] = content_type['first_row_is_table_header']
        content['first_col_header'] = content_type['first_col_is_header']
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'Page':
        content['type'] = 'connectioncontent'
        content['connection_string'] = '//{}/{}'.format(get_collection_for_page(content_type), content_type.slug)
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, block_type, count)
        else:
            content['outlet'] = fieldname
    elif content_type.__class__.__name__ == 'StreamValue':
        content['type'] = 'containercontent'
        if streamfield:
            content['outlet'] = get_stream_field_outlet_name(fieldname, 'container', count)
        else:
            content['outlet'] = '{}_container'.format(fieldname)

        # parse content for all wagtail streamfield block fields
        children = []
        for idx, item in enumerate(content_type):
            children.append(parse_data(item.value, {}, fieldname, item.block_type, True, idx))

        # flatten
        if len(children) == 1:
            content.update(children[0])
        elif len(children) > 1:
            return children
        else:
            return None
    elif content_type.__class__.__name__ == 'StructValue':
        result = []
        for item in content_type:
            r = parse_data(content_type[item], {}, item)
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
        return isoDate(obj.latest_revision_created_at)  # FIXME: Is this correct? Should this be last_published instead?

    def get_layout(self, obj):
        ct = ContentType.objects.get_for_id(obj.content_type_id)
        if hasattr(ct.model_class(), 'get_layout_name'):
            return ct.model_class().get_layout_name()
        else:
            return ct.model_class().__name__.lower()

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
        ct = ContentType.objects.get_for_id(obj.specific.content_type_id)
        if hasattr(ct.model_class(), 'metadata'):
            for item in ct.model_class().metadata():
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
                    if isinstance(value, date):
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

        url = self.context['request'].build_absolute_uri(url)

        return url

    def get_locale(self, obj):
        return getattr(obj, 'locale_code', getattr(obj.specific, 'locale_code', None))

    def get_contents_for_user(self, obj, wrapping, request):
        # Just returns the content vanilla as user specific content is
        # a thing for the implementer of special page types
        return obj, True, wrapping

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
            for field in obj.specific.content_panels:
                field_type = getattr(obj.specific, field.field_name)
                content = {}
                # parse content for all standard django and wagtail fields
                content = parse_data(field_type, content, field.field_name)
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
                view_restrictions__groups__in=user.groups.all()
            )
            return list(public_tree.values_list('slug', flat=True)) + list(non_public_tree.values_list('slug', flat=True))
        else:
            return list(obj.get_children().filter(live=True).values_list('slug', flat=True))

    class Meta(DynamicPageSerializer.Meta):
        fields = ('parent', 'identifier', 'collection', 'last_changed', 'archive', 'locale', 'layout', 'contents', 'children')
