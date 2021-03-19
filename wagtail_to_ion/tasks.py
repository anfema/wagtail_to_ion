# Copyright © 2019 anfema GmbH. All rights reserved.
import os
import subprocess
import json
import hashlib
from tempfile import NamedTemporaryFile

from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.db.models.fields.files import FieldFile

from wagtail_to_ion.conf import settings

from celery import shared_task


BUFFER_SIZE = 64 * 1024

# Use ffmpeg from user's bin if it exists, global ffmpeg otherwise
# TODO: project specific? add setting?
ffmpeg = os.path.expanduser('~/bin/ffmpeg')
if not os.path.exists(ffmpeg):
    ffmpeg = 'ffmpeg'

ffprobe = os.path.expanduser('~/bin/ffprobe')
if not os.path.exists(ffmpeg):
    ffprobe = 'ffprobe'


def new_empty_thumbnail(suffix):
    data = bytes.fromhex('''
        ffd8ffdb0043000302020202020302020203030303040604040404040806
        06050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f10101110
        0a0c12131210130f101010ffc9000b080001000101011100ffcc00060010
        1005ffda0008010100003f00d2cf20ffd9
    ''')
    h = hashlib.new('sha256')
    thumbnail_name = 'blank-{}.jpg'.format(suffix)
    if not os.path.exists(os.path.join(settings.MEDIA_ROOT, 'media_thumbnails', thumbnail_name)):
        # create blank thumbnail
        with open(os.path.join(settings.MEDIA_ROOT, 'media_thumbnails', thumbnail_name), 'wb') as fp:
            fp.write(data)
    h.update(data)
    return (h, os.path.join('media_thumbnails', thumbnail_name))


def update_thumbnail_original(media_item, hash, filename):
    if filename is None:
        hash, filename = new_empty_thumbnail(media_item.id)
        media_item.thumbnail.name = filename
    else:
        media_item.thumbnail.name = os.path.join('media_thumbnails', os.path.basename(filename))

    media_item.thumbnail_mime_type = 'image/jpeg'
    media_item.thumbnail_checksum = 'sha256:' + hash.hexdigest()
    media_item.save()


def update_thumbnail_rendition(rendition, hash, filename):
    if filename is None:
        hash, filename = new_empty_thumbnail(rendition.id)
        rendition.thumbnail.name = filename
    else:
        rendition.thumbnail.name = os.path.join('media_thumbnails', os.path.basename(filename))

    rendition.thumbnail_checksum = 'sha256:' + hash.hexdigest()
    rendition.save()


