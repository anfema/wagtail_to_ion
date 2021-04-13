# Copyright © 2019 anfema GmbH. All rights reserved.
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Tuple

from django.core.files import File
from django.core.files.base import ContentFile
from django.db.models.fields.files import FieldFile

from celery import shared_task

from wagtail_to_ion import ffmpeg_jobs

if TYPE_CHECKING:
    from wagtail_to_ion.models.file_based_models import AbstractIonMedia, AbstractIonMediaRendition


BUFFER_SIZE = 64 * 1024


def new_empty_thumbnail(suffix) -> Tuple[str, ContentFile]:
    data = bytes.fromhex('''
        ffd8ffdb0043000302020202020302020203030303040604040404040806
        06050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f10101110
        0a0c12131210130f101010ffc9000b080001000101011100ffcc00060010
        1005ffda0008010100003f00d2cf20ffd9
    ''')
    thumbnail_name = 'blank-{}.jpg'.format(suffix)
    sha256 = hashlib.sha256(data)

    return f'sha256:{sha256.hexdigest()}', ContentFile(data, name=thumbnail_name)


def setup_work_dir(file: FieldFile) -> Tuple[TemporaryDirectory, Path]:
    """Create a temporary directory as working directory and make the source file locally available."""
    temp_dir = TemporaryDirectory()

    try:
        source_file_path = Path(file.path)
    except (AttributeError, NotImplementedError):
        source_file_path = Path(temp_dir.name) / Path(file.name).name

        with source_file_path.open('wb') as fp:
            if file.multiple_chunks():
                for chunk in file.chunks():
                    fp.write(chunk)
            else:
                fp.write(file.read())

    return temp_dir, source_file_path


@shared_task
def generate_media_thumbnail(media_id: int):
    """Generate thumbnail from video and set media metadata."""
    from wagtail_to_ion.models import get_ion_media_model
    from wagtail_to_ion.models.file_based_models import get_file_metadata

    media: AbstractIonMedia = get_ion_media_model().objects.get(pk=media_id)
    work_dir, source_file_path = setup_work_dir(media.file)

    thumbnail_filename = f'{source_file_path.stem}-thumb.jpg'
    thumbnail_path = Path(work_dir.name) / thumbnail_filename

    try:
        metadata = ffmpeg_jobs.extract_video_metadata(source_file_path)
        ffmpeg_jobs.extract_video_thumbnail(source_file_path, thumbnail_path)
        media.thumbnail.save(name=thumbnail_filename, content=File(thumbnail_path.open('rb')), save=False)
        media.thumbnail_checksum, media.thumbnail_mime_type = get_file_metadata(File(thumbnail_path.open('rb')))
        media.width = metadata.width
        media.height = metadata.height
        media.duration = metadata.duration
        media.save(skip_state_detection=True)
    except ffmpeg_jobs.CodecProcessError:
        if not media.thumbnail:
            checksum, empty_thumbnail = new_empty_thumbnail(media.pk)
            media.thumbnail.save(name=empty_thumbnail.name, content=empty_thumbnail, save=False)
            media.thumbnail_checksum = checksum
            media.thumbnail_mime_type = 'image/jpeg'
            media.save(skip_state_detection=True)
    finally:
        work_dir.cleanup()


@shared_task
def generate_media_rendition(rendition_id: int):
    """Generate rendition from video media."""
    from wagtail_to_ion.models import get_ion_media_rendition_model
    from wagtail_to_ion.models.file_based_models import get_file_metadata

    rendition: AbstractIonMediaRendition = get_ion_media_rendition_model().objects.get(id=rendition_id)
    work_dir, source_file_path = setup_work_dir(rendition.media_item.file)

    rendition_filename = f'{source_file_path.stem}-{rendition.name}.{rendition.transcode_settings["container"]}'
    rendition_path = Path(work_dir.name) / rendition_filename

    thumbnail_filename = f'{source_file_path.stem}-{rendition.name}.jpg'
    thumbnail_path = Path(work_dir.name) / thumbnail_filename

    try:
        metadata = ffmpeg_jobs.extract_video_metadata(source_file_path)
        ffmpeg_jobs.transcode_video(source_file_path, rendition_path, metadata, rendition.transcode_settings)
        rendition_metadata = ffmpeg_jobs.extract_video_metadata(rendition_path)
        ffmpeg_jobs.extract_video_thumbnail(rendition_path, thumbnail_path)

        rendition.file.save(rendition_filename, File(rendition_path.open('rb')), save=False)
        rendition.width = rendition_metadata.width
        rendition.height = rendition_metadata.height
        rendition.checksum, _ = get_file_metadata(File(rendition_path.open('rb')), detect_mime_type=False)

        rendition.thumbnail.save(thumbnail_filename, File(thumbnail_path.open('rb')), save=False)
        rendition.thumbnail_checksum, _ = get_file_metadata(File(thumbnail_path.open('rb')), detect_mime_type=False)
        rendition.transcode_finished = True
        rendition.save()
    except ffmpeg_jobs.CodecProcessError as e:
        rendition.transcode_errors = str(e)
        rendition.save()
    finally:
        work_dir.cleanup()


@shared_task
def regenerate_rendition_thumbnail(rendition: AbstractIonMediaRendition):
    """Regenerate media rendition thumbnail."""
    from wagtail_to_ion.models.file_based_models import get_file_metadata

    work_dir, source_file_path = setup_work_dir(rendition.file)

    thumbnail_filename = Path(rendition.thumbnail.name).name
    thumbnail_path = Path(work_dir.name) / thumbnail_filename

    try:
        ffmpeg_jobs.extract_video_thumbnail(source_file_path, thumbnail_path)
        rendition.thumbnail.save(thumbnail_filename, File(thumbnail_path.open('rb')), save=False)
        rendition.thumbnail_checksum, _ = get_file_metadata(File(thumbnail_path.open('rb')), detect_mime_type=False)
        rendition.save()
    except ffmpeg_jobs.CodecProcessError as e:
        rendition.transcode_errors = str(e)
        rendition.save()
    finally:
        work_dir.cleanup()


@shared_task
def get_audio_metadata(media_id: int):
    from wagtail_to_ion.models import get_ion_media_model

    media: AbstractIonMedia = get_ion_media_model().objects.get(pk=media_id)
    work_dir, source_file_path = setup_work_dir(media.file)

    try:
        mediainfo = ffmpeg_jobs.extract_audio_metadata(source_file_path)
        media.duration = mediainfo.duration
        media.save(skip_state_detection=True)
    except ffmpeg_jobs.CodecProcessError:
        pass
    finally:
        work_dir.cleanup()
