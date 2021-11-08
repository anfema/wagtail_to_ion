from __future__ import annotations
from typing import List, Tuple, Dict
import os
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.files.storage import get_storage_class
from django.conf import settings
from django.db.models import Model
from django.db.models.expressions import Value
from django.db.models.fields.files import FieldFile, FileField, ImageField
from django.db.models.fields.related import ForeignKey
from django.db.models.signals import *
from wagtail.images.models import Image, Rendition
from wagtailmedia.models import Media
from wagtail.documents.models import Document


from wagtail_to_ion.models import (
    get_ion_document_model,
    get_ion_image_model,
    get_ion_image_rendition_model,
    get_ion_media_model,
    get_ion_media_rendition_model
)

IonDocument = get_ion_document_model()
IonImage = get_ion_image_model()
IonImageRendition = get_ion_image_rendition_model()
IonMedia = get_ion_media_model()
IonMediaRendition = get_ion_media_rendition_model()


def all_models() -> List[Model]:
    models: List[Model] = []
    for model in apps.get_models():
        if model in (IonMedia, IonImage, IonDocument, IonMediaRendition, IonImageRendition, Rendition, Document, Image, Media):
            continue  # Skip over ion Models
        if issubclass(model, IonMedia) or issubclass(model, IonImage) or issubclass(model, IonDocument):
            continue  # Skip over ion Model subclasses
        models.append(model)

    return models


class DisableSignals:
    def __init__(self, disabled_signals=None):
        self.stashed_signals = defaultdict(list)
        self.disabled_signals = disabled_signals or [
            pre_init, post_init,
            pre_save, post_save,
            pre_delete, post_delete,
            pre_migrate, post_migrate,
        ]

    def __enter__(self):
        for signal in self.disabled_signals:
            self.disconnect(signal)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for signal in list(self.stashed_signals):
            self.reconnect(signal)

    def disconnect(self, signal):
        self.stashed_signals[signal] = signal.receivers
        signal.receivers = []

    def reconnect(self, signal):
        signal.receivers = self.stashed_signals.get(signal, [])
        del self.stashed_signals[signal]


class Item:
    def description(self) -> str:
        return 'Unknown item'
   
    def file_objects(self) -> List[FieldFile]:
        return []

    def paths_on_disk(self) -> List[str]:
        files: List[str] = []
        for file in self.file_objects():
            try:
                path = os.path.relpath(file.path, start=settings.MEDIA_ROOT)
                files.append(path)
            except (NotImplementedError, ValueError):
                pass  # Non-local storage

        return files

    def size(self) -> int:
        sz = 0
        for file in self.file_objects():
            try:
                sz += file.size or 0
            except (ValueError, FileNotFoundError):
                pass  # File not found
        return sz

    @classmethod
    def collect(cls) -> Tuple[List[Item], List[UnusedItem]]:
        orphans: List[UnusedItem] = []
        used: List[Item] = []

        # Find the Item/UnusedItem references
        if issubclass(cls, UnusedItem):
            for c in cls.__mro__:
                if not issubclass(c, UnusedItem) and c != Item and c != object:
                    MyUsedItem = c
            MyUnusedItem = cls
        else:
            MyUsedItem = cls
            for c in cls.__subclasses__():
                if issubclass(c, UnusedItem):
                    MyUnusedItem = c

        # Find foreign keys referencing this class in non-wagtail/ion models
        query: Dict[Model, List[str]] = defaultdict(list)

        for model in all_models():
            # Find all foreign key fields
            for field in model._meta.fields:
                if isinstance(field, ForeignKey):
                    if field.related_model == cls.item_class or issubclass(field.related_model, cls.item_class):
                        query[model].append(field.name)

        # Collect items from DB
        items = cls.item_class.objects.all()
        count = items.count()
        print(f"Collecting {count} {cls.item_class.__name__}, {len(query)} non-page models with foreign keys...")

        i = 0
        size = 0
        orphan_size = 0

        # Iterate over items and classify them into used and orphan
        for item in items:
            i += 1
            if i % 10 == 0:
                print(f" - {len(used)} used ({size/1024/1024:.2f} MB), {len(orphans)} orphans ({orphan_size/1024/1024:.2f} MB), {i/count*100.0:3.2f}%", end="\r")

            item_used = False

            # is the item used in a page?
            if item.get_usage().count() > 0:
                item_used = True

            # Is the item used in a fk from a non-page model
            if not item_used:
                for model, fields in query.items():
                    for field in fields:
                        ct = model.objects.filter(**{f"{field}__pk": item.pk}).count()
                        if ct > 0:
                            item_used = True
                            break
                    if item_used:
                        break
                    
            # sort into bins
            if item_used:
                image = MyUsedItem(item)
                size += image.size()
                used.append(image)
            else:
                image = MyUnusedItem(item)
                orphan_size += image.size()
                orphans.append(image)

        print(f"Collected {len(used)} used items ({size/1024/1024:.2f} MB), {len(orphans)} orphans ({orphan_size/1024/1024:.2f} MB)")
        return used, orphans


