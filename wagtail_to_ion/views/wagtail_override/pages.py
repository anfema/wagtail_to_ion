# Copyright © 2017 anfema GmbH. All rights reserved.
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import ugettext as _
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils import timezone
from django.utils.http import urlquote

from wagtail.core import hooks
from wagtail.admin import messages, signals
from wagtail.admin.action_menu import PageActionMenu
from wagtail.admin.mail import send_notification
from wagtail.admin.widgets import Button, ButtonWithDropdownFromHook, PageListingButton
from wagtail.admin.auth import PermissionPolicyChecker
from wagtail.images.permissions import permission_policy
from wagtail.core.models import Page, PageRevision, GroupPagePermission
from wagtail.admin.views.pages import get_valid_next_url_from_request

from wagtail_to_ion.conf import settings
from wagtail_to_ion.signals import page_created

permission_checker = PermissionPolicyChecker(permission_policy)


# override wagtail 'register_page_listing_buttons' hook to remove unneeded buttons
def page_listing_buttons(page, page_perms, is_parent=False):
    if page_perms.can_edit():
        yield PageListingButton(
            _('Edit'),
            reverse('wagtailadmin_pages:edit', args=[page.id]),
            attrs={'title': _("Edit '{title}'").format(title=page.get_admin_display_title())},
            priority=10
        )

    if page_perms.can_add_subpage():
        if is_parent:
            yield Button(
                _('Add child page'),
                reverse('wagtailadmin_pages:add_subpage', args=[page.id]),
                attrs={'title': _("Add a child page to '{title}' ").format(title=page.get_admin_display_title())},
                classes={'button', 'button-small', 'bicolor', 'icon', 'white', 'icon-plus'},
                priority=40
            )
        else:
            yield PageListingButton(
                _('Add child page'),
                reverse('wagtailadmin_pages:add_subpage', args=[page.id]),
                attrs={'title': _("Add a child page to '{title}' ").format(title=page.get_admin_display_title())},
                priority=40
            )
    if page_perms.user.is_superuser or ('add' in page_perms.permissions):
        yield ButtonWithDropdownFromHook(
            _('More'),
            hook_name='register_page_listing_more_buttons',
            page=page,
            page_perms=page_perms,
            is_parent=is_parent,
            attrs={'target': '_blank',
                    'title': _("View more options for '{title}'").format(title=page.get_admin_display_title())},
            priority=50
        )


# add publish button to dropdown menu
@hooks.register('register_page_listing_more_buttons')
def page_listing_more_buttons(page, page_perms, is_parent=False):
    if page_perms.can_publish():
        yield Button(
            'Publish',
            '/cms/pages/{page_id}/publish-with-children/'.format(page_id=page.id),
            priority=60
        )


# WARNING: on wagtail update, check this code
hooks._hooks['register_page_listing_buttons'] = [(page_listing_buttons, 0)]


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


