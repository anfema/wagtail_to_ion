# Copyright © 2017 anfema GmbH. All rights reserved.
import hashlib
from typing import Optional, Tuple

from django.core.files import File
from django.db import models, transaction
from django.db.models import ProtectedError
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from magic import from_buffer as magic_from_buffer
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.documents.models import AbstractDocument
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import AbstractImage, AbstractRendition
from wagtailmedia.models import AbstractMedia

from wagtail_to_ion.blocks import IonMediaBlock
from wagtail_to_ion.conf import settings
from wagtail_to_ion.models import get_ion_media_rendition_model
from wagtail_to_ion.tasks import generate_media_rendition, get_audio_metadata, generate_media_thumbnail

Checksum = str
MimeType = str


BUFFER_SIZE = 64 * 1024


def get_file_metadata(file: File, detect_mime_type: bool = True) -> Tuple[Checksum, Optional[MimeType]]:
    """Calculate checksum and detect mime type in one go."""
    sha256 = hashlib.sha256()
    mime_type = None

    for i, chunk in enumerate(file.chunks(chunk_size=BUFFER_SIZE)):
        sha256.update(chunk)
        if detect_mime_type and i == 0:
            mime_type = magic_from_buffer(chunk, mime=True)

    return f'sha256:{sha256.hexdigest()}', mime_type


class AbstractIonDocument(AbstractDocument):
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

    def save(self, *args, **kwargs):
        self.checksum, self.mime_type = get_file_metadata(self.file)
        super().save(*args, **kwargs)

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=self.check_usage_block_types))


class AbstractIonImage(AbstractImage):
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

    def save(self, *args, **kwargs):
        self.checksum, self.mime_type = get_file_metadata(self.file)
        super().save(*args, **kwargs)

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=self.check_usage_block_types))

    @property
    def archive_rendition(self):
        result = self.get_rendition(self.rendition_type)

        try:
            result.checksum, result.mime_type = get_file_metadata(result.file)
        except FileNotFoundError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                rendition = self.get_rendition_model()
                result = rendition()
                result.mime_type = 'application/x-empty'
            else:
                raise e

        return result


class AbstractIonRendition(AbstractRendition):
    image = models.ForeignKey(settings.WAGTAILIMAGES_IMAGE_MODEL, related_name='renditions', on_delete=models.CASCADE)
    file_size = models.PositiveIntegerField(null=True, editable=False)
    file_last_modified = models.DateTimeField(null=True, editable=False)

    class Meta:
        abstract = True
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class AbstractIonMedia(AbstractMedia):
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
    thumbnail = models.ImageField(
        upload_to='media_thumbnails',
        verbose_name=_('thumbnail'),
        null=True,
        blank=True
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
        skip_state_detection = kwargs.pop('skip_state_detection', False)  # True if fields have been set by a task

        if skip_state_detection:
            super().save(*args, **kwargs)
            return

        # handle audio files
        if self.type == 'audio':
            self.set_media_metadata()
            super().save(*args, **kwargs)
            transaction.on_commit(lambda: get_audio_metadata.delay(self.pk))
            return

        # handle video files
        needs_transcode = False
        needs_thumbnail = False

        if not self.pk:
            needs_transcode = True
            needs_thumbnail = True
        else:
            obj = self._meta.default_manager.get(pk=self.pk)

            if obj.file != self.file:
                needs_transcode = True
                needs_thumbnail = True
            elif obj.thumbnail != self.thumbnail:
                if self.pk:  # thumbnail was manually changed
                    if not self.thumbnail:  # thumbnail was reset
                        needs_thumbnail = True
                    else:
                        self.set_thumbnail_metadata()

        if needs_transcode:
            self.set_media_metadata()

        super().save(*args, **kwargs)

        if needs_thumbnail:
            transaction.on_commit(lambda: generate_media_thumbnail.delay(self.pk))

        # remove all renditions and generate new ones
        if needs_transcode:
            self.create_renditions()

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=self.check_usage_block_types))

    def set_media_metadata(self):
        self.checksum, self.mime_type = get_file_metadata(self.file)

    def set_thumbnail_metadata(self):
        self.thumbnail_checksum, self.thumbnail_mime_type = get_file_metadata(self.thumbnail)

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


class AbstractIonMediaRendition(models.Model):
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
    file = models.FileField(upload_to='media_renditions', null=True, blank=True, verbose_name=_('file'))
    file_size = models.PositiveIntegerField(null=True, editable=False)
    file_last_modified = models.DateTimeField(null=True, editable=False)
    thumbnail = models.FileField(upload_to='media_thumbnails', null=True, blank=True, verbose_name=_('thumbnail'))
    thumbnail_file_size = models.PositiveIntegerField(null=True, editable=False)
    thumbnail_file_last_modified = models.DateTimeField(null=True, editable=False)
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('width'))
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('height'))
    transcode_finished = models.BooleanField(default=False)
    transcode_errors = models.TextField(blank=True, null=True)
    checksum = models.CharField(max_length=255, default='null:')
    thumbnail_checksum = models.CharField(max_length=255, default='null:')

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