class UnusedItem(Item):

    def remove(self) -> None:
        self.item_class.objects.get(pk=self.instance.pk).delete()
        for file in self.file_objects():
            try:
                file.delete(save=False)
            except (ValueError, FileNotFoundError):
                pass  # Missing file
        for path in self.paths_on_disk():
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass  # Probably deleted before


class FileItem(Item):
    """
    This item describes a file on disk
    """
    def __init__(self, filename) -> None:
        super().__init__()
        self.filename = filename

    def description(self) -> str:
        return f"File: {self.filename}"

    def size(self) -> int:
        Storage = get_storage_class()
        storage = Storage()

        return storage.size(self.filename)

    @classmethod
    def walk_dir(cls, directory: str = '') -> List[str]:       
        Storage = get_storage_class()
        storage = Storage()

        result: List[str] = []
        dirs, files = storage.listdir(directory)

        result.extend([os.path.join(directory, file) for file in files])
        for d in dirs:
            f = FileItem.walk_dir(os.path.join(directory,d))
            result.extend(f)
        return result

    @classmethod
    def collect(cls, exclusions: List[Item]) -> Tuple[List[FileItem], List[UnusedFileItem]]:
        already_excluded_paths: List[str] = []
        orphans: List[UnusedFileItem] = []
        used: List[FileItem] = []

        # Collect filenames for all exclusions
        for e in exclusions:
            already_excluded_paths.extend(e.paths_on_disk())

        print(f"Collecting files with {len(already_excluded_paths)} exclusions...")        

        # Find all files on disk and exclude known paths
        i = 0
        size = 0
        orphan_size = 0
        for full_filename in FileItem.walk_dir():
            i += 1
            if i % 100 == 0:
                print(f" - {i} files ({size/1024/1024:.2f} MB), {len(orphans)} orphans ({orphan_size/1024/1024:.2f} MB)", end="\r")

            if full_filename not in already_excluded_paths:
                file_item = UnusedFileItem(full_filename)
                orphan_size += file_item.size()
                orphans.append(file_item)
            else:
                file_item = FileItem(full_filename)
                size += file_item.size()
                used.append(file_item)

        print(f"Collected {len(used)} files ({size/1024/1024:.2f} MB) and {len(orphans)} orphans ({orphan_size/1024/1024:.2f} MB)")

        # orphans contains a list of files not used by the cms
        return used, orphans


class UnusedFileItem(UnusedItem, FileItem):

    def remove(self) -> None:
        os.unlink(self.filename)


