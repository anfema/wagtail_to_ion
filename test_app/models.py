from django.db import models

from wagtail.documents.edit_handlers import DocumentChooserPanel
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtailmedia.edit_handlers import MediaChooserPanel
from wagtail_to_ion.models.abstract import AbstractIonCollection, AbstractIonPage
from wagtail_to_ion.models.content_type_description import AbstractContentTypeDescription
from wagtail_to_ion.models.file_based_models import AbstractIonDocument, AbstractIonImage, AbstractIonMedia, \
    AbstractIonMediaRendition, AbstractIonRendition
from wagtail_to_ion.models.page_models import AbstractIonLanguage


# wagtail_to_ion models
class ContentTypeDescription(AbstractContentTypeDescription):
    class Meta(AbstractContentTypeDescription.Meta):
        db_table = 'wagtail_to_ion_contenttypedescription'


class IonCollection(AbstractIonCollection):
    class Meta(AbstractIonCollection.Meta):
        db_table = 'wagtail_to_ion_collection'


class IonLanguage(AbstractIonLanguage):
    class Meta(AbstractIonLanguage.Meta):
        db_table = 'wagtail_to_ion_language'


class IonDocument(AbstractIonDocument):
    class Meta(AbstractIonDocument.Meta):
        db_table = 'wagtail_to_ion_iondocument'


class IonImage(AbstractIonImage):
    class Meta(AbstractIonImage.Meta):
        db_table = 'wagtail_to_ion_ionimage'


class IonRendition(AbstractIonRendition):
    class Meta(AbstractIonRendition.Meta):
        db_table = 'wagtail_to_ion_ionrendition'


class IonMedia(AbstractIonMedia):
    class Meta(AbstractIonMedia.Meta):
        db_table = 'wagtail_to_ion_ionmedia'


class IonMediaRendition(AbstractIonMediaRendition):
    class Meta(AbstractIonMediaRendition.Meta):
        db_table = 'wagtail_to_ion_ionmediarendition'


# project specific models
class TestPage(AbstractIonPage):
    document_field = models.ForeignKey(IonDocument, blank=True, null=True, on_delete=models.SET_NULL)
    image_field = models.ForeignKey(IonImage, blank=True, null=True, on_delete=models.SET_NULL)
    media_field = models.ForeignKey(IonMedia, blank=True, null=True, on_delete=models.SET_NULL)

    content_panels = AbstractIonPage.content_panels + [
        DocumentChooserPanel('document_field'),
        ImageChooserPanel('image_field'),
        MediaChooserPanel('media_field'),
    ]

    parent_page_types = [
        'IonLanguage',
        'TestPage',
    ]
