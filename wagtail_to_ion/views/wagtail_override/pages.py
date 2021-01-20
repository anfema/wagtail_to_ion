# Copyright © 2017 anfema GmbH. All rights reserved.
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.translation import ugettext as _
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from wagtail.core import hooks
from wagtail.admin import messages
from wagtail.admin.widgets import Button
from wagtail.admin.auth import PermissionPolicyChecker
from wagtail.images.permissions import permission_policy
from wagtail.core.models import Page, PageRevision
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request


permission_checker = PermissionPolicyChecker(permission_policy)


# add publish button to dropdown menu
@hooks.register('register_page_listing_more_buttons')
def page_listing_more_buttons(page, page_perms, is_parent=False):
    if page_perms.can_publish():
        yield Button(
            'Publish',
            '/cms/pages/{page_id}/publish-with-children/'.format(page_id=page.id),
            priority=60
        )


def publish_parent_tree(page):
    '''
    get upper tree of page to prevent having unpublished parent pages of a published page
    '''
    if page.get_parent().title != 'Root':
        if not page.get_parent().live and page.get_parent().has_unpublished_changes:
            revision = PageRevision.objects.filter(page=page.get_parent()).latest('created_at')
            revision.publish()
            return publish_parent_tree(page.get_parent())


def get_unpublished_parent(page):
    '''
    get upper tree of page to get unpublished parent pages of a to publish page
    '''
    if page.get_parent().title != 'Root':
        if not page.get_parent().live and page.get_parent().has_unpublished_changes:
            return True
        return get_unpublished_parent(page.get_parent())


# override wagtail.admin.views.pages unpublish method to remove 'Unpublish' checkbox for subpages, since we
# want to unpublish them automatically
def ion_unpublish(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific

    # TODO permission handling postponed
    # user_perms = UserPagePermissionsProxy(request.user)
    # if not user_perms.for_page(page).can_unpublish():
    # 	raise PermissionDenied

    next_url = get_valid_next_url_from_request(request)

    if request.method == 'POST':
        include_descendants = True

        page.unpublish()

        if include_descendants:
            live_descendant_pages = page.get_descendants().live().specific()
            for live_descendant_page in live_descendant_pages:
                # if user_perms.for_page(live_descendant_page).can_unpublish():
                live_descendant_page.unpublish()

        messages.success(request, _("Page '{0}' unpublished.").format(page.get_admin_display_title()), buttons=[
            messages.button(reverse('wagtailadmin_pages:edit', args=(page.id,)), _('Edit'))
        ])

        if next_url:
            return redirect(next_url)
        return redirect('wagtailadmin_explore', page.get_parent().id)

    return TemplateResponse(request, 'wagtailadmin/pages/confirm_unpublish.html', {
        'page': page,
        'next': next_url,
    })


def ion_publish_with_children(request, page_id):
    page = get_object_or_404(Page, id=page_id)
    page_perms = page.permissions_for_user(request.user)
    
    if not page_perms.can_publish():
        raise PermissionDenied

    revision = PageRevision.objects.filter(page=page).latest('created_at')
    unpublished_descendant_pages = page.get_descendants().filter(live=False).specific()

    next_url = get_valid_next_url_from_request(request)

    if request.method == 'POST':
        revision.publish()

        for unpublished_descendant_page in unpublished_descendant_pages:
            unpublished_descendant_revision = PageRevision.objects.filter(page=unpublished_descendant_page).latest('created_at')
            unpublished_descendant_revision.publish()

        messages.success(request, _("Publishing successful."))

        if next_url:
            return redirect(next_url)
        return redirect('wagtailadmin_explore', page.get_parent().id)

    return TemplateResponse(request, 'wagtailadmin/pages/publish_with_children.html', {
        'page': page,
        'next': next_url,
        'unpublished_descendants': unpublished_descendant_pages,
        'unpublished_descendant_count': page.get_descendants().not_live().count(),
    })
