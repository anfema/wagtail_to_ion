# Copyright © 2017 anfema GmbH. All rights reserved.
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from wagtail.core import hooks
from wagtail.admin import messages
from wagtail.admin.forms.pages import CopyForm
from wagtail.admin.widgets import Button
from wagtail.admin.auth import PermissionPolicyChecker, user_has_any_page_permission, user_passes_test
from wagtail.images.permissions import permission_policy
from wagtail.core.models import Page
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request


permission_checker = PermissionPolicyChecker(permission_policy)


# add publish button to dropdown menu
@hooks.register('register_page_listing_more_buttons')
def page_listing_more_buttons(page, page_perms, is_parent=False, next_url=None):
    if page_perms.can_publish():
        yield Button(
            'Publish with children',
            reverse('publish-with-children', args=(page.id,)),
            priority=60
        )


def publish_parent_tree(page):
    '''
    get upper tree of page to prevent having unpublished parent pages of a published page
    '''
    if page.get_parent().title != 'Root':
        if not page.get_parent().live and page.get_parent().has_unpublished_changes:
            revision = page.get_parent().get_latest_revision()
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
    #     raise PermissionDenied

    next_url = get_valid_next_url_from_request(request)

    if request.method == 'POST':
        include_descendants = True

        for fn in hooks.get_hooks('before_unpublish_page'):
            result = fn(request, page)
            if hasattr(result, 'status_code'):
                return result

        page.unpublish(user=request.user)

        if include_descendants:
            live_descendant_pages = page.get_descendants().live().specific()
            for live_descendant_page in live_descendant_pages:
                # if user_perms.for_page(live_descendant_page).can_unpublish():
                live_descendant_page.unpublish()

        for fn in hooks.get_hooks('after_unpublish_page'):
            result = fn(request, page)
            if hasattr(result, 'status_code'):
                return result

        messages.success(request, _("Page '{0}' unpublished.").format(page.get_admin_display_title()), buttons=[
            messages.button(reverse('wagtailadmin_pages:edit', args=(page.id,)), _('Edit'))
        ])

        if next_url:
            return redirect(next_url)
        return redirect('wagtailadmin_explore', page.get_parent().id)

    return TemplateResponse(request, 'wagtailadmin/pages/confirm_unpublish.html', {
        'page': page,
        'next': next_url,
        # 'live_descendant_count': page.get_descendants().live().count(),
    })


def ion_publish_with_children(request, page_id):
    page = get_object_or_404(Page, id=page_id)
    page_perms = page.permissions_for_user(request.user)

    if not page_perms.can_publish():
        raise PermissionDenied

    revision = page.get_latest_revision()
    unpublished_descendant_pages = page.get_descendants().filter(live=False).specific()

    next_url = get_valid_next_url_from_request(request)

    if request.method == 'POST':
        revision.publish()

        for unpublished_descendant_page in unpublished_descendant_pages:
            unpublished_descendant_revision = unpublished_descendant_page.get_latest_revision()
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


class AutoTitleCopyForm(CopyForm):
    """
    Copy form for pages with auto-generated title & slug fields.

    The `new_title` & `new_slug` fields are marked as optional and can be omitted from the form.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for omitted_field in ('new_title', 'new_slug'):
            self.fields[omitted_field].required = False
            self.fields[omitted_field].initial = ''

    def clean(self):
        # generate `new_title` & `new_slug`:
        # only required for copy as alias functionality; new title & slug for standard copy operations are handled
        # in `AbstractIonPage.copy()`
        new_title = self.page.specific_class.generate_page_title()
        return {
            **super().clean(),
            'new_title': new_title,
            'new_slug': slugify(new_title),
        }


# Copy of the wagtail `wagtail.admin.views.pages.copy.copy()` view
#
# Adjustments:
#  - `CopyForm` replaced by `AutoTitleCopyForm`
#  - disabled `before_copy_page` hook handling
#  - replaced template
#  - fix crash when alias field is not available in form:
#    replaced `form.cleaned_data['alias']` with `form.cleaned_data.get('alias')`
#
@user_passes_test(user_has_any_page_permission)
def ion_copy_auto_title(request, page_id):
    page = Page.objects.get(id=page_id)

    # Parent page defaults to parent of source page
    parent_page = page.get_parent()

    # Check if the user has permission to publish subpages on the parent
    can_publish = parent_page.permissions_for_user(request.user).can_publish_subpage()

    # Create the form
    form = AutoTitleCopyForm(request.POST or None, user=request.user, page=page, can_publish=can_publish)

    next_url = get_valid_next_url_from_request(request)

    # for fn in hooks.get_hooks('before_copy_page'):
    #     result = fn(request, page)
    #     if hasattr(result, 'status_code'):
    #         return result

    # Check if user is submitting
    if request.method == 'POST':
        # Prefill parent_page in case the form is invalid (as prepopulated value for the form field,
        # because ModelChoiceField seems to not fall back to the user given value)
        parent_page = Page.objects.get(id=request.POST['new_parent_page'])

        if form.is_valid():
            # Receive the parent page (this should never be empty)
            if form.cleaned_data['new_parent_page']:
                parent_page = form.cleaned_data['new_parent_page']

            if not page.permissions_for_user(request.user).can_copy_to(parent_page,
                                                                       form.cleaned_data.get('copy_subpages')):
                raise PermissionDenied

            # Re-check if the user has permission to publish subpages on the new parent
            can_publish = parent_page.permissions_for_user(request.user).can_publish_subpage()
            keep_live = can_publish and form.cleaned_data.get('publish_copies')

            # Copy the page
            # Note that only users who can publish in the new parent page can create an alias.
            # This is because alias pages must always match their original page's state.
            if can_publish and form.cleaned_data.get('alias'):
                new_page = page.specific.create_alias(
                    recursive=form.cleaned_data.get('copy_subpages'),
                    parent=parent_page,
                    update_slug=form.cleaned_data['new_slug'],
                    user=request.user,
                )
            else:
                new_page = page.specific.copy(
                    recursive=form.cleaned_data.get('copy_subpages'),
                    to=parent_page,
                    update_attrs={
                        'title': form.cleaned_data['new_title'],
                        'slug': form.cleaned_data['new_slug'],
                    },
                    keep_live=keep_live,
                    user=request.user,
                )

            # Give a success message back to the user
            if form.cleaned_data.get('copy_subpages'):
                messages.success(
                    request,
                    _("Page '{0}' and {1} subpages copied.").format(page.get_admin_display_title(),
                                                                    new_page.get_descendants().count())
                )
            else:
                messages.success(request, _("Page '{0}' copied.").format(page.get_admin_display_title()))

            for fn in hooks.get_hooks('after_copy_page'):
                result = fn(request, page, new_page)
                if hasattr(result, 'status_code'):
                    return result

            # Redirect to explore of parent page
            if next_url:
                return redirect(next_url)
            return redirect('wagtailadmin_explore', parent_page.id)

    return TemplateResponse(request, 'wagtailadmin/pages/copy_auto_title.html', {
        'page': page,
        'form': form,
        'next': next_url,
    })


@hooks.register('before_copy_page')
def use_auto_title_copy_form(request, page):
    if getattr(page.specific_class, 'ion_generate_page_title', None):
        return ion_copy_auto_title(request, page.pk)
