# Copyright © 2017 anfema GmbH. All rights reserved.
from wagtail.core.models import PageBase

from wagtail_to_ion.utils import get_model_mixins


class PageMixinMeta(PageBase):
	"""Metaclass to add configured mixins as class bases"""
	def __new__(cls, name, bases, attrs, **kwargs):
		mixins = get_model_mixins(name)
		for mixin in mixins:
			new_attrs = [attr for attr in dir(mixin) if not attr.startswith('__') and not callable(getattr(mixin, attr))]
			new_vals = [getattr(mixin, attr) for attr in new_attrs]
			attrs.update(zip(new_attrs, new_vals))
		bases = mixins + bases
		return super().__new__(cls, name, bases, attrs)