def generate_rendition_thumbnail(rendition, rendition_file=None, thumbnail_file=None):
    if thumbnail_file is None:
        basename = os.path.basename(rendition.media_item.file.path)
        filename, _ = os.path.splitext(basename)
        thumbnail_file = os.path.join(settings.MEDIA_ROOT, 'media_thumbnails', '{}-{}.jpg'.format(filename, rendition.name))

    if rendition_file is None:
        rendition_file = rendition.file.path

    # generate rendition thumbnails
    try:
        rendition_head = [
            ffmpeg,
            '-i', rendition_file
        ]
        thumbnail = [
            '-y',
            '-vframes', '1',
            '-ss', '00:00:02.000',
            '-an',
            thumbnail_file
        ]
        subprocess.run(
            rendition_head + thumbnail,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        h = hashlib.new('sha256')
        with open(thumbnail_file, 'rb') as fp:
            buffer = fp.read(BUFFER_SIZE)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = fp.read(BUFFER_SIZE)

        update_thumbnail_rendition(rendition, h, thumbnail_file)
    except Exception as e:
        rendition.transcode_errors = 'ERROR generating rendition thumbnail:\n' + ' '.join(rendition_head + thumbnail) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            rendition.transcode_errors += e.stderr.decode('utf-8')
        else:
            rendition.transcode_errors += str(e)
        try:
            update_thumbnail_rendition(rendition, None, None)
        except Exception as e:
            rendition.transcode_errors += '\nERROR saving rendition thumbnail:\n' + str(e)
        rendition.save()
        return False  # Thumbnail generation failed

    return True


def generate_media_thumbnail(rendition, thumbnail_file=None):
    if thumbnail_file is None:
        basename = os.path.basename(rendition.media_item.file.path)
        filename, _ = os.path.splitext(basename)
        thumbnail_file = os.path.join(settings.MEDIA_ROOT, 'media_thumbnails', '{}-thumb.jpg'.format(filename))

    # generate media thumbnail
    try:
        head = [
            ffmpeg,
            '-i', rendition.media_item.file.path
        ]
        thumbnail = [
            '-y',
            '-vframes', '1',
            '-ss', '00:00:02.000',
            '-an',
            thumbnail_file
        ]
        subprocess.run(
            head + thumbnail,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        h = hashlib.new('sha256')
        with open(thumbnail_file, 'rb') as fp:
            buffer = fp.read(BUFFER_SIZE)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = fp.read(BUFFER_SIZE)

        update_thumbnail_original(rendition.media_item, h, thumbnail_file)
    except Exception as e:
        rendition.transcode_errors = 'ERROR generating media thumbnail:\n' + ' '.join(head + thumbnail) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            rendition.transcode_errors += e.stderr.decode('utf-8')
        else:
            rendition.transcode_errors += str(e)
        try:
            update_thumbnail_original(rendition.media_item, None, None)
            update_thumbnail_rendition(rendition, None, None)
        except Exception as e:
            rendition.transcode_errors += '\nERROR saving thumbnails:\n' + str(e)
        rendition.save()
        return False  # Thumbnail failed
    return True


@shared_task
def generate_media_rendition(rendition_id: int):
    from wagtail_to_ion.models import get_ion_media_rendition_model
    IonMediaRendition = get_ion_media_rendition_model()

    rendition = IonMediaRendition.objects.get(id=rendition_id)
    print("Running {}".format(rendition))

    basename = os.path.basename(rendition.media_item.file.path)
    filename, _ = os.path.splitext(basename)
    config = settings.ION_VIDEO_RENDITIONS[rendition.name]
    outfile = os.path.join(
        settings.MEDIA_ROOT,
        'media_renditions',
        '{}-{}.{}'.format(
            filename,
            rendition.name,
            config['container']
        )
    )
    thumbnail_file = os.path.join(settings.MEDIA_ROOT, 'media_thumbnails', '{}-{}.jpg'.format(filename, rendition.name))
    orig_thumbnail_file = os.path.join(settings.MEDIA_ROOT, 'media_thumbnails', '{}-thumb.jpg'.format(filename))

    # Construct the several parts of the ffmpeg command line piece by piece.
    # No shell expansion in order to avoid file name injections.
    #
    #   head: input file
    # vcodec: x264, higher crf gives better compression, as does 'slower' preset
    # compat: not used, only for reference - add to cmd when devices require it
    # scaler: hardcoded scaling to 720p while keeping aspect ratio
    # acodec: hardcoded 96kbps AAC
    #   tail: reorder file header for playing while still streaming,
    #         -strict -2 allows us to use the older LTS-16.04 ffmpeg
    #
    head = [
        ffmpeg,
        '-i', rendition.media_item.file.path
    ]
    vcodec = [
        '-vcodec',
        config['video']['codec'],
        '-' + config['video']['method'],
        str(config['video']['method_parameter']),
        '-preset',
        config['video']['preset']
    ]
    # compat = ['-profile:v', 'high', '-level', '4.0']
    acodec = [
        '-acodec', config['audio']['codec'],
        '-b:a', str(config['audio']['bitrate']) + 'k',
        '-ac', '2'
    ]
    tail = [
        '-movflags', '+faststart',
        '-y',
        '-strict',
        '-2',
        outfile
    ]

    # media info
    try:
        probe = [
            ffprobe,
            '-print_format', 'json',
            '-select_streams', 'v:0',
            '-show_streams',
            rendition.media_item.file.path
        ]
        result = subprocess.run(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        mediainfo = json.loads(result.stdout.decode('utf-8'))

        try:
            rendition.media_item.width = mediainfo['streams'][0]['width']
            rendition.media_item.height = mediainfo['streams'][0]['height']
            rendition.media_item.duration = round(float(mediainfo['streams'][0]['duration']))
            rendition.media_item.save()
        except (AttributeError, IndexError):
            pass  # probe failed, do not update item
    except Exception as e:
        rendition.transcode_errors = 'ERROR generating media info:\n' + ' '.join(probe) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            rendition.transcode_errors += e.stderr.decode('utf-8')
        else:
            rendition.transcode_errors += str(e)
        try:
            update_thumbnail_original(rendition.media_item, None, None)
            update_thumbnail_rendition(rendition, None, None)
        except Exception as e:
            rendition.transcode_errors += '\nERROR saving thumbnails:\n' + str(e)
        rendition.save()
        return  # Thumbnail failed

    # generate media thumbnail
    result = generate_media_thumbnail(rendition, thumbnail_file=orig_thumbnail_file)
    if result is False:
        return  # Thumbnail generation failed

    # transcode
    try:
        w = config['video']['size'][0]
        h = config['video']['size'][1]
        if rendition.media_item.height > rendition.media_item.width:
            w, h = h, w  # portrait mode video, rotate the scaler

        scaler = [
            '-filter:v',
            'scale={}:{}'.format(w, h)
        ]
        result = subprocess.run(
            head + vcodec + scaler + acodec + tail,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        rendition.file.name = os.path.join('media_renditions', os.path.basename(outfile))
    except Exception as e:
        rendition.transcode_errors = 'ERROR transcoding media:\n' + ' '.join(head + vcodec + scaler + acodec + tail) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            rendition.transcode_errors += e.stderr.decode('utf-8')
        else:
            rendition.transcode_errors += str(e)
        try:
            update_thumbnail_rendition(rendition, None, None)
        except Exception as e:
            rendition.transcode_errors += '\nERROR saving rendition thumbnail:\n' + str(e)
        rendition.save()
        return  # Transcode failed

    # generate rendition thumbnails
    result = generate_rendition_thumbnail(rendition, rendition_file=outfile, thumbnail_file=thumbnail_file)
    if result is False:
        return  # Error while generating thumbnail

    # update rendition media info
    try:
        probe = [
            ffprobe,
            '-print_format', 'json',
            '-select_streams', 'v:0',
            '-show_streams',
            outfile
        ]
        result = subprocess.run(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        mediainfo = json.loads(result.stdout.decode('utf-8'))

        h = hashlib.new('sha256')
        with open(outfile, 'rb') as fp:
            buffer = fp.read(BUFFER_SIZE)
            while len(buffer) > 0:
                h.update(buffer)
                buffer = fp.read(BUFFER_SIZE)
        rendition.checksum = 'sha256:{}'.format(h.hexdigest())

        try:
            rendition.width = mediainfo['streams'][0]['width']
            rendition.height = mediainfo['streams'][0]['height']
            rendition.transcode_finished = True
        except (AttributeError, IndexError) as e:
            # probe of rendition failed, do not update item
            rendition.transcode_errors = str(e)

        rendition.save()
    except Exception as e:
        rendition.transcode_errors = 'ERROR generating rendition media info:\n' + ' '.join(probe) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            rendition.transcode_errors += e.stderr.decode('utf-8')
        else:
            rendition.transcode_errors += str(e)
        rendition.save()


def extract_media_format(file_path):
    ffprobe = os.path.expanduser('~/bin/ffprobe')
    if not os.path.exists(ffprobe):
        ffprobe = 'ffprobe'

    probe = [
        ffprobe,
        '-print_format', 'json',
        '-show_format',
        '-i', file_path,
    ]

    try:
        result = subprocess.run(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr)
        raise

    return json.loads(result.stdout.decode('utf-8'))


def get_audio_metadata(media_item: FieldFile):
    if isinstance(media_item.file, InMemoryUploadedFile):
        with NamedTemporaryFile(delete=False) as temp_file:
            media_item.file.open()
            temp_file.write(media_item.file.read())
            temp_file.close()
            mediainfo = extract_media_format(temp_file.name)
            try:
                os.remove(temp_file.name)
            except OSError:
                pass
    elif isinstance(media_item.file, TemporaryUploadedFile):
        mediainfo = extract_media_format(media_item.file.temporary_file_path())
    else:
        mediainfo = extract_media_format(media_item.path)

    return mediainfo.get('format', {})
