# Copyright © 2017 anfema GmbH. All rights reserved.
from django.contrib import admin

from wagtail_to_ion.models import get_ion_media_rendition_model


class ProtectInUseModelAdmin(admin.ModelAdmin):
    protect_objects_in_use: bool = True

    def get_deleted_objects(self, objs, request):
        if self.protect_objects_in_use:
            protected = []

            for obj in objs:
                usage = obj.get_usage()
                if usage:
                    protected += list(usage)
            if protected:
                return [], {}, set(), protected

        return super().get_deleted_objects(objs, request)


class AbstractIonImageAdmin(ProtectInUseModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)


class AbstractIonDocumentAdmin(ProtectInUseModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)


class IonMediaRenditionInlineAdmin(admin.TabularInline):
    model = get_ion_media_rendition_model()
    extra = 0


class AbstractIonMediaAdmin(ProtectInUseModelAdmin):
    list_display = ('title', 'collection', 'include_in_archive')
    list_filter = ('collection', 'include_in_archive')
    search_fields = ('title',)
    inlines = (IonMediaRenditionInlineAdmin, )


class AbstractIonCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_type', 'first_published_at', 'last_published_at')
    search_fields = ('title',)


class AbstractContentTypeDescriptionAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'description')
    search_fields = ('content_type__model', 'description',)
    list_filter = ('content_type',)
