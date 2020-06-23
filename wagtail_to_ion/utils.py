from wagtail.core.models import Collection, Page, PageViewRestriction
from wagtail.images import get_image_model
from wagtail.documents.models import get_document_model

from django.utils.module_loading import import_string
from wagtail_to_ion.conf import settings
from wagtail_to_ion.models import get_collection_model

from rest_framework.serializers import SerializerMetaclass

PageCollection = get_collection_model()


def get_user_collections(user):
    """
    Return collections for the user
    """
    collections = Collection.objects.all()
    if not user.is_superuser:
        collections = collections.filter(group_permissions__group__user=user).distinct()

    return collections


def get_user_images(user, images=None):
    """
    Return collections and images for the user
    """
    collections = get_user_collections(user)
    if not images:
        images = get_image_model().objects.all()
    if not user.is_superuser:
        images = images.filter(collection__in=collections)
    return images


def get_user_documents(user, documents=None):
    """
    Return collections and documents for the user
    """
    collections = get_user_collections(user)
    if not documents:
        documents = get_document_model().objects.all()
    if not user.is_superuser:
        documents = documents.filter(collection__in=collections)

    return documents


def visible_tree_by_user(root, user):
    tree = root.get_descendants().filter(live=True)
    public_tree = tree.public()
    non_public_tree = tree.not_public().filter(
        view_restrictions__restriction_type=PageViewRestriction.GROUPS,
        view_restrictions__groups__in=user.groups
    )
    ids = public_tree.values_list('id', flat=True) + non_public_tree.values_list('id', flat=True)
    return Page.objects.get(id__in=ids)


def visible_collections_by_user(user):
    collections = PageCollection.objects.filter(live=True)
    if not user.is_active:
        collections = collections.public()
    else:
        public_collections = collections.public()
        non_public_collections = collections.not_public().filter(
            view_restrictions__restriction_type=PageViewRestriction.GROUPS,
            view_restrictions__groups__in=user.groups
        )
        ids = public_collections.values_list('id', flat=True) + non_public_collections.values_list('id', flat=True)
        collections = PageCollection.objects.filter(id__in=ids)
    return collections


def isoDate(d):
    if d:
        return d.replace(microsecond=0, tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return 'None'


def get_model_mixins(model_name):
    mixin_paths = settings.WAGTAIL_TO_ION_MODEL_MIXINS.get(model_name, ())
    mixins = list()
    for mixin_path in mixin_paths:
        mixins.append(import_string(mixin_path))
    return tuple(mixins)
