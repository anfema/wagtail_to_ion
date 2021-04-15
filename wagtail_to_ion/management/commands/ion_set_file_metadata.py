from django.core.management.base import BaseCommand
from django.db.models import Q

from wagtail_to_ion.models import get_ion_document_model, get_ion_image_model, get_ion_media_model, \
    get_ion_media_rendition_model


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
    file_field_map = {
        'file': ('file_size', 'file_last_modified'),
        'thumbnail': ('thumbnail_file_size', 'thumbnail_file_last_modified'),
    }

    for model, file_fields in model_file_field_map.items():
        qs_filter = Q()
        for file_field in file_fields:
            for file_meta_field in file_field_map[file_field]:
                qs_filter |= Q(**{f'{file_meta_field}__isnull': True})
        qs = model.objects.filter(qs_filter)

        total = 0
        total_failed = 0

        for obj in qs.iterator():
            failed = False
            for file_field in file_fields:
                file = getattr(obj, file_field)
                for file_meta_field in file_field_map[file_field]:
                    if file_meta_field.endswith('file_size'):
                        try:
                            setattr(obj, file_meta_field, file.size)
                        except Exception:  # noqa
                            failed = True
                    if file_meta_field.endswith('file_last_modified'):
                        try:
                            setattr(obj, file_meta_field, file.storage.get_modified_time(file.name))
                        except Exception:  # noqa
                            failed = True

            if not failed:
                obj.save()
            else:
                total_failed += 1
            total += 1

        print(f'{model.__name__}: fixed {total - total_failed} records ({total_failed} had missing files)')


class Command(BaseCommand):
    help = 'Set file size & last modification time on file based models'

    def add_arguments(self, parser):
        # TODO? add retry flag (operate on entries with file_size=0 | file_last_modified=1970-01-01)
        pass

    def handle(self, *args, **options):
        set_file_metadata()
