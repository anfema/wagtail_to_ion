# Copyright © 2017 anfema GmbH. All rights reserved.
from __future__ import annotations

from typing import Optional

from django.db import models, transaction
from django.db.models import ProtectedError
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.documents.models import AbstractDocument
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import AbstractImage, AbstractRendition, SourceImageIOError, get_upload_to, \
    get_rendition_upload_to
from wagtailmedia.models import AbstractMedia

from wagtail_to_ion.blocks import IonMediaBlock
from wagtail_to_ion.conf import settings
from wagtail_to_ion.fields.files import IonFileField, IonImageField
from wagtail_to_ion.models import get_ion_media_rendition_model
from wagtail_to_ion.tasks import generate_media_rendition, get_audio_metadata, generate_media_thumbnail


FILE_META_FIELDS = {
    'checksum_field': 'checksum',
    'mime_type_field': 'mime_type',
    'file_size_field': 'file_size',
    'last_modified_field': 'file_last_modified',
}

THUMBNAIL_META_FIELDS = {
    'checksum_field': 'thumbnail_checksum',
    'mime_type_field': 'thumbnail_mime_type',
    'file_size_field': 'thumbnail_file_size',
    'last_modified_field': 'thumbnail_file_last_modified',
}


class IonFileContainerInterface:
    pass


class AbstractIonDocument(IonFileContainerInterface, AbstractDocument):
    file = IonFileField(
        upload_to='documents',
        verbose_name=_('file'),
        **FILE_META_FIELDS,
    )
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
    file_last_modified = models.DateTimeField(null=True, editable=False)
    include_in_archive = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_form_fields = (
        'title',
        'file',
        'collection',
        'tags',
        'include_in_archive',
    )
    check_usage_block_types = (DocumentChooserBlock,)

    class Meta:
        abstract = True

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=self.check_usage_block_types))


class AbstractIonImage(IonFileContainerInterface, AbstractImage):
    file = IonImageField(
        upload_to=get_upload_to,
        verbose_name=_('file'),
        width_field='width',
        height_field='height',
        **FILE_META_FIELDS,
    )
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
    file_last_modified = models.DateTimeField(null=True, editable=False)
    rendition_type = models.CharField(max_length=128, default='jpegquality-70')
    include_in_archive = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_form_fields = (
        'title',
        'file',
        'collection',
        'tags',
        'focal_point_x',
        'focal_point_y',
        'focal_point_width',
        'focal_point_height',
        'include_in_archive',
    )
    check_usage_block_types = (ImageChooserBlock,)

    class Meta:
        abstract = True

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=self.check_usage_block_types))

    @property
    def archive_rendition(self):
        try:
            result = self.get_rendition(self.rendition_type)
        except (FileNotFoundError, SourceImageIOError) as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                rendition = self.get_rendition_model()
                result = rendition()
            else:
                raise e

        return result


class AbstractIonRendition(IonFileContainerInterface, AbstractRendition):
    image = models.ForeignKey(settings.WAGTAILIMAGES_IMAGE_MODEL, related_name='renditions', on_delete=models.CASCADE)
    file = IonImageField(
        upload_to=get_rendition_upload_to,
        width_field='width',
        height_field='height',
        **FILE_META_FIELDS,
    )
    checksum = models.CharField(max_length=255, null=True)
    mime_type = models.CharField(max_length=128, null=True)
    file_size = models.PositiveIntegerField(null=True, editable=False)
    file_last_modified = models.DateTimeField(null=True, editable=False)

    class Meta:
        abstract = True
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class AbstractIonMedia(IonFileContainerInterface, AbstractMedia):
    file = IonFileField(
        upload_to='media',
        verbose_name=_('file'),
        **FILE_META_FIELDS,
    )
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
    thumbnail = IonImageField(
        upload_to='media_thumbnails',
        verbose_name=_('thumbnail'),
        null=True,
        blank=True,
        **THUMBNAIL_META_FIELDS,
    )
    duration = models.PositiveIntegerField(
        verbose_name=_('duration'),
        null=True,
        blank=True,
        help_text=_('Duration in seconds')
    )
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('width'))
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('height'))
    file_size = models.PositiveIntegerField(null=True, editable=False)
    file_last_modified = models.DateTimeField(null=True, editable=False)

    thumbnail_checksum = models.CharField(blank=True, max_length=255)
    thumbnail_mime_type = models.CharField(blank=True, max_length=128)
    thumbnail_file_size = models.PositiveIntegerField(null=True, editable=False)
    thumbnail_file_last_modified = models.DateTimeField(null=True, editable=False)
    include_in_archive = models.BooleanField(
        default=False,
        help_text="If enabled, the file will be included in the ION archive "
        "tar file and can increase the archive's size significantly."
    )
    updated_at = models.DateTimeField(auto_now=True)
    admin_form_fields = (
        'title',
        'file',
        'collection',
        'tags',
    )
    check_usage_block_types = (IonMediaBlock,)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.file.has_changed:
            if self.type == 'audio':
                self.set_audio_metadata()
            elif self.type == 'video':
                self.create_thumbnail()
                self.create_renditions()

    @property
    def archive_rendition(self) -> Optional[AbstractIonMediaRendition]:
        return self.renditions.filter(transcode_finished=True).first()

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=self.check_usage_block_types))

    def set_audio_metadata(self):
        transaction.on_commit(lambda: get_audio_metadata.delay(self.pk))

    def create_thumbnail(self):
        transaction.on_commit(lambda: generate_media_thumbnail.delay(self.pk))

    def create_renditions(self):
        is_video_file = self.mime_type.startswith('video/')
        for rendition in self.renditions.all():
            rendition.delete()
        for key, config in settings.ION_VIDEO_RENDITIONS.items():
            get_ion_media_rendition_model().objects.create(
                name=key,
                media_item=self,
                transcode_errors='Not a video file' if not is_video_file else None,
            )


