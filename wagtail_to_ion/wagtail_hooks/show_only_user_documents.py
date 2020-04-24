from django.urls import reverse

from wagtail.core import hooks

from wagtail_to_ion.utils import get_user_documents


@hooks.register('construct_document_chooser_queryset')
def show_only_user_documents(documents, request):
    """
    Only show images in user collections
    """
    return get_user_documents(request.user, documents)

@hooks.register('construct_main_menu')
def modify_documents_menu_item(request, menu_items):
    for item in menu_items:
        if item.name == 'documents':
            item.url = reverse('document-index')