# override wagtail.admin.views.pages create method to remove 'View Draft' button
def ion_create(request, content_type_app_name, content_type_model_name, parent_page_id):
    parent_page = get_object_or_404(Page, id=parent_page_id).specific
    parent_page_perms = parent_page.permissions_for_user(request.user)
    if not parent_page_perms.can_add_subpage():
        raise PermissionDenied

    try:
        content_type = ContentType.objects.get_by_natural_key(content_type_app_name, content_type_model_name)
    except ContentType.DoesNotExist:
        raise Http404

    # Get class
    page_class = content_type.model_class()

    # Make sure the class is a descendant of Page
    if not issubclass(page_class, Page):
        raise Http404

    # page must be in the list of allowed subpage types for this parent ID
    if page_class not in parent_page.creatable_subpage_models():
        raise PermissionDenied

    if not page_class.can_create_at(parent_page):
        raise PermissionDenied

    for fn in hooks.get_hooks('before_create_page'):
        result = fn(request, parent_page, page_class)
        if hasattr(result, 'status_code'):
            return result

    page = page_class(owner=request.user)
    edit_handler = page_class.get_edit_handler()
    edit_handler = edit_handler.bind_to(instance=page, request=request)
    form_class = edit_handler.get_form_class()

    next_url = get_valid_next_url_from_request(request)

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=page,
                          parent_page=parent_page)

        if form.is_valid():
            page = form.save(commit=False)

            is_publishing = bool(request.POST.get('action-publish')) and parent_page_perms.can_publish_subpage()
            is_submitting = bool(request.POST.get('action-submit'))

            if not is_publishing:
                page.live = False

            # Save page
            parent_page.add_child(instance=page)
            page_created.send(sender=Page, request=request, page=page)

            # Save revision
            revision = page.save_revision(
                user=request.user,
                submitted_for_moderation=is_submitting,
            )

            # disable for create function for now
            # Publish
            # if is_publishing:
            # 	publish_parent_tree(page)
            # 	revision.publish()


            # if is_publishing:
            # 	if page.go_live_at and page.go_live_at > timezone.now():
            # 		messages.success(request, _("Page '{0}' created and scheduled for publishing.").format(
            # 			page.get_admin_display_title()), buttons=[
            # 			messages.button(reverse('wagtailadmin_pages:edit', args=(page.id,)), _('Edit'))
            # 		])
            # 	else:
            # 		messages.success(request, ("Page '{0}' created and published.").format(page.get_admin_display_title()), buttons=[
            # 			# This button is removed, since we are not using the frontend feature
            # 			# messages.button(page.url, _('View live'), new_window=True),
            # 			messages.button(reverse('wagtailadmin_pages:edit', args=(page.id,)), _('Edit'))
            # 		])

            # Notifications
            if is_submitting:
                messages.success(
                    request,
                    _("Page '{0}' created and submitted for moderation.").format(page.get_admin_display_title()),
                    buttons=[
                        # This button is removed, since we are not using the frontend feature
                        # messages.button(
                        # 	reverse('wagtailadmin_pages:view_draft', args=(page.id,)),
                        # 	_('View draft'),
                        # 	new_window=True
                        # ),
                        messages.button(
                            reverse('wagtailadmin_pages:edit', args=(page.id,)),
                            _('Edit')
                        )
                    ]
                )
                if not send_notification(page.get_latest_revision().id, 'submitted', request.user.pk):
                    messages.error(request, _("Failed to send notifications to moderators"))
            else:
                messages.success(request, _("Page '{0}' created.").format(page.get_admin_display_title()))

            for fn in hooks.get_hooks('after_create_page'):
                result = fn(request, page)
                if hasattr(result, 'status_code'):
                    return result

            if is_publishing or is_submitting:
                # we're done here
                if next_url:
                    # redirect back to 'next' url if present
                    return redirect(next_url)
                # redirect back to the explorer
                return redirect('wagtailadmin_explore', page.get_parent().id)
            else:
                # Just saving - remain on edit page for further edits
                target_url = reverse('wagtailadmin_pages:edit', args=[page.id])
                if next_url:
                    # Ensure the 'next' url is passed through again if present
                    target_url += '?next=%s' % urlquote(next_url)
                return redirect(target_url)
        else:
            messages.validation_error(
                request, _("The page could not be created due to validation errors"), form
            )
            edit_handler = edit_handler.bind_to(instance=page, request=request, form=form)
            has_unsaved_changes = True
    else:
        signals.init_new_page.send(sender=ion_create, page=page, parent=parent_page)
        form = form_class(instance=page, parent_page=parent_page)
        edit_handler = edit_handler.bind_to(instance=page, request=request, form=form)
        has_unsaved_changes = False

    return render(request, 'wagtailadmin/pages/create.html', {
        'content_type': content_type,
        'page_class': page_class,
        'parent_page': parent_page,
        'edit_handler': edit_handler,
        'action_menu': PageActionMenu(request, view='create', parent_page=parent_page),
        'preview_modes': page.preview_modes,
        'form': form,
        'next': next_url,
        'has_unsaved_changes': has_unsaved_changes,
    })


