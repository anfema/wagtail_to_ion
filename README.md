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

1. Add it to `INSTALLED_APPS`
```python
  INSTALLED_APPS = [
      'wagtail_to_ion',
      ...
  ]
```
2. Add `ION_VIDEO_RENDITIONS` (see below) to `settings.py`
3. Add overridden URLs into your `urls.py`
```python
    url(r'^cms/', include('wagtail_to_ion.urls.wagtail_override_urls')), # overridden urls by the api adapter
    url(r'^cms/', include(wagtailadmin_urls)),                           # default wagtail admin urls
```
4. Add new API URLs
```python
    url(r'^', include('wagtail_to_ion.urls.api_urls')),
```

Make sure you run a celery worker in addition to the django backend for the video conversion to work.

## 3. Settings

### `GET_PAGES_BY_USER`

Set to true if the pages in the API are differently scoped for unique users. Defaults to `false`

### `WAGTAIL_TO_ION_MODEL_MIXINS`

Automatically add mixins to specific wagtail to ion models. (For more information see __4. Available Hooks__)

Example:

```python
WAGTAIL_TO_ION_MODEL_MIXINS = {
    'Language': (
        'some_app.models.SomeMixinClass',
    ),
}
```

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

### `ION_COLLECTION_MODEL`

Defaults to `wagtail_to_ion.Collection`, but can be overridden to allow for collections to hold
additional metadata. If you want to use your own collection class, see details below.

## 4. Available hooks

### Collection model

The collection model is fully overrideable to allow for additional metadata to be included in
the collections. Because of this you should always use `get_collection_model()` instead of
importing `wagtail_to_ion.models.Collection` directly. The module will make sure that the
Collection class will not exist when using the override to crash any users that do not do that.

To create your own collection class inherit from
`wagtail_to_ion.models.abstract.AbstractCollection`

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
