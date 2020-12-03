from wagtail_to_ion.utils import get_user_images

from django.shortcuts import render
from django.core.paginator import Paginator
from django.views.decorators.vary import vary_on_headers
from django.utils.translation import ugettext as _

from wagtail.core.models import Collection
from wagtail.admin.forms.search import SearchForm
from wagtail.images import get_image_model
from wagtail.admin.auth import PermissionPolicyChecker
from wagtail.admin.models import popular_tags_for_model
from wagtail.images.permissions import permission_policy

permission_checker = PermissionPolicyChecker(permission_policy)

@permission_checker.require_any('add', 'change', 'delete')
@vary_on_headers('X-Requested-With')
def image_index(request):
    """
    wagtail override due to collection permissions are not considered by wagtail by default
    """
    Image = get_image_model()

    # Get images (filtered by user permission)
    images = permission_policy.instances_user_has_any_permission_for(
        request.user, ['change', 'delete']
    ).order_by('-created_at')

    # Search
    query_string = None
    if 'q' in request.GET:
        form = SearchForm(request.GET, placeholder=_("Search images"))
        if form.is_valid():
            query_string = form.cleaned_data['q']

            images = images.search(query_string)
    else:
        form = SearchForm(placeholder=_("Search images"))

    # Filter by collection
    current_collection = None
    collection_id = request.GET.get('collection_id')
    if collection_id:
        try:
            current_collection = Collection.objects.get(id=collection_id)
            images = images.filter(collection=current_collection)
        except (ValueError, Collection.DoesNotExist):
            pass

    images = get_user_images(request.user, images)
    paginator = Paginator(images, per_page=20)
    images = paginator.get_page(request.GET.get('p'))

    collections = permission_policy.collections_user_has_any_permission_for(
        request.user, ['add', 'change']
    )
    if len(collections) < 2:
        collections = None

    # Create response
    if request.is_ajax():
        return render(request, 'wagtailimages/images/results.html', {
            'images': images,
            'query_string': query_string,
            'is_searching': bool(query_string),
        })
    else:
        return render(request, 'wagtailimages/images/index.html', {
            'images': images,
            'query_string': query_string,
            'is_searching': bool(query_string),

            'search_form': form,
            'popular_tags': popular_tags_for_model(Image),
            'collections': collections,
            'current_collection': current_collection,
            'user_can_add': permission_policy.user_has_permission(request.user, 'add'),
        })