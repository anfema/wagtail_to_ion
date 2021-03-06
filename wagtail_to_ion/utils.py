from django.db.models import Q

from wagtail.core.models import Collection, Page, PageViewRestriction
from wagtail.images import get_image_model
from wagtail.documents import get_document_model

from wagtail_to_ion.models import get_ion_collection_model
from wagtail_to_ion.models.abstract import AbstractIonCollection


IonCollection = get_ion_collection_model()


def get_user_collections(user):
    """
    Return collections for the user
    """
    # TODO: doesn't support permission inheritance of nested collections
    # TODO: remove (should be obsolete once 'choose' permission is available; permission handling is project specific)
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


def get_collection_for_page(page):
    if page is None:
        return None

    ion_collection = Page.objects.ancestor_of(page).type(AbstractIonCollection).first()
    if ion_collection:
        return ion_collection.slug


# TODO: might be obsolete once https://github.com/wagtail/wagtail/pull/6300 has been merged
def visible_tree_by_user(root, user):
    collection = IonCollection.objects.get(live=True, slug=get_collection_for_page(root))
    
    if collection.view_restrictions.exists():
        restrictions = collection.view_restrictions.filter(
            restriction_type=PageViewRestriction.GROUPS,
            groups__in=user.groups.all()
        )
        if not restrictions.exists():
            return Page.objects.none()

    if root.view_restrictions.exists():
        restrictions = root.view_restrictions.filter(
            restriction_type=PageViewRestriction.GROUPS,
            groups__in=user.groups.all()
        )
        if not restrictions.exists():
            return Page.objects.none()

    tree = root.get_descendants().filter(live=True)
    public_tree = tree.public()
    non_public_tree = tree.not_public().filter(
        Q(
            view_restrictions__restriction_type=PageViewRestriction.GROUPS,
            view_restrictions__groups__in=user.groups.all()
        ) | \
        Q(
            view_restrictions__isnull=True
        )
    )
    ids = list(public_tree.values_list('id', flat=True))
    ids += list(non_public_tree.values_list('id', flat=True))
    return Page.objects.filter(id__in=ids)


def visible_collections_by_user(user):
    collections = IonCollection.objects.filter(live=True)
    if not user.is_active:
        collections = collections.public()
    else:
        public_collections = collections.public()
        non_public_collections = collections.not_public().filter(
            view_restrictions__restriction_type=PageViewRestriction.GROUPS,
            view_restrictions__groups__in=user.groups.all()
        )
        ids = list(public_collections.values_list('id', flat=True))
        ids += list(non_public_collections.values_list('id', flat=True))
        collections = IonCollection.objects.filter(id__in=ids)
    return collections


def isoDate(d):
    if d:
        return d.replace(microsecond=0, tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return 'None'
