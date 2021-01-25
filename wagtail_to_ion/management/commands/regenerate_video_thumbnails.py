from django.core.management.base import BaseCommand, CommandError
from wagtail_to_ion.models import IonMedia, IonMediaRendition
from wagtail_to_ion.tasks import generate_rendition_thumbnail, generate_media_thumbnail

def update_video_thumbnails(media_id=None):
	if media_id is None:
		items = IonMedia.objects.all()
	else:
		items = IonMedia.objects.filter(pk=media_id)

	for item in items:
		print('Regenerating thumbnails for {} (id: {})'.format(item.title, item.id))
		first = True
		for rendition in IonMediaRendition.objects.filter(media_item_id=item.id, transcode_finished=True):
			try:
				if first is True:
					generate_media_thumbnail(rendition)
					first = False
				print(' - Rendition {}...'.format(rendition.name))
				generate_rendition_thumbnail(rendition)
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
