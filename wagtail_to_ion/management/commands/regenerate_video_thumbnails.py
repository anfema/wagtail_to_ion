from django.core.management.base import BaseCommand, CommandError

from wagtail_to_ion.models import get_ion_media_model, get_ion_media_rendition_model
from wagtail_to_ion.tasks import regenerate_rendition_thumbnail, generate_media_thumbnail


IonMedia = get_ion_media_model()
IonMediaRendition = get_ion_media_rendition_model()


def update_video_thumbnails(media_id=None):
	if media_id is None:
		items = IonMedia.objects.all()
	else:
		items = IonMedia.objects.filter(pk=media_id)

	for item in items:
		print('Regenerating thumbnails for {} (id: {})'.format(item.title, item.id))
		generate_media_thumbnail(item.pk)
		for rendition in IonMediaRendition.objects.filter(media_item_id=item.id, transcode_finished=True):
			try:
				print(' - Rendition {}...'.format(rendition.name))
				regenerate_rendition_thumbnail(rendition)
			except Exception as e:
				print(' - Failed rendering {}: {}'.format(rendition.name, str(e)))


class Command(BaseCommand):
	help = 'Regenerate Video thumbnails'

	def add_arguments(self, parser):
		parser.add_argument(
			'--id',
			action='store',
			type=int,
			dest='media_id',
			default=None,
			help='Media id to generate thumbnail for',
		)

	def handle(self, *args, **options):
		try:
			update_video_thumbnails(media_id=options.get('media_id'))
		except AssertionError as e:
			raise CommandError(str(e))
