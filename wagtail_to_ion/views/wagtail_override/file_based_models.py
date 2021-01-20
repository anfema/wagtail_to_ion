# Copyright © 2017 anfema GmbH. All rights reserved.
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.translation import ugettext as _
from django.db.models import ProtectedError
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.encoding import force_text
from django.views.decorators.vary import vary_on_headers
from django.template.loader import render_to_string
from django.urls import reverse

from wagtail.core.models import Collection
from wagtail.admin import messages
from wagtail.admin.auth import PermissionPolicyChecker, permission_denied
from wagtail.images import get_image_model
from wagtail.images.forms import get_image_form
from wagtail.images.fields import ALLOWED_EXTENSIONS
from wagtail.images.permissions import permission_policy
from wagtailmedia.models import get_media_model
from wagtail.images.views.multiple import get_image_edit_form
from wagtail.search.backends import get_search_backends
from wagtail.documents.forms import get_document_form, get_document_multi_form
from wagtail.documents import get_document_model

from wagtailmedia.forms import get_media_form


permission_checker = PermissionPolicyChecker(permission_policy)


@permission_checker.require('add')
@vary_on_headers('X-Requested-With')
def add_image(request):
    Image = get_image_model()
    ImageForm = get_image_form(Image)

    collections = permission_policy.collections_user_has_permission_for(request.user, 'add')
    if len(collections) > 1:
        collections_to_choose = collections
    else:
        # no need to show a collections chooser
        collections_to_choose = None

    if request.method == 'POST':
        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if not request.FILES:
            return HttpResponseBadRequest("Must upload a file")

        # Build a form for validation
        form = ImageForm({
            'title': request.FILES['files[]'].name,
            'collection': request.POST.get('collection'),
        }, {
            'file': request.FILES['files[]'],
        }, user=request.user)

        if form.is_valid():
            # Save it
            image = form.save(commit=False)
            image.uploaded_by_user = request.user
            image.file_size = image.file.size
            image.file.seek(0)
            image._set_file_hash(image.file.read())
            image.file.seek(0)
            image.save()

            # Success! Send back an edit form for this image to the user
            return JsonResponse({
                'success': True,
                'image_id': int(image.id),
                'form': render_to_string('wagtailimages/multiple/edit_form.html', {
                    'image': image,
                    'form': get_image_edit_form(Image)(
                        instance=image, prefix='image-%d' % image.id, user=request.user
                    ),
                }, request=request),
            })
        else:
            # Validation error
            return JsonResponse({
                'success': False,

                # https://github.com/django/django/blob/stable/1.6.x/django/forms/util.py#L45
                'error_message': '\n'.join(['\n'.join([force_text(i) for i in v]) for k, v in form.errors.items()]),
            })
    else:
        form = ImageForm(user=request.user)

    return TemplateResponse(request, 'wagtailimages/multiple/add.html', {
        'max_filesize': form.fields['file'].max_upload_size,
        'help_text': form.fields['file'].help_text,
        'allowed_extensions': ALLOWED_EXTENSIONS,
        'error_max_file_size': form.fields['file'].error_messages['file_too_large_unknown_size'],
        'error_accepted_file_types': form.fields['file'].error_messages['invalid_image'],
        'collections': collections_to_choose,
    })


@permission_checker.require('delete')
def delete_image(request, image_id):
    image = get_object_or_404(get_image_model(), id=image_id)

    if not permission_policy.user_has_permission_for_instance(request.user, 'delete', image):
        return permission_denied(request)

    if request.method == 'POST':
        try:
            image.delete()
        except ProtectedError as e:
            messages.error(request, _(e.args[0]))
        else:
            messages.success(request, _("Image '{0}' deleted.").format(image.title))
            return redirect('wagtailimages:index')

    return TemplateResponse(request, "wagtailimages/images/confirm_delete.html", {
        'image': image,
    })


@permission_checker.require('add')
def add_media(request, media_type):
    Media = get_media_model()
    MediaForm = get_media_form(Media)

    if request.POST:
        media = Media(uploaded_by_user=request.user, type=media_type)
        form = MediaForm(request.POST, request.FILES, instance=media, user=request.user)
        if form.is_valid():
            form.save()

            # Reindex the media entry to make sure all tags are indexed
            for backend in get_search_backends():
                backend.add(media)

            messages.success(request, _("Media file '{0}' added.").format(media.title), buttons=[
                messages.button(reverse('wagtailmedia:edit', args=(media.id,)), _('Edit'))
            ])
            return redirect('wagtailmedia:index')
        else:
            messages.error(request, _("The media file could not be saved due to errors."))
    else:
        media = Media(uploaded_by_user=request.user, type=media_type)
        form = MediaForm(user=request.user, instance=media)

    return TemplateResponse(request, "wagtailmedia/media/add.html", {
        'form': form,
        'media_type': media_type,
    })


@permission_checker.require('delete')
def delete_media(request, media_id):
    Media = get_media_model()
    media = get_object_or_404(Media, id=media_id)

    if not permission_policy.user_has_permission_for_instance(request.user, 'delete', media):
        return permission_denied(request)

    if request.POST:
        try:
            media.delete()
        except ProtectedError as e:
            messages.error(request, _(e.args[0]))
        else:
            messages.success(request, _("Media file '{0}' deleted.").format(media.title))
            return redirect('wagtailmedia:index')

    return TemplateResponse(request, "wagtailmedia/media/confirm_delete.html", {
        'media': media,
    })


@permission_checker.require('add')
@vary_on_headers('X-Requested-With')
def add_document(request):
    Document = get_document_model()
    DocumentForm = get_document_form(Document)
    DocumentMultiForm = get_document_multi_form(Document)

    collections = permission_policy.collections_user_has_permission_for(request.user, 'add')
    if len(collections) > 1:
        collections_to_choose = collections
    else:
        # no need to show a collections chooser
        collections_to_choose = None

    if request.method == 'POST':
        if not request.is_ajax():
            return HttpResponseBadRequest("Cannot POST to this view without AJAX")

        if not request.FILES:
            return HttpResponseBadRequest("Must upload a file")

        # Build a form for validation
        form = DocumentForm({
            'title': request.FILES['files[]'].name,
            'collection': request.POST.get('collection'),
        }, {
            'file': request.FILES['files[]']
        }, user=request.user)

        if form.is_valid():
            # Save it
            doc = form.save(commit=False)
            doc.uploaded_by_user = request.user
            doc.file_size = doc.file.size

            # Set new document file hash
            doc.file.seek(0)
            doc._set_file_hash(doc.file.read())
            doc.file.seek(0)

            doc.save()

            # Success! Send back an edit form for this document to the user
            return JsonResponse({
                'success': True,
                'doc_id': int(doc.id),
                'form': render_to_string('wagtaildocs/multiple/edit_form.html', {
                    'doc': doc,
                    'form': DocumentMultiForm(
                        instance=doc, prefix='doc-%d' % doc.id, user=request.user
                    ),
                }, request=request),
            })
        else:
            # Validation error
            return JsonResponse({
                'success': False,

                # https://github.com/django/django/blob/stable/1.6.x/django/forms/util.py#L45
                'error_message': '\n'.join(['\n'.join([force_text(i) for i in v]) for k, v in form.errors.items()]),
            })
    else:
        form = DocumentForm(user=request.user)

    return TemplateResponse(request, 'wagtaildocs/multiple/add.html', {
        'help_text': form.fields['file'].help_text,
        'collections': collections_to_choose,
    })
