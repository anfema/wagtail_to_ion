# Copyright © 2017 anfema GmbH. All rights reserved.
from datetime import datetime

from django.http import Http404, HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.exceptions import PermissionDenied
from rest_framework import generics

from wagtail.core.models import Page, PageViewRestriction

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models import get_collection_model
from wagtail_to_ion.serializers import CollectionSerializer, CollectionDetailSerializer, DynamicPageDetailSerializer ,make_tar
from wagtail_to_ion.views.mixins import ListMixin, TarResponseMixin
from wagtail_to_ion.utils import visible_tree_by_user, visible_collections_by_user


Collection = get_collection_model()


class CollectionListView(ListMixin):
    serializer_class = CollectionSerializer

    def get_queryset(self):
        user = self.request.user
        if settings.GET_PAGES_BY_USER:
            return visible_collections_by_user(user)
        else:
            return Collection.objects.filter(live=True)


class CollectionDetailView(generics.RetrieveAPIView):
    serializer_class = CollectionDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        user = self.request.user
        if settings.GET_PAGES_BY_USER:
            return visible_collections_by_user(user)
        else:
            return Collection.objects.filter(live=True)


class CollectionArchiveView(TarResponseMixin, ListMixin):
    content_serializer_class = DynamicPageDetailSerializer

    def get_queryset(self):
        try:
            languages = self.collection.get_children().filter(live=True)

            collection = None
            default_collection = None
            for language in languages:
                spec = language.specific
                if spec.is_default:
                    default_collection = spec
                if spec.code == self.locale:
                    collection = spec
            if collection is None:
                collection = default_collection

            if settings.GET_PAGES_BY_USER:
                user = self.request.user
                pages = visible_tree_by_user(collection, user)
            else:
                pages = collection.get_descendants().filter(live=True)
            return pages
        except ObjectDoesNotExist:
            return None

    def get_collection(self, slug):
        return Collection.objects.filter(live=True, slug=slug)

    def get(self, request, locale, collection, *args, **kwargs):
        self.collection = self.get_collection(collection).first()
        self.locale = locale

        pages = self.get_queryset()
        updated_pages = list(pages)

        if not pages or len(pages) == 0:
            raise Http404

        if 'lastUpdated' in request.GET:
            last_updated = datetime.strptime(request.GET['lastUpdated'], '%Y-%m-%dT%H:%M:%SZ')
            updated_pages = Page.objects.filter(
                last_published_at__gt=last_updated,
                id__in=pages.values_list("id", flat=True)
            )
            if updated_pages.count() == 0:
                return HttpResponse(status=304)  # not modified
            updated_pages = list(updated_pages)

        tar = make_tar(list(pages), updated_pages, self.locale, request, content_serializer=self.content_serializer_class)
        return self.render_to_tar_response(tar)
