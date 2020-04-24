from django import template

from wagtail_to_ion.utils import get_user_collections as util_get_user_collections

register = template.Library()


# Get a user's collections based on their groups
@register.simple_tag(takes_context=True)
def get_user_collections(context):
    user = context['request'].user
    return util_get_user_collections(user)
