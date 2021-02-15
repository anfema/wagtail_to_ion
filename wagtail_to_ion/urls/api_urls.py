# Copyright © 2017 anfema GmbH. All rights reserved.
from django.urls import path

from wagtail_to_ion.views.api import CollectionListView, CollectionDetailView, DynamicPageDetailView, \
    CollectionArchiveView, PageArchiveView, LocaleListView


urlpatterns = [
    path('<slug:locale>', CollectionListView.as_view(), name='collection-list'),
    path('<slug:locale>/<slug:slug>', CollectionDetailView.as_view(), name='collection-detail'),
    path('<slug:locale>/<slug:collection>/<slug:slug>', DynamicPageDetailView.as_view(), name='page-detail'),
    path('<slug:locale>/<slug:collection>.tar', CollectionArchiveView.as_view(), name='archive-collection'),
    path('<slug:locale>/<slug:collection>/<slug:slug>.tar', PageArchiveView.as_view(), name='archive-page'),
    path('<slug:collection>/locales/', LocaleListView.as_view(), name='collection-locale-list')
]
