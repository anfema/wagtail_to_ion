# Wagtail to ION API adapter

Content:

1. Requirements
2. Installation
3. Settings
4. Available hooks

## 1. Requirements

- Wagtail > 2.0 and WagtailMedia
- Django > 2.2
- Celery
- RestFramework
- BeautifulSoup
- `python-magic`
- `ffmpeg` and `ffprobe` for Media conversion

## 2. Installation

1. Add it (and wagtail media) to `INSTALLED_APPS`
```python
  INSTALLED_APPS = [
      'wagtailmedia',
      'wagtail_to_ion',
      ...
  ]
```
2. Add `ION_VIDEO_RENDITIONS` (see below) to `settings.py`
3. Add overridden URLs into your `urls.py`
```python
    path('cms/', include('wagtail_to_ion.urls.wagtail_override_urls')),  # overridden urls by the api adapter
    path('cms/', include('wagtail.admin.urls')),                         # default wagtail admin urls
```
4. Add new API URLs
```python
    path('api/v1/', include(('wagtail_to_ion.urls.api_urls', 'wagtail_to_ion'), namespace='v1')),
```

5. Create required models in your project inheriting from the abstract models provided by `wagtail_to_ion`:
```python
from wagtail_to_ion.models.abstract import AbstractIonCollection, AbstractIonPage
from wagtail_to_ion.models.content_type_description import AbstractContentTypeDescription
from wagtail_to_ion.models.file_based_models import AbstractIonDocument, AbstractIonImage, AbstractIonMedia, \
    AbstractIonMediaRendition, AbstractIonRendition
from wagtail_to_ion.models.page_models import AbstractIonLanguage


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
```

6. Add the models to `settings.py`:
```python
WAGTAILDOCS_DOCUMENT_MODEL = 'my_app.IonDocument'
WAGTAILIMAGES_IMAGE_MODEL = 'my_app.IonImage'
WAGTAILMEDIA_MEDIA_MODEL = 'my_app.IonMedia'

ION_COLLECTION_MODEL = 'my_app.IonCollection'
ION_LANGUAGE_MODEL = 'my_app.IonLanguage'
ION_IMAGE_RENDITION_MODEL = 'my_app.IonRendition'
ION_MEDIA_RENDITION_MODEL = 'my_app.IonMediaRendition'
ION_CONTENT_TYPE_DESCRIPTION_MODEL = 'my_app.ContentTypeDescription'
```

7. (Optional) Create models for custom page types inheriting from `AbstractIonPage` 

8. Create and apply migrations

Make sure you run a celery worker in addition to the django backend for the video conversion to work.

## 3. Settings

### `GET_PAGES_BY_USER`

Set to true if the pages in the API are differently scoped for unique users. Defaults to `false`

### `ION_ALLOW_MISSING_FILES`

If set to `True` the serializer allows missing media files and will just skip them, if set to `False` (the default) the renderer will throw an exception when a file is missing.

### `ION_VIDEO_RENDITIONS`

Defines the renditions that are generated when a user uploads a new video file.

Sane defaults would be something like this:

```python
{
    "720p": {
        "video": {
            "codec": "libx264",
            "size": [-1, 720],
            "method": "crf",
            "method_parameter": 28,
            "preset": "slow"
        },
        "audio": {
            "codec": "aac",
            "bitrate": 96
        },
        "container": "mp4"
    },
    "1080p": {
        "video": {
            "codec": "libx264",
            "size": [-1, 1080],
            "method": "crf",
            "method_parameter": 28,
            "preset": "slow"
        },
        "audio": {
            "codec": "aac",
            "bitrate": 128
        },
        "container": "mp4"
    }
}
```

## 4. Available hooks

### `page_created` signal

The `wagtail_to_ion.signals.page_created` signal is fired after creating a new page to allow
for permission management outside the scope of this API adapter. You will get two keyword
arguments: `request` and `page` which contain the request object that created the page and
the new page instance. The signal is sent after inserting the page into the tree and before
publishing. So you'll have to call `page.save()` if you want your changes to be permanent.

### Overriding Views

To override a view, just create a Subclass of the original view and include it in your
`urls.py` __before__ the original api urls.

The following Views are available:

#### Collection related views

- `CollectionListView`, list of collection content
  - Override the serializer with `serializer_class`
  - Override `get_queryset` to add additional filtering
- `CollectionDetailView`, detail of collection
  - Override the serializer with `serializer_class`
  - Override `get_queryset` to add additional filtering
- `CollectionArchiveView`, tar archive for collection
  - Override page serializer with `content_serializer_class`
  - Override `get_queryset` to implement custom by-user filtering, the default will only use
    the `PageViewRestriction` of Wagtail
  - Override `get` to allow for custom `lastUpdated` handling

#### Locale related views

- `LocaleListView`, list of available locales for a collection
  - Override the serializer with `serializer_class`

#### Page related views

- `DynamicPageDetailView`, fetch page details
  - Override page serializer with `serializer_class`
  - Override `get_queryset` to allow for extra filtering
- `PageArchiveView`, fetch a page archive tar file
  - Override page serializer with `serializer_class`
  - Override `get_queryset` to allow for extra filtering

### Overriding Serializers

#### Collection related serializers

- `CollectionSerializer`
  - Override `get_identifier` or `get_name` to modify collection info
- `CollectionDetailSerializer`
  - Override `content_serializer_class` to modify page serialization

Attention: When you override `CollectionSerializer` you have to override the
`CollectionDetailSerializer` too since it inherits from it. Like this:

```python
class CollectionDetailSerializerOverride(CollectionDetailSerializer, CollectionSerializerOverride):
    pass
```

#### Locale related serializers

- `LocaleSerializer`, serializes locale data, standard `rest_framework.serializers.ModelSerializer`

#### Page related serializers

- `DynamicPageSerializer`, serializes only page meta data
  - Override `get_last_changed` if you want to implement per user dynamic pages that change more often than
    they are actually published.
- `DynamicPageDetailSerializer`, serializes page meta data and content, inherits from `DynamicPageSerializer`
  - Override `get_contents_for_user` to implement per user dynamic pages that render completely custom data
  - Override `get_children` for additional filtering.

Attention: When you override `DynamicPageSerializer` you have to override the
`DynamicPageDetailSerializer` too since it inherits from it. Example:

```python
class DynamicPageDetailSerializerOverride(DynamicPageDetailSerializer, DynamicPageSerializerOverride):
    pass
```
