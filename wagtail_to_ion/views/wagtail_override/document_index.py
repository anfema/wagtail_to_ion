from wagtail_to_ion.utils import get_user_documents

from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.decorators.vary import vary_on_headers

from wagtail.admin.forms.search import SearchForm
from wagtail.admin.auth import PermissionPolicyChecker
from wagtail.admin.models import popular_tags_for_model
from wagtail.core.models import Collection
from wagtail.documents import get_document_model
from wagtail.documents.permissions import permission_policy

permission_checker = PermissionPolicyChecker(permission_policy)


@permission_checker.require_any('add', 'change', 'delete')
@vary_on_headers('X-Requested-With')
def document_index(request):
    Document = get_document_model()

    # Get documents (filtered by user permission)
    documents = permission_policy.instances_user_has_any_permission_for(
        request.user, ['change', 'delete']
    )

    # Ordering
    if 'ordering' in request.GET and request.GET['ordering'] in ['title', '-created_at']:
        ordering = request.GET['ordering']
    else:
        ordering = '-created_at'
    documents = documents.order_by(ordering)

    # Filter by collection
    current_collection = None
    collection_id = request.GET.get('collection_id')
    if collection_id:
        try:
            current_collection = Collection.objects.get(id=collection_id)
            documents = documents.filter(collection=current_collection)
        except (ValueError, Collection.DoesNotExist):
            pass

    # Search
    query_string = None
    if 'q' in request.GET:
        form = SearchForm(request.GET, placeholder=_("Search documents"))
        if form.is_valid():
            query_string = form.cleaned_data['q']
            documents = documents.search(query_string)
    else:
        form = SearchForm(placeholder=_("Search documents"))

    # Pagination
    documents = get_user_documents(request.user, documents)
    paginator = Paginator(documents, per_page=20)
    documents = paginator.get_page(request.GET.get('p'))

    collections = permission_policy.collections_user_has_any_permission_for(
        request.user, ['add', 'change']
    )
    if len(collections) < 2:
        collections = None

    # Create response
    if request.is_ajax():
        return render(request, 'wagtaildocs/documents/results.html', {
            'ordering': ordering,
            'documents': documents,
            'query_string': query_string,
            'is_searching': bool(query_string),
        })
    else:
        return render(request, 'wagtaildocs/documents/index.html', {
            'ordering': ordering,
            'documents': documents,
            'query_string': query_string,
            'is_searching': bool(query_string),

            'search_form': form,
            'popular_tags': popular_tags_for_model(Document),
            'user_can_add': permission_policy.user_has_permission(request.user, 'add'),
            'collections': collections,
            'current_collection': current_collection,
        })
