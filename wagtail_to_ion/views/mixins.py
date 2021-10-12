# Copyright © 2017 anfema GmbH. All rights reserved.
from django.http import HttpResponse

from wagtail_to_ion.tar import TarWriter

from rest_framework import generics
from rest_framework.response import Response


class ListMixin(generics.ListAPIView):

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        restructured_data = {}
        for obj in serializer.data:
            if 'collection' in restructured_data:
                restructured_data['collection'].append(obj['collection'][0])
            else:
                restructured_data['collection'] = [obj['collection'][0]]
        return Response(restructured_data)
