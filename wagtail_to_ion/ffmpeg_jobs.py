import json
import os
import subprocess
from pathlib import Path
from typing import Optional, NamedTuple


# Use ffmpeg from user's bin if it exists, global ffmpeg otherwise
# TODO: project specific? add setting?
ffmpeg = os.path.expanduser('~/bin/ffmpeg')
if not os.path.exists(ffmpeg):
    ffmpeg = 'ffmpeg'

ffprobe = os.path.expanduser('~/bin/ffprobe')
if not os.path.exists(ffmpeg):
    ffprobe = 'ffprobe'


class CodecProcessError(Exception):
    pass


class AudioMetaData(NamedTuple):
    duration: int


class VideoMetaData(NamedTuple):
    width: int
    height: int
    duration: int


def extract_audio_metadata(input_path: Path) -> Optional[AudioMetaData]:
    # audio media info
    probe = [
        ffprobe,
        '-print_format', 'json',
        '-show_format',
        '-i', str(input_path),
    ]

    try:
        result = subprocess.run(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        mediainfo = json.loads(result.stdout.decode('utf-8'))

        return AudioMetaData(
            duration=round(float(mediainfo['format']['duration'])),
        )
    except Exception as e:
        errors = 'ERROR generating media info:\n' + ' '.join(probe) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            errors += e.stderr.decode('utf-8')
        else:
            errors += str(e)
        raise CodecProcessError(errors)


def extract_video_metadata(input_path: Path) -> Optional[VideoMetaData]:
    # video media info
    probe = [
        ffprobe,
        '-print_format', 'json',
        '-select_streams', 'v:0',
        '-show_streams',
        str(input_path),
    ]
    try:
        result = subprocess.run(
            probe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        mediainfo = json.loads(result.stdout.decode('utf-8'))

        return VideoMetaData(
            width=mediainfo['streams'][0]['width'],
            height=mediainfo['streams'][0]['height'],
            duration=round(float(mediainfo['streams'][0]['duration'])),
        )
    except Exception as e:
        errors = 'ERROR generating media info:\n' + ' '.join(probe) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            errors += e.stderr.decode('utf-8')
        else:
            errors += str(e)
        raise CodecProcessError(errors)


def extract_video_thumbnail(input_path: Path, output_path: Path, video_duration: Optional[int] = None):
    if video_duration is None:
        metadata = extract_video_metadata(input_path)
        video_duration = metadata.duration

    # use the first frame for short videos else the one at 2 seconds
    thumbnail_pos = '00:00:02.000' if video_duration > 5 else '00:00:00.000'

    # generate media thumbnail
    head = [
        ffmpeg,
        '-i', str(input_path)
    ]
    thumbnail = [
        '-y',
        '-vframes', '1',
        '-ss', thumbnail_pos,
        '-an',
        str(output_path),
    ]
    try:
        subprocess.run(
            head + thumbnail,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
    except Exception as e:
        errors = 'ERROR generating media thumbnail:\n' + ' '.join(head + thumbnail) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            errors += e.stderr.decode('utf-8')
        else:
            errors += str(e)
        raise CodecProcessError(errors)


def transcode_video(input_path: Path, output_path: Path, meta_data: VideoMetaData, config: dict):
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
        '-i', str(input_path),
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
        str(output_path),
    ]

    w = config['video']['size'][0]
    h = config['video']['size'][1]
    if meta_data.height > meta_data.width:
        w, h = h, w  # portrait mode video, rotate the scaler

    scaler = [
        '-filter:v',
        'scale={}:{}'.format(w, h)
    ]

    try:
        subprocess.run(
            head + vcodec + scaler + acodec + tail,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
    except Exception as e:
        errors = 'ERROR transcoding media:\n' + ' '.join(head + vcodec + scaler + acodec + tail) + '\n'
        if isinstance(e, subprocess.CalledProcessError):
            errors += e.stderr.decode('utf-8')
        else:
            errors += str(e)
        raise CodecProcessError(errors)
