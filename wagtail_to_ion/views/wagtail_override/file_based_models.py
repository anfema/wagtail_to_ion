from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy

from wagtail.admin import messages
from wagtail.admin.auth import PermissionPolicyChecker
from wagtail.documents import get_document_model
from wagtail.documents.permissions import permission_policy as document_permission_policy
from wagtail.documents.views.documents import delete as document_delete_view
from wagtail.images import get_image_model
from wagtail.images.permissions import permission_policy as image_permission_policy
from wagtail.images.views.images import delete as image_delete_view
from wagtailmedia.models import get_media_model
from wagtailmedia.permissions import permission_policy as media_permission_policy
from wagtailmedia.views.media import delete as media_delete_view


document_permission_checker = PermissionPolicyChecker(document_permission_policy)
image_permission_checker = PermissionPolicyChecker(image_permission_policy)
media_permission_checker = PermissionPolicyChecker(media_permission_policy)

MESSAGE = gettext_lazy('Cannot delete object if used by any page')


@image_permission_checker.require('delete')
def image_safe_delete(request, image_id):
    image = get_object_or_404(get_image_model(), pk=image_id)
    if image.get_usage().exists():
        messages.error(request, MESSAGE)
        return redirect('wagtailimages:edit', image_id=image_id)
    return image_delete_view(request, image_id)


@document_permission_checker.require('delete')
def document_safe_delete(request, document_id):
    document = get_object_or_404(get_document_model(), pk=document_id)
    if document.get_usage().exists():
        messages.error(request, MESSAGE)
        return redirect('wagtaildocs:edit', document_id=document_id)
    return document_delete_view(request, document_id)


@media_permission_checker.require('delete')
def media_safe_delete(request, media_id):
    media = get_object_or_404(get_media_model(), pk=media_id)
    if media.get_usage().exists():
        messages.error(request, MESSAGE)
        return redirect('wagtailmedia:edit', media_id)
    return media_delete_view(request, media_id)
