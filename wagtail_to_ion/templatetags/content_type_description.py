from collections import namedtuple

from django import template

from wagtail_to_ion.models import get_ion_content_type_description_model


register = template.Library()


@register.simple_tag
def content_type_description(app_label, model_name, verbose_name):
    ContentTypeDescription = get_ion_content_type_description_model()
    content_type_description = namedtuple("content_type_description", ["description", "image_url"])
    image_path = None

    try:
        description_object = ContentTypeDescription.objects.get(content_type__app_label=app_label, content_type__model=model_name)
    except ContentTypeDescription.DoesNotExist:
        description_object = None

    if description_object:
        if description_object.example_image:
            image_path = description_object.example_image.url

        return content_type_description(description_object.description, image_path)
    else:
        return content_type_description('Page of type "{}"'.format(verbose_name), None)
