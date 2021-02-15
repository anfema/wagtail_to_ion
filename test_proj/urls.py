"""test_proj URL Configuration
The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path


urlpatterns = [
    path('admin/', admin.site.urls),
    # wagtail_to_ion
    path('cms/', include('wagtail_to_ion.urls.wagtail_override_urls')),  # overridden urls by the api adapter
    path('api/v1/', include(('wagtail_to_ion.urls.api_urls', 'wagtail_to_ion'), namespace='v1')),
    # wagtail
    path('cms/', include('wagtail.admin.urls')),
    path('documents/', include('wagtail.documents.urls')),
    # re_path(r'', include('wagtail.core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
