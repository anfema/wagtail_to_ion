from django.db import models

from wagtail.core.fields import StreamField
from wagtail.core import blocks
from wagtail.admin.edit_handlers import StreamFieldPanel
from wagtail.core.blocks import ListBlock

from wagtail.documents.edit_handlers import DocumentChooserPanel
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtail.images.blocks import ImageChooserBlock
from wagtailmedia.edit_handlers import MediaChooserPanel
from wagtail_to_ion.models.abstract import AbstractIonCollection, AbstractIonPage
from wagtail_to_ion.models.content_type_description import AbstractContentTypeDescription
from wagtail_to_ion.models.file_based_models import AbstractIonDocument, AbstractIonImage, AbstractIonMedia, \
    AbstractIonMediaRendition, AbstractIonRendition
from wagtail_to_ion.models.page_models import AbstractIonLanguage

# wagtail_to_ion models
class ContentTypeDescription(AbstractContentTypeDescription):
    pass


class IonCollection(AbstractIonCollection):
    pass


class IonLanguage(AbstractIonLanguage):
    pass


class IonDocument(AbstractIonDocument):
    pass


class IonImage(AbstractIonImage):
    pass


class IonRendition(AbstractIonRendition):
    pass


class IonMedia(AbstractIonMedia):
    pass


class IonMediaRendition(AbstractIonMediaRendition):
    pass


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


class PersonBlock(blocks.StructBlock):
    first_name = blocks.CharBlock()
    surname = blocks.CharBlock()
    photo = ImageChooserBlock(required=False)
    biography = blocks.RichTextBlock()

    class Meta:
        icon = 'user'


class StreamFieldPage(AbstractIonPage):
    stream = StreamField([
        ('heading', blocks.CharBlock(form_classname="full title")),
        ('paragraph', blocks.RichTextBlock()),
        ('image', ImageChooserBlock()),
        ('person', PersonBlock()),
        ('group', ListBlock(PersonBlock()))
    ])

    content_panels = AbstractIonPage.content_panels + [
        StreamFieldPanel('stream'),
    ]


class ExpandableBlock(blocks.StructBlock):
    header = blocks.CharBlock(max_length=512)
    content = blocks.StreamBlock([
        ('richtext', blocks.RichTextBlock()),
        ('image', ImageChooserBlock()),
    ])


class RecursiveStreamFieldPage(AbstractIonPage):
    body = StreamField([
        ('expandable_block', ExpandableBlock()),
    ])

    content_panels = [
        StreamFieldPanel('body'),
    ]
