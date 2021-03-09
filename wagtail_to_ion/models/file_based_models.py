# Copyright © 2017 anfema GmbH. All rights reserved.
import hashlib
import os

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from magic import from_buffer as magic_from_buffer
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.documents.models import AbstractDocument
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import AbstractImage, AbstractRendition
from wagtailmedia.models import AbstractMedia

from wagtail_to_ion.conf import settings
from wagtail_to_ion.models import get_ion_media_rendition_model
from wagtail_to_ion.tasks import generate_media_rendition, get_audio_metadata


BUFFER_SIZE = 64 * 1024


class AbstractIonDocument(AbstractDocument):
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
    include_in_archive = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_form_fields = (
        'title',
        'file',
        'collection',
        'tags',
        'include_in_archive',
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        try:
            self.file.open()
            h = hashlib.new('sha256')
            buffer = self.file.read(BUFFER_SIZE)
            if not self.mime_type:
                self.mime_type = magic_from_buffer(buffer, mime=True)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = self.file.read(BUFFER_SIZE)
            self.checksum = 'sha256:' + h.hexdigest()
        except FileNotFoundError as exception:
            raise exception
        super().save(*args, **kwargs)
        os.chmod(self.file.path, 0o644)

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=DocumentChooserBlock))


class AbstractIonImage(AbstractImage):
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
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

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        try:
            self.file.open()
            h = hashlib.new('sha256')
            buffer = self.file.read(BUFFER_SIZE)
            if not self.mime_type:
                self.mime_type = magic_from_buffer(buffer, mime=True)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = self.file.read(BUFFER_SIZE)
            self.checksum = 'sha256:' + h.hexdigest()
        except FileNotFoundError as exception:
            raise exception
        super().save(*args, **kwargs)
        os.chmod(self.file.path, 0o644)

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=ImageChooserBlock))

    @property
    def archive_rendition(self):
        result = self.get_rendition(self.rendition_type)

        h = hashlib.new('sha256')
        try:
            result.file.open()
            buffer = result.file.read(BUFFER_SIZE)
            mime_type = magic_from_buffer(buffer, mime=True)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = result.file.read(BUFFER_SIZE)
            self.checksum = 'sha256:' + h.hexdigest()
        except FileNotFoundError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                rendition = self.get_rendition_model()
                result = rendition()
                mime_type = 'application/x-empty'
            else:
                raise e

        setattr(result, 'checksum', 'sha256:' + h.hexdigest())
        setattr(result, 'mime_type', mime_type)
        return result


class AbstractIonRendition(AbstractRendition):
    image = models.ForeignKey(settings.WAGTAILIMAGES_IMAGE_MODEL, related_name='renditions', on_delete=models.CASCADE)

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

    thumbnail_checksum = models.CharField(blank=True, max_length=255)
    thumbnail_mime_type = models.CharField(blank=True, max_length=128)
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

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # handle audio files
        if self.type == 'audio':
            self.set_media_metadata()
            super().save(*args, **kwargs)
            return

        # handle video files
        needs_transcode = False
        needs_thumbnail = False
        try:
            obj = self._meta.default_manager.get(pk=self.pk)
        except self.DoesNotExist:
            needs_transcode = True
            needs_thumbnail = True
        else:
            if not obj.file.path == self.file.path:
                needs_transcode = True
            try:
                if not obj.thumbnail.path == self.thumbnail.path:
                    needs_thumbnail = True
            except ValueError:
                pass

        if needs_thumbnail:
            self.set_thumbnail_metadata()

        if needs_transcode:
            self.set_media_metadata()

        super().save(*args, **kwargs)
        try:
            os.chmod(self.file.path, 0o644)
            os.chmod(self.thumbnail.path, 0o644)
        except ValueError:
            pass

        # remove all renditions and generate new ones
        if needs_transcode:
            self.create_renditions()

    def get_usage(self):
        from wagtail_to_ion.utils import get_object_block_usage
        return super().get_usage().union(get_object_block_usage(self, block_types=IonMediaBlock))

    def set_media_metadata(self):
        self.file.open()
        h = hashlib.new('sha256')
        buffer = self.file.read(BUFFER_SIZE)
        self.mime_type = magic_from_buffer(buffer, mime=True)
        while len(buffer) > 0:
            h.update(buffer)
            buffer = self.file.read(BUFFER_SIZE)
        self.checksum = 'sha256:' + h.hexdigest()
        self.file.seek(0)

        if self.type == 'audio':
            metadata = get_audio_metadata(self.file)
            self.duration = round(float(metadata.get('duration')))

    def set_thumbnail_metadata(self):
        try:
            self.thumbnail.open()
            h = hashlib.new('sha256')
            buffer = self.thumbnail.read(BUFFER_SIZE)
            if not self.thumbnail_mime_type:
                self.thumbnail_mime_type = magic_from_buffer(buffer, mime=True)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = self.thumbnail.read(BUFFER_SIZE)
            self.thumbnail_checksum = 'sha256:' + h.hexdigest()
        except ValueError:
            pass

    def create_renditions(self):
        renditions = []
        for rendition in self.renditions.all():
            rendition.delete()
        for key, config in settings.ION_VIDEO_RENDITIONS.items():
            rendition = get_ion_media_rendition_model().objects.create(
                name=key,
                media_item=self,
            )
            if not self.mime_type.startswith('video/'):
                rendition.transcode_errors = 'Not a video file'
                rendition.save()
            renditions.append(rendition)

        if self.mime_type.startswith('video/'):
            # Run transcode in background
            for rendition in renditions:
                generate_media_rendition.delay(rendition.id)


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
    thumbnail = models.FileField(upload_to='media_thumbnails', null=True, blank=True, verbose_name=_('thumbnail'))
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
