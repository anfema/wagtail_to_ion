from django.contrib.contenttypes.models import ContentType
from django.db import models


class AbstractContentTypeDescription(models.Model):
    """
    Maps the django.contrib.contenttypes to human-readable strings
    """

    description = models.TextField()
    content_type = models.OneToOneField(ContentType, on_delete=models.PROTECT)
    example_image = models.ImageField(blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.description
