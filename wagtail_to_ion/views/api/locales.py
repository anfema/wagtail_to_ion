# Copyright © 2019 anfema GmbH. All rights reserved.
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from wagtail_to_ion.serializers import LocaleSerializer
from wagtail_to_ion.models import get_collection_model, Language

Collection = get_collection_model()


class LocaleListView(generics.ListAPIView):
    serializer_class = LocaleSerializer

    def get_collection(self, slug):
        return Collection.objects.filter(live=True, slug=slug)

    def get_queryset(self, collection_slug):
        user = self.request.user
        if not user.is_active:
            raise PermissionDenied()

        collection = self.get_collection(collection_slug).first()
        return Language.objects.descendant_of(collection)

    def list(self, request, collection, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset(collection))
        serializer = self.get_serializer(queryset, many=True)
        restructured_data = {}
        for item in serializer.data:
            if 'language' in restructured_data:
                restructured_data['language'].append(item['language'][0])
            else:
                restructured_data['language'] = [item['language'][0]]
        return Response(restructured_data)
