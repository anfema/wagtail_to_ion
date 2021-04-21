from django.core.management.base import BaseCommand
from django.db.models import Q

from wagtail_to_ion.fields.files import IonFieldFile
from wagtail_to_ion.models import get_ion_document_model, get_ion_image_model, get_ion_media_model, \
    get_ion_media_rendition_model


# PR #25 adds new fields to file based models; run this command to set the fields on existing records.


def set_file_metadata():
    IonDocument = get_ion_document_model()
    IonImage = get_ion_image_model()
    IonRendition = get_ion_image_model().get_rendition_model()
    IonMedia = get_ion_media_model()
    IonMediaRendition = get_ion_media_rendition_model()

    model_file_field_map = {
        # model -> file field(s)
        IonDocument: ('file',),
        IonImage: ('file',),
        IonRendition: ('file',),
        IonMedia: ('file', 'thumbnail'),
        IonMediaRendition: ('file', 'thumbnail'),
    }
    qs_file_field_map = {
        'file': ('file_size', 'file_last_modified'),
        'thumbnail': ('thumbnail_file_size', 'thumbnail_file_last_modified'),
    }

    for model, file_fields in model_file_field_map.items():
        qs_filter = Q()
        for file_field in file_fields:
            for file_meta_field in qs_file_field_map[file_field]:
                qs_filter |= Q(**{f'{file_meta_field}__isnull': True})
        qs = model.objects.filter(qs_filter)

        total = 0
        total_failed = 0

        for obj in qs.iterator():
            failed = False
            for file_field in file_fields:
                file: IonFieldFile = getattr(obj, file_field)
                try:
                    # check if the value of any file meta field is missing (the value is automatically set by
                    # IonFileField/IonImageField on model instance init if the file is available)
                    failed = not all([
                        file.checksum,
                        file.mime_type,
                        file.size,
                        file.last_modified,
                    ])
                except ValueError:
                    failed = True
                if failed:
                    break
            if not failed:
                updated_at = getattr(obj, 'updated_at', None)
                obj.save()
                # restore `updated_at` field
                if hasattr(obj, 'updated_at'):
                    model.objects.filter(pk=obj.pk).update(updated_at=updated_at)
            else:
                total_failed += 1
            total += 1

        print(f'{model.__name__}: fixed {total - total_failed} records ({total_failed} had missing files)')


class Command(BaseCommand):
    help = 'Set file size & last modification time on file based models'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        set_file_metadata()
