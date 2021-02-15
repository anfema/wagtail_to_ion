from django.contrib import admin

from wagtail_to_ion.admin import AbstractIonImageAdmin, AbstractIonDocumentAdmin, AbstractIonMediaAdmin, \
    AbstractIonCollectionAdmin, AbstractContentTypeDescriptionAdmin
from .models import IonImage, IonDocument, IonMedia, IonCollection, ContentTypeDescription


@admin.register(IonImage)
class IonImageAdmin(AbstractIonImageAdmin):
    pass


@admin.register(IonDocument)
class IonDocumentAdmin(AbstractIonDocumentAdmin):
    pass


@admin.register(IonMedia)
class IonMediaAdmin(AbstractIonMediaAdmin):
    pass


@admin.register(IonCollection)
class IonCollectionAdmin(AbstractIonCollectionAdmin):
    pass


@admin.register(ContentTypeDescription)
class ContentTypeDescriptionAdmin(AbstractContentTypeDescriptionAdmin):
    pass