class DjangoFileFieldItem(Item):

    def __init__(self, field_file: FieldFile) -> None:
        super().__init__()
        self.field_file = field_file
    
    def description(self) -> str:
        try:
            return f'File: {self.field_file.path}'
        except NotImplementedError:
            return f'File: {self.field_file.url}'

    def file_objects(self) -> List[FieldFile]:
        return [self.field_file]
    
    @classmethod
    def collect(cls) -> Tuple[List[Item], List[UnusedItem]]:
        orphans: List[UnusedFileItem] = []  # Will stay empty
        used: List[FileItem] = []

        query: Dict[Model, List[str]] = defaultdict(list)

        print(f"Searching for file fields...")      

        # Iterate through all models
        for model in all_models():
            # Find all file fields
            for field in model._meta.fields:
                if isinstance(field, FileField) or isinstance(field, ImageField):
                    print(f" - Found {model.__name__}->{field.name}          ", end="\r")
                    query[model].append(field.name)

        print(f"Collecting file field items from {len(query)} models...")      

        # Now run queries on all found models
        size_sum = 0
        with DisableSignals():
            for model, fields in query.items():
                print(f" - Querying model {model.__name__}")
                
                i = 0
                size = 0
                for item in model.objects.all().only(*fields):
                    # And add them to the used list
                    for field in fields:
                        f = getattr(item, field, None)
                        if f is not None:
                            try:
                                size += f.file.size
                                used.append(cls(f))
                                i += 1
                                if i % 100 == 0:
                                    print(f" - {i} files ({size/1024/1024:.2f} MB)", end="\r")
                            except (ValueError, FileNotFoundError):
                                pass  # Missing file
                size_sum += size
                print(f" - {i} files ({size/1024/1024:.2f} MB)")
        print(f"Collected {len(used)} files ({size_sum/1024/1024:.2f} MB) from file fields")

        return used, orphans  # Orphans is always empty


class ItemWithRendition(Item):
    def __init__(self, instance, renditions) -> None:
        super().__init__()
        self.instance = instance
        self.renditions = list(renditions)

    def file_objects(self) -> List[FieldFile]:
        files: List[FieldFile] = []

        files.append(self.instance.file)

        for rendition in self.renditions:
            if getattr(rendition, 'file', None) is not None:
                files.append(rendition.file)

        return files

    def description(self) -> str:
        return "\n".join(
            [f"{self.item_class.__name__}: pk = {self.instance.pk}"] +
            [f"{self.item_class.__name__}Rendition: pk = {desc.pk}" for desc in self.renditions]
        )

class ImageItem(ItemWithRendition):
    """
    This Items describes an IonImage
    """

    item_class = IonImage

    def __init__(self, image: IonImage) -> None:
        super().__init__(image, IonImageRendition.objects.filter(image=image))


class UnusedImageItem(UnusedItem, ImageItem):
    pass


class MediaItem(ItemWithRendition):
    """
    This Items describes an IonMedia item
    """

    item_class = IonMedia

    def __init__(self, media: IonMedia) -> None:
        super().__init__(media, IonMediaRendition.objects.filter(media_item=media, transcode_finished=True))


class UnusedMediaItem(UnusedItem, MediaItem):
    pass


class DocumentItem(Item):
    """
    This Items describes an IonDocument item that is not linked to
    """

    item_class = IonDocument

    def __init__(self, document: IonDocument) -> None:
        super().__init__()
        self.instance = document

    def description(self) -> str:
        return f"Document: pk = {self.instance.pk}"

    def file_objects(self) -> List[FieldFile]:
        return [self.instance.file]


class UnusedDocumentItem(UnusedItem, DocumentItem):
    pass


class Command(BaseCommand):
    help = 'Generate a file deletion list for unused media files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--files',
            action='store_true',
            dest='files',
            default=False,
            help='List unused media files on disk, be aware that this does not include standard Django FileFields and ImageFields',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            dest='delete',
            default=False,
            help='Delete unused items found',
        )

    def handle(self, *args, **options):
        items_used: List[Item] = []
        items_orphaned: List[UnusedItem] = []
        
        for typ in (DocumentItem, MediaItem, ImageItem):
            used, orphans = typ.collect()
            items_used.extend(used)
            items_orphaned.extend(orphans)
        
        if options.get('files'):
            used, _ = DjangoFileFieldItem.collect()
            items_used.extend(used)
            all_items = items_used + items_orphaned
            used, orphans = FileItem.collect(all_items)
            items_orphaned.extend(orphans)
        
        for item in items_orphaned:
            print(item.description())
            if options.get('delete'):
                item.remove()
