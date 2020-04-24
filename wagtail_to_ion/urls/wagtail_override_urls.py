# Copyright © 2017 anfema GmbH. All rights reserved.
from django.conf.urls import url
from wagtail.utils.urlpatterns import decorate_urlpatterns
from wagtail.admin.auth import require_admin_access
from wagtail_to_ion.views.wagtail_override import delete_image, image_index, delete_media, add_image, add_media, document_index, add_document, ion_create, ion_edit, ion_unpublish,ion_publish_with_children


urlpatterns = [
    url(r'^images/<int:image_id>/delete/$', delete_image),
    url(r'^images/$', image_index , name='image-index'),
    url(r'^media/delete/<int:media_id>/$', delete_media),
    url(r'^images/multiple/add/$', add_image, name='add_multiple'),
    url(r'^media/(\w+)/add/$', add_media, name='add'),
    url(r'^documents/$', document_index , name='document-index'),
    url(r'^documents/multiple/add/$', add_document, name='add_multiple'),
]

overriden_urlpatterns = [
    url(r'^pages/add/(\w+)/(\w+)/(\d+)/$', ion_create, name='add'),
    url(r'^pages/(\d+)/edit/$', ion_edit, name='edit'),
    url(r'^pages/(\d+)/unpublish/$', ion_unpublish, name='unpublish'),
    url(r'^pages/(\d+)/publish-with-children/$', ion_publish_with_children, name='publish-with-children'),
]

overriden_urlpatterns = decorate_urlpatterns(overriden_urlpatterns, require_admin_access)

urlpatterns += overriden_urlpatterns