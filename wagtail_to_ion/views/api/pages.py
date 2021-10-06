# Copyright © 2017 anfema GmbH. All rights reserved.
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from rest_framework import generics
from wagtail.core.models import Page

from wagtail_to_ion.conf import settings
from wagtail_to_ion.serializers import DynamicPageDetailSerializer, make_page_tar
from wagtail_to_ion.models import get_ion_collection_model
from wagtail_to_ion.views.mixins import TarResponseMixin, ListMixin
from wagtail_to_ion.utils import visible_tree_by_user


Collection = get_ion_collection_model()


class DynamicPageDetailView(generics.RetrieveAPIView):
    serializer_class = DynamicPageDetailSerializer
    lookup_field = 'slug'

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        kwargs['user'] = self.request.user
        return super().get_serializer(*args, **kwargs)

    def get_collection(self, slug):
        return Collection.objects.filter(live=True, slug=slug)

    def get_queryset(self):
        tree = self.get_collection(self.kwargs['collection']).first().get_children()

        collection = None
        default_collection = None
        for item in tree:
            spec = item.specific
            if spec.code == self.kwargs['locale']:
                collection = spec
                break
            if spec.is_default:
                default_collection = spec

        if collection is None:
            collection = default_collection

        if settings.GET_PAGES_BY_USER:
            return visible_tree_by_user(collection, self.request.user).filter(slug=self.kwargs['slug'])

        return collection.get_descendants().filter(
            live=True,
            slug=self.kwargs['slug']
        )


class PageArchiveView(TarResponseMixin, ListMixin):
    serializer_class = DynamicPageDetailSerializer

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return Page.objects.filter(
            slug=self.slug,
            live=True
        )

    def get(self, request, *args, **kwargs):
        self.locale = self.kwargs['locale']
        self.slug = kwargs['slug']

        pages = self.get_queryset()
        if pages.count() == 0:
            raise Http404

        page_obj = pages.first()

        tar = make_page_tar(page_obj, self.locale, request, content_serializer=self.serializer_class)
        return self.render_to_tar_response(tar)