# override wagtail.admin.views.pages edit method to remove 'View Draft' button
def ion_edit(request, page_id):
    latest_revision = get_object_or_404(Page, id=page_id).get_latest_revision()
    page = get_object_or_404(Page, id=page_id).get_latest_revision_as_page()
    parent = page.get_parent()

    content_type = ContentType.objects.get_for_model(page)
    page_class = content_type.model_class()

    page_perms = page.permissions_for_user(request.user)
    if not page_perms.can_edit():
        raise PermissionDenied

    for fn in hooks.get_hooks('before_edit_page'):
        result = fn(request, page)
        if hasattr(result, 'status_code'):
            return result

    edit_handler = page_class.get_edit_handler()
    edit_handler = edit_handler.bind_to(instance=page, request=request)
    form_class = edit_handler.get_form_class()

    next_url = get_valid_next_url_from_request(request)

    has_unpublished_parents = get_unpublished_parent(page)

    errors_debug = None

    readonly_group = False
    if request.user.groups.filter(name__in=settings.ION_READ_ONLY_GROUPS).exists():
        readonly_group = True

    if request.method == 'POST' and not readonly_group:
        form = form_class(request.POST, request.FILES, instance=page,
                          parent_page=parent)

        if form.is_valid() and not page.locked:
            page = form.save(commit=False)

            is_publishing = bool(request.POST.get('action-publish')) and page_perms.can_publish()
            is_parent_publishing = bool(request.POST.get('action-publish-parents')) and page_perms.can_publish()
            is_submitting = bool(request.POST.get('action-submit'))
            is_reverting = bool(request.POST.get('revision'))

            # If a revision ID was passed in the form, get that revision so its
            # date can be referenced in notification messages
            if is_reverting:
                previous_revision = get_object_or_404(page.revisions, id=request.POST.get('revision'))

            # Save revision
            revision = page.save_revision(
                user=request.user,
                submitted_for_moderation=is_submitting,
            )

            # Publish Parents
            if is_parent_publishing:
                publish_parent_tree(page)

            # Publish
            if is_publishing:
                if get_unpublished_parent(page):
                    messages.warning(request,
                                     _("This page has unpublished parent(s). Please publish via the 'Publish Parent(s)' button below"),
                                     buttons=[
                                        messages.button(
                                            reverse('wagtailadmin_pages:edit', args=(page_id,)),
                                            _('Okay')
                                        )
                    ])

                    return redirect('wagtailadmin_pages:edit', page.id)

                revision.publish()

                # Need to reload the page because the URL may have changed, and we
                # need the up-to-date URL for the "View Live" button.
                page = page.specific_class.objects.get(pk=page.pk)

            # Notifications
            if is_parent_publishing:
                messages.success(request, _("Parent(s) of {} have been published".format(page.get_admin_display_title())))

            elif is_publishing:
                if page.go_live_at and page.go_live_at > timezone.now():
                    # Page has been scheduled for publishing in the future

                    if is_reverting:
                        message = _(
                            "Revision from {0} of page '{1}' has been scheduled for publishing."
                        ).format(
                            previous_revision.created_at.strftime("%d %b %Y %H:%M"),
                            page.get_admin_display_title()
                        )
                    else:
                        message = _(
                            "Page '{0}' has been scheduled for publishing."
                        ).format(
                            page.get_admin_display_title()
                        )

                    messages.success(request, message, buttons=[
                        messages.button(
                            reverse('wagtailadmin_pages:edit', args=(page.id,)),
                            _('Edit')
                        )
                    ])

                else:
                    # Page is being published now

                    if is_reverting:
                        message = _(
                            "Revision from {0} of page '{1}' has been published."
                        ).format(
                            previous_revision.created_at.strftime("%d %b %Y %H:%M"),
                            page.get_admin_display_title()
                        )
                    else:
                        message = _(
                            "Page '{0}' has been published."
                        ).format(
                            page.get_admin_display_title()
                        )

                    messages.success(request, message, buttons=[
                        # This button is removed, since we are not using the frontend feature
                        # messages.button(
                        # 	page.url,
                        # 	_('View live'),
                        # 	new_window=True
                        # ),
                        messages.button(
                            reverse('wagtailadmin_pages:edit', args=(page_id,)),
                            _('Edit')
                        )
                    ])

            elif is_submitting:

                message = _(
                    "Page '{0}' has been submitted for moderation."
                ).format(
                    page.get_admin_display_title()
                )

                messages.success(request, message, buttons=[
                    # This button is removed, since we are not using the frontend feature
                    # messages.button(
                    #     reverse('wagtailadmin_pages:view_draft', args=(page_id,)),
                    #     _('View draft'),
                    #     new_window=True
                    # ),
                    messages.button(
                        reverse('wagtailadmin_pages:edit', args=(page_id,)),
                        _('Edit')
                    )
                ])

                if not send_notification(page.get_latest_revision().id, 'submitted', request.user.pk):
                    messages.error(request, _("Failed to send notifications to moderators"))

            else:  # Saving

                if is_reverting:
                    message = _(
                        "Page '{0}' has been replaced with revision from {1}."
                    ).format(
                        page.get_admin_display_title(),
                        previous_revision.created_at.strftime("%d %b %Y %H:%M")
                    )
                else:
                    message = _(
                        "Page '{0}' has been updated."
                    ).format(
                        page.get_admin_display_title()
                    )

                messages.success(request, message)

            for fn in hooks.get_hooks('after_edit_page'):
                result = fn(request, page)
                if hasattr(result, 'status_code'):
                    return result

            if is_publishing or is_submitting:
                # we're done here - redirect back to the explorer
                if next_url:
                    # redirect back to 'next' url if present
                    return redirect(next_url)
                # redirect back to the explorer
                return redirect('wagtailadmin_explore', page.get_parent().id)
            else:
                # Just saving - remain on edit page for further edits
                target_url = reverse('wagtailadmin_pages:edit', args=[page.id])
                if next_url:
                    # Ensure the 'next' url is passed through again if present
                    target_url += '?next=%s' % urlquote(next_url)
                return redirect(target_url)
        else:
            if page.locked:
                messages.error(request, _("The page could not be saved as it is locked"))
            else:
                messages.validation_error(
                    request, _("The page could not be saved due to validation errors"), form
                )

            edit_handler = edit_handler.bind_to(instance=page, request=request, form=form)
            errors_debug = (
                repr(edit_handler.form.errors) +
                repr([
                    (name, formset.errors)
                    for (name, formset) in edit_handler.form.formsets.items()
                    if formset.errors
                ])
            )
            has_unsaved_changes = True
    else:
        form = form_class(instance=page, parent_page=parent)
        edit_handler = edit_handler.bind_to(instance=page, request=request, form=form)
        has_unsaved_changes = False

    # Check for revisions still undergoing moderation and warn
    if latest_revision and latest_revision.submitted_for_moderation:
        buttons = []

        if page.live:
            buttons.append(messages.button(
                reverse('wagtailadmin_pages:revisions_compare', args=(page.id, 'live', latest_revision.id)),
                _('Compare with live version')
            ))

        messages.warning(request, _("This page is currently awaiting moderation"), buttons=buttons)

    return render(request, 'wagtailadmin/pages/edit.html', {
        'page': page,
        'content_type': content_type,
        'edit_handler': edit_handler,
        'errors_debug': errors_debug,
        'action_menu': PageActionMenu(request, view='edit', page=page),
        'preview_modes': page.preview_modes,
        'form': form,
        'next': next_url,
        'has_unsaved_changes': has_unsaved_changes,
        'has_unpublished_parent': has_unpublished_parents,
        'is_readonly': readonly_group
    })


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

    return render(request, 'wagtailadmin/pages/confirm_unpublish.html', {
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

    return render(request, 'wagtailadmin/pages/publish_with_children.html', {
        'page': page,
        'next': next_url,
        'unpublished_descendants': unpublished_descendant_pages,
        'unpublished_descendant_count': page.get_descendants().not_live().count(),
    })

