# Copyright © 2017 anfema GmbH. All rights reserved.
import json
import os

from django.urls import reverse
from rest_framework.renderers import JSONRenderer

from wagtail_to_ion.tar import TarWriter
from wagtail_to_ion.conf import settings
from wagtail_to_ion.serializers import DynamicPageDetailSerializer
from wagtail_to_ion.utils import get_collection_for_page


def build_url(request, locale_code, page, variation='default'):
    url = reverse('v1:page-detail', kwargs={
        'locale': locale_code,
        'collection': get_collection_for_page(page),
        'slug': page.slug,
    })
    return request.build_absolute_uri(url) + "?variation={}".format(variation)


def collect_files(request, self, page, collected_files, user):
    spec = page.specific

    for field in spec.content_panels:
        if field.__class__.__name__ == 'MultiFieldPanel':
            continue
        sub_field = getattr(spec, field.field_name)
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
            sub_field = getattr(spec, field.field_name)
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
                item['path'] = file.file.path
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


def make_page_tar(page, locale, request, content_serializer=DynamicPageDetailSerializer):
    # build content json
    content = content_serializer(instance=page, context={'request': request})
    content = JSONRenderer().render(content.data)
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
    collect_files(request, page, page, collected_files, user)
    i = {}
    for f in collected_files:
        if f["page"] not in i:
            i[f["page"]] = 0
        f['tar_name'] = "pages/" + f["page"] + "/" + str(i[f["page"]])
        i[f["page"]] = i[f["page"]] + 1
        url = f["url"]
        if "variation" in request.GET:
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
    tar.add_data(index_file, "index.json")

    # add toplevel data
    tar.add_dir('pages')
    tar.add_data(content, "pages/" + page.slug + ".json")

    # add all files
    for f in collected_files:
        tar.add_file(f['path'], f['tar_name'])

    return tar.data()


#
# Collection TAR
#
def make_tar(pages, updated_pages, locale_code, request, content_serializer=DynamicPageDetailSerializer):
    # fetch all pages
    index_file = []
    content = []
    collected_files = []

    for page in pages:
        index, files = make_pagemeta(page, locale_code, request)
        index_file.extend(index)
        if page in updated_pages:
            page_content = make_pagecontent(page, request, content_serializer=content_serializer)
            content.extend(page_content)
            collected_files.extend(files)

    # de-duplicate
    collected_files = dedup_files(collected_files)
    index_file = dedup_index(index_file)

    # create tar writer instance
    tar = TarWriter()

    # index file
    index_file = json.dumps(index_file).encode("utf-8")
    tar.add_data(index_file, "index.json")

    tar.add_dir('pages')

    # add children data
    used_dirs = [os.path.dirname(f['tar_name']) for f in collected_files]
    for page in content:
        tar.add_data(page['json'], 'pages/' + page['name'] + ".json", date=page['last_published'])
        page_dir = 'pages/' + page['name']
        if page_dir in used_dirs:
            tar.add_dir(page_dir, date=page['last_published'])

    # add all files
    for f in collected_files:
        tar.add_file(f['path'], f['tar_name'])

    return tar.data()


def make_pagemeta(page, locale_code, request):
    user = request.user

    # create index
    index_file = []
    url = build_url(request, locale_code, page, variation=request.GET.get('variation', 'default'))

    index_file.append({
        "url": url,
        "name": "pages/" + page.slug + ".json"
    })

    # collect all files
    collected_files = []
    collect_files(request, page, page, collected_files, user)
    i = {}
    for f in collected_files:
        if f["page"] not in i:
            i[f["page"]] = 0
        f['tar_name'] = "pages/" + f["page"] + "/" + str(i[f["page"]])
        i[f["page"]] = i[f["page"]] + 1
        index_file.append({
            "url": request.build_absolute_uri(f['url']),
            "name": f['tar_name'],
            "checksum": f['checksum']
        })

    return index_file, collected_files


def make_pagecontent(page, request, content_serializer=DynamicPageDetailSerializer):
    # build content json
    content = content_serializer(instance=page, context={'request': request})  # FIXME: may be overridden

    content = [{
        "json": (JSONRenderer().render(content.data).decode('utf-8')).encode('utf-8'),
        "name": page.slug,
        "last_published": page.last_published_at
    }]

    return content
