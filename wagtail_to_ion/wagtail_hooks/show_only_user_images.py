from wagtail.core import hooks

from wagtail_to_ion.utils import get_user_images


@hooks.register('construct_image_chooser_queryset')
def show_only_user_images(images, request):
    """
    Only show images in user collections
    """
    return get_user_images(request.user, images)
