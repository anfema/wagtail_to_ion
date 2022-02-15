# Copyright © 2017 anfema GmbH. All rights reserved.
import json
import os

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils.module_loading import import_string

from rest_framework.renderers import JSONRenderer

from wagtail_to_ion.tar import TarWriter, TarData, TarDir, TarStorageFile
from wagtail_to_ion.conf import settings
from wagtail_to_ion.serializers import DynamicPageDetailSerializer
from wagtail_to_ion.serializers.ion.base import IonSerializerAttachedFileInterface
from wagtail_to_ion.serializers.pages import get_wagtail_panels_and_extra_fields
from wagtail_to_ion.utils import get_collection_for_page


if settings.ION_ARCHIVE_BUILD_URL_FUNCTION is not None:
    try:
        build_url = import_string(settings.ION_ARCHIVE_BUILD_URL_FUNCTION)
    except ImportError:
        raise ImproperlyConfigured(f"The function {settings.ION_ARCHIVE_BUILD_URL_FUNCTION} couldn't be imported.")
else:
    def build_url(request, locale_code, page, variation='default'):
        url = reverse('v1:page-detail', kwargs={
            'locale': locale_code,
            'collection': get_collection_for_page(page),
            'slug': page.slug,
        })
        return request.build_absolute_uri(url) + "?variation={}".format(variation)


def _collect_files_from_serializer_tree(ion_serializer):
    if isinstance(ion_serializer, IonSerializerAttachedFileInterface):
        yield from ion_serializer.attached_files
    if hasattr(ion_serializer, 'children'):
        for child_serializer in ion_serializer.children:
            yield from _collect_files_from_serializer_tree(child_serializer)


def collect_files_from_tree(page, request, ion_serializer_tree):
    for file_container in _collect_files_from_serializer_tree(ion_serializer_tree):
        yield {
            'url': request.build_absolute_uri(file_container.url),
            'page': page.slug,
            'checksum': file_container.checksum,
            'file': file_container.file,
        }


def collect_files(request, page, collected_files, user):
    for _, field_name, instance in get_wagtail_panels_and_extra_fields(page):
        sub_field = getattr(instance, field_name)
        if sub_field.__class__.__name__ in ['IonDocument', 'IonMedia'] and sub_field.include_in_archive:
            items = {sub_field.file.url: sub_field}
        elif sub_field.__class__.__name__ == 'IonImage' and sub_field.include_in_archive:
            try:
                items = {request.build_absolute_uri(sub_field.archive_rendition.url): sub_field.archive_rendition}
            except (ValueError, AttributeError) as e:
                if settings.ION_ALLOW_MISSING_FILES is True:
                    items = {}
                else:
                    raise e
        else:
            items = {}
        if sub_field.__class__.__name__ == 'StreamFieldPanel':
            sub_field = getattr(instance, field_name)  # TODO: required?
            for content in sub_field:
                if content.__class__.__name__ in ['IonDocument', 'IonMedia'] and sub_field.include_in_archive:
                    items[content.file.url] = content
                elif content.__class__.__name__ == 'IonImage' and sub_field.include_in_archive:
                    try:
                        items[request.build_absolute_uri(content.archive_rendition.url)] = content.archive_rendition
                    except (ValueError, AttributeError) as e:
                        if settings.ION_ALLOW_MISSING_FILES is True:
                            items = {}
                        else:
                            raise e
        if items:
            for (key, file) in items.items():
                item = {}
                item['url'] = key
                item['page'] = page.slug
                item['checksum'] = file.checksum
                try:
                    item['path'] = file.file.path
                except NotImplementedError:
                    item['path'] = None
                item['file'] = file.file
                collected_files.append(item)


def dedup_files(collected_files):
    # dedup files
    dedup_file_list = []
    for collected_file in collected_files:
        found = False
        for existing_file in dedup_file_list:
            if collected_file["url"] == existing_file["url"]:
                found = True
                break
        if not found:
            dedup_file_list.append(collected_file)
    return dedup_file_list


def dedup_index(index_file):
    # dedup index file
    dedup_index_file = []
    for entry in index_file:
        found = False
        for existing_entry in dedup_index_file:
            if entry["url"] == existing_entry["url"]:
                found = True
                break
        if not found:
            dedup_index_file.append(entry)
    return dedup_index_file


#
# Page TAR
#

