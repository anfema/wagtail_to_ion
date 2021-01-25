# Copyright © 2017 anfema GmbH. All rights reserved.
from django.conf.urls import url
from wagtail_to_ion.views.api import CollectionListView, CollectionDetailView, DynamicPageDetailView, CollectionArchiveView, PageArchiveView, LocaleListView


urlpatterns = [
    url(r'^(?P<locale>[-\w\d]+)$', CollectionListView.as_view(), name='collection-list'),
    url(r'^(?P<locale>[-\w\d]+)/(?P<slug>[-\w\d]+)$', CollectionDetailView.as_view(), name='collection-detail'),
    url(r'^(?P<locale>[-\w\d]+)/(?P<collection>[-\w\d]+)/(?P<slug>[-\w\d]+)$', DynamicPageDetailView.as_view(), name='page-list'),
    url(r'^(?P<locale>[-\w\d]+)/(?P<collection>[-\w\d]+)\.tar$', CollectionArchiveView.as_view(), name='archive-collection'),
    url(r'^(?P<locale>[-\w\d]+)/(?P<collection>[-\w\d]+)/(?P<slug>[-\w\d]+)\.tar$', PageArchiveView.as_view(), name='archive-page'),
    url(r'(?P<collection>[-\w\d]+)/locales/$', LocaleListView.as_view(), name='collection-locale-list')
]
