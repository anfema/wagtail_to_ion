# Copyright © 2017 anfema GmbH. All rights reserved.
import hashlib
import os

from django.db import models
from django.db.utils import cached_property
from django.utils.translation import ugettext_lazy as _


from magic import from_buffer as magic_from_buffer
from wagtail.documents.blocks import *
from wagtail.documents.models import AbstractDocument
from wagtail.images.models import AbstractImage, AbstractRendition
from wagtailmedia.blocks import AbstractMediaChooserBlock
from wagtailmedia.models import AbstractMedia, SourceImageIOError

from wagtail_to_ion.conf import settings
from wagtail_to_ion.tasks import generate_media_rendition


BUFFER_SIZE = 64 * 1024


class IonDocument(AbstractDocument):
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


class IonImage(AbstractImage):
    checksum = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128)
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

    @property
    def archive_rendition(self):
        try:
            result = self.get_rendition('jpegquality-70')
        except SourceImageIOError as e:
            if not settings.ION_ALLOW_MISSING_FILES:
                raise e
            return None

        h = hashlib.new('sha256')
        try:
            result.file.open()
            buffer = result.file.read(BUFFER_SIZE)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = result.file.read(BUFFER_SIZE)
            self.checksum = 'sha256:' + h.hexdigest()
        except FileNotFoundError as e:
            if settings.ION_ALLOW_MISSING_FILES is True:
                rendition = self.get_rendition_model()
                result = rendition()
            else:
                raise e

        setattr(result, 'checksum', 'sha256:' + h.hexdigest())
        setattr(result, 'mime_type', 'image/jpeg')
        return result


class IonRendition(AbstractRendition):
    image = models.ForeignKey(IonImage, related_name='renditions', on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class IonMedia(AbstractMedia):
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

    thumbnail_checksum = models.CharField(max_length=255)
    thumbnail_mime_type = models.CharField(max_length=128)
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

    def save(self, *args, **kwargs):
        needs_transcode = False
        needs_thumbnail = False
        try:
            obj = IonMedia.objects.get(pk=self.pk)
        except IonMedia.DoesNotExist:
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
            except FileNotFoundError as exception:
                raise exception
            except ValueError:
                pass

        if needs_transcode:
            try:
                self.file.open()
                h = hashlib.new('sha256')
                buffer = self.file.read(BUFFER_SIZE)
                self.mime_type = magic_from_buffer(buffer, mime=True)
                while len(buffer) > 0:
                    h.update(buffer)
                    buffer = self.file.read(BUFFER_SIZE)
                self.checksum = 'sha256:' + h.hexdigest()
            except FileNotFoundError as exception:
                raise exception

        super().save(*args, **kwargs)
        try:
            os.chmod(self.file.path, 0o644)
            os.chmod(self.thumbnail.path, 0o644)
        except ValueError:
            pass

        # remove all renditions and generate new ones
        if needs_transcode:
            renditions = []
            for rendition in self.renditions.all():
                rendition.delete()
            for key, config in settings.ION_VIDEO_RENDITIONS.items():
                rendition = IonMediaRendition.objects.create(
                    name=key,
                    media_item=self
                )
                if not self.mime_type.startswith('video/'):
                    rendition.transcode_errors = 'Not a video file'
                    rendition.save()
                renditions.append(rendition)

            if self.mime_type.startswith('video/'):
                # Run transcode in background
                for rendition in renditions:
                    generate_media_rendition.delay(rendition.id)

    def delete(self, *args, **kwargs):
        try:
            self.file.delete()
        except ValueError:
            pass
        try:
            self.thumbnail.delete()
        except ValueError:
            pass
        # delete one by one to make sure files are deleted
        for rendition in self.renditions.all():
            rendition.delete()
        super().delete(*args, **kwargs)


class IonMediaRendition(models.Model):
    name = models.CharField(
        max_length=128,
        choices=zip(
            settings.ION_VIDEO_RENDITIONS.keys(),
            settings.ION_VIDEO_RENDITIONS.keys()
        )
    )
    media_item = models.ForeignKey(IonMedia, on_delete=models.CASCADE, related_name='renditions')
    file = models.FileField(upload_to='media_renditions', null=True, blank=True, verbose_name=_('file'))
    thumbnail = models.FileField(upload_to='media_thumbnails', null=True, blank=True, verbose_name=_('thumbnail'))
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('width'))
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('height'))
    transcode_finished = models.BooleanField(default=False)
    transcode_errors = models.TextField(blank=True, null=True)
    checksum = models.CharField(max_length=255, default='null:')
    thumbnail_checksum = models.CharField(max_length=255, default='null:')

    class Meta:
        unique_together = (('name', 'media_item'), )

    def __str__(self):
        return "IonMediaRendition {} for {}".format(self.name, self.media_item)

    def delete(self, *args, **kwargs):
        try:
            self.file.delete()
        except ValueError:
            pass
        try:
            self.thumbnail.delete()
        except ValueError:
            pass
        super().delete(*args, **kwargs)


class IonMediaBlock(AbstractMediaChooserBlock):
    @cached_property
    def target_model(self):
        from wagtailmedia.models import get_media_model
        return get_media_model()

    @cached_property
    def widget(self):
        from wagtailmedia.widgets import AdminMediaChooser
        return AdminMediaChooser

    def render_basic(self, value, context=None):
        raise NotImplementedError('You need to implement %s.render_basic' % self.__class__.__name__)
