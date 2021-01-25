from wagtail.core import hooks

from wagtail_to_ion.utils import get_user_documents


@hooks.register('construct_document_chooser_queryset')
def show_only_user_documents(documents, request):
    """
    Only show images in user collections
    """
    return get_user_documents(request.user, documents)
