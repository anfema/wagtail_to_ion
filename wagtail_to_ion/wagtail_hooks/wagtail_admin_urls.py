from django.urls import path

from wagtail.core import hooks

from wagtail_to_ion.views.wagtail_override import image_safe_delete, document_safe_delete, media_safe_delete


@hooks.register('register_admin_urls')
def register_admin_urls():
    return [
        path('documents/delete/<int:document_id>/', document_safe_delete, name='documents-safe-delete'),
        path('images/<int:image_id>/delete/', image_safe_delete, name='images-safe-delete'),
        path('media/delete/<int:media_id>/', media_safe_delete, name='media-safe-delete'),
    ]
