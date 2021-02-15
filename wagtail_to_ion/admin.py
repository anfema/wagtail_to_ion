# Copyright © 2017 anfema GmbH. All rights reserved.
from django.contrib import admin

from wagtail_to_ion.models import get_ion_media_rendition_model


class AbstractIonImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)


class AbstractIonDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)


class IonMediaRenditionInlineAdmin(admin.TabularInline):
    model = get_ion_media_rendition_model()
    extra = 0


class AbstractIonMediaAdmin(admin.ModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)
    inlines = (IonMediaRenditionInlineAdmin, )


class AbstractIonCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_type', 'first_published_at', 'last_published_at')
    search_fields = ('title',)


class AbstractContentTypeDescriptionAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'description')
    search_fields = ('title',)
    list_filter = ('content_type',)