def collect_children(page, user=None):
    '''
    :param page: given page
    :param user: User instance
    :return: array of whole children tree of given page
    '''
    result = []
    if settings.GET_PAGES_BY_USER:
        for child in page.get_children_by_user(user):
            result.append(child)
            result.extend(collect_children(child, user))
    else:
        for child in page.get_children():
            result.append(child)
            result.extend(collect_children(child))
    return result


def make_page_tar(page, locale, request, content_serializer=DynamicPageDetailSerializer) -> TarWriter:
    # build content json
    content = content_serializer(instance=page, context={'request': request})
    content_json = JSONRenderer().render(content.data)
    user = request.user

    # create index
    index_file = []
    url = build_url(request, locale, page, variation=request.GET.get('variation', 'default'))

    index_file.append({
        "url": url,
        "name": "pages/" + page.slug + ".json"
    })

    # collect all files
    collected_files = []
    collected_files.extend(collect_files_from_tree(page, request, content.ion_serializer_tree))
    i = {}
    for f in collected_files:
        if f["page"] not in i:
            i[f["page"]] = 0
        f['tar_name'] = "pages/" + f["page"] + "/" + str(i[f["page"]])
        i[f["page"]] = i[f["page"]] + 1
        url = f["url"]
        if "variation" in request.GET and url.startswith(request.build_absolute_uri('/')):
            url += "?variation=" + request.GET["variation"]
        index_file.append({
            "url": url,
            "name": f['tar_name'],
            "checksum": f['checksum']
        })

    # de-duplicate
    collected_files = dedup_files(collected_files)
    index_file = dedup_index(index_file)

    # create tar writer instance
    tar = TarWriter()

    # index file
    index_file = json.dumps(index_file).encode("utf-8")
    tar.add_item(TarData("index.json", index_file))

    # add toplevel data
    tar.add_item(TarDir("pages"))
    tar.add_item(TarData(f"pages/{page.slug}.json", content_json))

    # add all files
    for f in collected_files:
        tar.add_item(TarStorageFile(f['file'], f['tar_name']))

    return tar


#
# Collection TAR
#
def make_tar(pages, updated_pages, locale_code, request, content_serializer=DynamicPageDetailSerializer) -> TarWriter:
    # fetch all pages
    index_file = []
    content = []
    collected_files = []

    for page in pages:
        index = make_pagemeta(page, locale_code, request)
        index_file.extend(index)
        if page in updated_pages:
            page_content, files = make_pagecontent(page, request, content_serializer=content_serializer)
            content.extend(page_content)
            collected_files.extend(files)

    i = {}
    for f in collected_files:
        if f['page'] not in i:
            i[f['page']] = 0
        f['tar_name'] = 'pages/' + f['page'] + '/' + str(i[f['page']])
        i[f['page']] = i[f['page']] + 1
        index_file.append({
            'url': request.build_absolute_uri(f['url']),
            'name': f['tar_name'],
            'checksum': f['checksum'],
        })

    # de-duplicate
    collected_files = dedup_files(collected_files)
    index_file = dedup_index(index_file)

    # create tar writer instance
    tar = TarWriter()

    # index file
    index_file = json.dumps(index_file).encode("utf-8")
    tar.add_item(TarData("index.json", index_file))

    tar.add_item(TarDir("pages"))

    # add children data
    used_dirs = [os.path.dirname(f['tar_name']) for f in collected_files]
    for page in content:
        tar.add_item(TarData(f"pages/{page['name']}.json", page['json'], date=page['last_published']))
        page_dir = 'pages/' + page['name']
        if page_dir in used_dirs:
            tar.add_item(TarDir(page_dir, date=page['last_published']))

    # add all files
    for f in collected_files:
        tar.add_item(TarStorageFile(f['file'], f['tar_name']))

    return tar


def make_pagemeta(page, locale_code, request):
    user = request.user

    # create index
    index_file = []
    url = build_url(request, locale_code, page, variation=request.GET.get('variation', 'default'))

    index_file.append({
        "url": url,
        "name": "pages/" + page.slug + ".json"
    })

    return index_file


def make_pagecontent(page, request, content_serializer=DynamicPageDetailSerializer):
    # build content json
    content = content_serializer(instance=page, context={'request': request})  # FIXME: may be overridden

    content_dict = [{
        "json": (JSONRenderer().render(content.data).decode('utf-8')).encode('utf-8'),
        "name": page.slug,
        "last_published": page.last_published_at
    }]

    return content_dict, collect_files_from_tree(page, request, content.ion_serializer_tree)