class AbstractIonMediaRendition(IonFileContainerInterface, models.Model):
    name = models.CharField(
        max_length=128,
        choices=zip(
            settings.ION_VIDEO_RENDITIONS.keys(),
            settings.ION_VIDEO_RENDITIONS.keys()
        )
    )
    media_item = models.ForeignKey(
        settings.WAGTAILMEDIA_MEDIA_MODEL,
        on_delete=models.CASCADE,
        related_name='renditions',
    )
    file = IonFileField(
        upload_to='media_renditions',
        null=True,
        blank=True,
        verbose_name=_('file'),
        **FILE_META_FIELDS,
    )
    file_size = models.PositiveIntegerField(null=True, editable=False)
    file_last_modified = models.DateTimeField(null=True, editable=False)
    thumbnail = IonImageField(
        upload_to='media_thumbnails',
        null=True,
        blank=True,
        verbose_name=_('thumbnail'),
        **THUMBNAIL_META_FIELDS,
    )
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('width'))
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('height'))
    transcode_finished = models.BooleanField(default=False)
    transcode_errors = models.TextField(blank=True, null=True)
    checksum = models.CharField(max_length=255, default='null:')
    mime_type = models.CharField(max_length=128, null=True)
    thumbnail_checksum = models.CharField(max_length=255, default='null:')
    thumbnail_mime_type = models.CharField(max_length=128, null=True)
    thumbnail_file_size = models.PositiveIntegerField(null=True, editable=False)
    thumbnail_file_last_modified = models.DateTimeField(null=True, editable=False)

    class Meta:
        abstract = True
        unique_together = (
            ('name', 'media_item'),
        )

    def __str__(self):
        return "IonMediaRendition {} for {}".format(self.name, self.media_item)

    def save(self, *args, **kwargs):
        created = self.pk is None
        super().save(*args, **kwargs)
        if created:
            # generate rendition files on create
            transaction.on_commit(lambda: generate_media_rendition.delay(self.pk))

    @property
    def transcode_settings(self) -> Optional[dict]:
        if self.name:
            return settings.ION_VIDEO_RENDITIONS[self.name]


@receiver(pre_delete)
def prevent_deletion_if_in_use(sender, instance, **kwargs):
    if isinstance(instance, (AbstractIonDocument, AbstractIonImage, AbstractIonMedia)):
        usage = instance.get_usage()
        if usage:
            model_name = instance.__class__.__name__
            raise ProtectedError(
                f"Cannot delete instance of model '{model_name}' because it is referenced in stream field blocks",
                usage,
            )


@receiver(post_delete)
def remove_media_files(sender, instance, **kwargs):
    if isinstance(instance, (AbstractIonMedia, AbstractIonMediaRendition)):
        try:
            instance.file.delete(save=False)
        except ValueError:
            pass
        try:
            instance.thumbnail.delete(save=False)
        except ValueError:
            pass
