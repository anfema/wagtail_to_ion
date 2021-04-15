from django.utils.functional import cached_property
from wagtailmedia.blocks import AbstractMediaChooserBlock


class IonMediaBlock(AbstractMediaChooserBlock):
    @cached_property
    def target_model(self):
        from wagtailmedia.models import get_media_model
        return get_media_model()

    @cached_property
    def widget(self):
        from wagtailmedia.widgets import AdminMediaChooser
        return AdminMediaChooser

    def render_basic(self, value, context=None):
        raise NotImplementedError('You need to implement %s.render_basic' % self.__class__.__name__)