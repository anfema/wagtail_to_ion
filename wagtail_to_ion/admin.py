# Copyright © 2017 anfema GmbH. All rights reserved.
from django.contrib import admin
from .models import IonImage, IonMedia, get_collection_model, ContentTypeDescription, IonMediaRendition, IonDocument


@admin.register(IonImage)
class IonImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)


@admin.register(IonDocument)
class IonDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)


class IonMediaRenditionInlineAdmin(admin.TabularInline):
    model = IonMediaRendition
    extra = 0


@admin.register(IonMedia)
class IonMediaAdmin(admin.ModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)
    inlines = (IonMediaRenditionInlineAdmin, )


@admin.register(get_collection_model())
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_type', 'first_published_at', 'last_published_at')
    search_fields = ('title',)


@admin.register(ContentTypeDescription)
class ContentTypeDescriptionAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'description')
    search_fields = ('title',)
    list_filter = ('content_type',)
