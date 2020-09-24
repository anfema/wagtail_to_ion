from django.db import models
from django.utils.text import slugify
from django.contrib.contenttypes.models import ContentType


class ContentTypeDescription(models.Model):
    """
    Maps the django.contrib.contenttypes to human-readable strings
    """

    description = models.TextField(blank=False, null=False)
    content_type = models.OneToOneField(ContentType, on_delete=models.PROTECT, blank=False, null=False)
    example_image = models.ImageField(blank=True, null=True)

    def __str__(self):
        return self.description
