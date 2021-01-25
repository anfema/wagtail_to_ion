# Copyright © 2017 anfema GmbH. All rights reserved.
from django.conf.urls import url

from wagtail.utils.urlpatterns import decorate_urlpatterns
from wagtail.admin.auth import require_admin_access

from wagtail_to_ion.views.wagtail_override import ion_unpublish, ion_publish_with_children


overridden_urlpatterns = [
    url(r'^pages/(\d+)/unpublish/$', ion_unpublish, name='unpublish'),
    url(r'^pages/(\d+)/publish-with-children/$', ion_publish_with_children, name='publish-with-children'),
]

urlpatterns = decorate_urlpatterns(overridden_urlpatterns, require_admin_access)
