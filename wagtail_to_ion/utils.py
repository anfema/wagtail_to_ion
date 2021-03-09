import functools
from typing import Any, Dict, Generator, List, NamedTuple, Tuple, Type, Union

from django.db.models import Q, Model

from wagtail.core.blocks import Block, BoundBlock, StreamValue, StructBlock, StructValue
from wagtail.core.fields import StreamField
from wagtail.core.models import Collection, Page, PageViewRestriction, get_page_models
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


def get_object_block_usage(obj, block_types: Union[Type[Block], Tuple[Type[Block]]]):
    """
    Returns a queryset of pages that contain a block linked to a particular object.

    Works like `wagtail.admin.models.get_object_usage` but inspects all pages
    which might contain a block of the specified type(s).

    To avoid inspecting all pages the following optimizations are applied:
      1. operate only on page models with a StreamField containing the specified block type(s)
      2. filter pages by expected JSON string in StreamField column(s)
    """
    block_usage = get_page_models_using_blocks(block_types=block_types)
    page_ptr_ids = set()

    for page_model in block_usage.keys():
        stream_field_filter_q = Q()
        stream_fields = set()

        # create a (postgres specific) filter for every block; look for:
        # - `"value": <pk>` string if block is in a StreamValue
        # - `"<field_name>": <pk>` if block is in a StructValue
        for block in block_usage[page_model]:
            filter_att = block.block_name if block.in_struct else 'value'
            stream_field_filter_q |= Q(**{f'{block.stream_field_name}__regex': rf'"{filter_att}":\s*{obj.pk}\M'})
            stream_fields.add(block.stream_field_name)

        for page_with_obj_pk_in_blocks in page_model.objects.filter(stream_field_filter_q):
            for field_name in stream_fields:
                for block, value, in_struct in get_stream_value_blocks(getattr(page_with_obj_pk_in_blocks, field_name)):
                    if isinstance(block, block_types) and value == obj:
                        page_ptr_ids.add(page_with_obj_pk_in_blocks.page_ptr_id)

    return Page.objects.filter(pk__in=page_ptr_ids)


class StreamFieldBlockInfo(NamedTuple):
    block_name: str
    block_type: Block
    in_struct: bool


def get_stream_field_blocks(stream_field) -> Generator[StreamFieldBlockInfo, None, None]:
    """Generates an un-nested list of blocks of a `StreamField`."""
    def unnest_blocks(blocks: dict, in_struct: bool = False):
        for block in blocks.items():
            yield StreamFieldBlockInfo(block[0], block[1], in_struct)
            if hasattr(block[1], 'child_blocks'):
                yield from unnest_blocks(block[1].child_blocks, in_struct=isinstance(block[1], StructBlock))

    return unnest_blocks(stream_field.stream_block.child_blocks)


class StreamValueBlockInfo(NamedTuple):
    block_type: Block
    block_value: Any
    json_field_name: str


def get_stream_value_blocks(stream_value: StreamValue) -> Generator[StreamValueBlockInfo, None, None]:
    """Generates an un-nested list of blocks of a `StreamValue`."""
    def unnest_blocks(value: Union[StreamValue, StructValue]):
        if isinstance(value, StreamValue):
            for stream_block in value:
                assert isinstance(stream_block, BoundBlock)
                if isinstance(stream_block.value, StructValue):
                    yield from unnest_blocks(stream_block.value)
                else:
                    yield StreamValueBlockInfo(stream_block.block, stream_block.value, 'value')
        elif isinstance(value, StructValue):
            for block_name, bound_block in value.bound_blocks.items():
                assert isinstance(bound_block, BoundBlock)
                if isinstance(bound_block.value, StreamValue):
                    yield from unnest_blocks(bound_block.value)
                else:
                    yield StreamValueBlockInfo(bound_block.block, bound_block.value, block_name)
        else:
            raise RuntimeError(f'Unexpected type: {type(value)}')

    return unnest_blocks(stream_value)


class ModelStreamFieldBlockInfo(NamedTuple):
    stream_field_name: str
    block_name: str
    block_type: Block
    in_struct: bool


@functools.lru_cache()
def get_page_models_using_blocks(
    block_types: Union[Type[Block], Tuple[Type[Block]]],
) -> Dict[Type[Model], List[ModelStreamFieldBlockInfo]]:
    """Returns information about all page models which use the specified block type(s) in a StreamField."""
    models_with_block: Dict[Type[Model], List[ModelStreamFieldBlockInfo]] = {}

    for page_model in get_page_models():
        for stream_field in [field for field in page_model._meta.get_fields() if isinstance(field, StreamField)]:
            for stream_field_block in get_stream_field_blocks(stream_field):
                if isinstance(stream_field_block.block_type, block_types):
                    if page_model not in models_with_block:
                        models_with_block[page_model] = []
                    models_with_block[page_model].append(
                        ModelStreamFieldBlockInfo(stream_field.attname, *stream_field_block),
                    )

    return models_with_block
