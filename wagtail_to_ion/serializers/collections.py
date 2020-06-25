# Copyright © 2017 anfema GmbH. All rights reserved.
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from wagtail_to_ion.utils import visible_tree_by_user
from wagtail_to_ion.models import get_collection_model
from wagtail_to_ion.conf import settings

from .pages import DynamicPageSerializer, DataObject


class CollectionSerializer(DataObject):
    identifier = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    default_locale = serializers.SerializerMethodField()
    fts_db = serializers.SerializerMethodField()
    archive = serializers.SerializerMethodField()

    def get_identifier(self, obj):
        return obj.slug

    def get_name(self, obj):
        return obj.title

    def get_default_locale(self, obj):
        locales = obj.get_children().filter(live=True)
        for locale in locales:
            spec = locale.specific
            if spec.is_default:
                return spec.code

    def get_fts_db(self, obj):
        return 'NULL'

    def get_archive(self, obj):
        locale = self.context['request'].resolver_match.kwargs['locale']
        url = reverse('v1:archive-collection', kwargs={
            'locale': locale,
            'collection': obj.slug,
        })
        url = self.context['request'].build_absolute_uri(url)
        return url

    class Meta:
        model = get_collection_model()
        fields = ('identifier', 'name', 'default_locale', 'fts_db', 'archive')


class CollectionDetailSerializer(CollectionSerializer):
    pages = serializers.SerializerMethodField()
    
    content_serializer_class = DynamicPageSerializer

    def get_pages(self, obj):
        locale = self.context['request'].resolver_match.kwargs['locale']
        user = self.context['request'].user
        try:
            localized_tree = obj.get_children().filter(live=True)
            # find locale
            locale_item = None
            default_locale = None
            for item in localized_tree:
                spec = item.specific
                if spec.code == locale:
                    locale_item = spec
                if spec.is_default:
                    default_locale = spec
            if locale_item is None:
                locale_item = default_locale
            if settings.GET_PAGES_BY_USER:
                pages = visible_tree_by_user(locale_item, user)
            else:
                pages = locale_item.get_descendants().filter(live=True)
        except ObjectDoesNotExist:
            pages = {}

        serializer = self.content_serializer_class(instance=pages, many=True, user=user)
        return serializer.data

    class Meta(CollectionSerializer.Meta):
        fields = CollectionSerializer.Meta.fields + ('pages',)
