from django.forms.widgets import Widget


class StartStopRangeWidget(Widget):
    template_name = 'wagtail_to_ion/widgets/dual_range_widget.html'

    def __init__(self, range_min, range_max, reset_mode='zero', unit=None, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['style'] = 'width: 300px;'
        super().__init__(attrs=attrs)
        self.min = range_min
        self.max = range_max
        self.reset_mode = reset_mode
        self.unit = unit

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if value[0] is None:
            if self.reset_mode == 'inf':
                minval = self.min - 1
            else:
                minval = 0
        else:
            minval = value[0]

        if value[1] is None:
            if self.reset_mode == 'inf':
                maxval = self.max + 1
            else:
                maxval = 0
        else:
            maxval = value[1] - 1  # upper boundary is excluded

        context['widget']['minvalue'] = minval
        context['widget']['maxvalue'] = maxval
        context['widget']['rangemin'] = self.min - 1
        context['widget']['rangemax'] = self.max + 1
        context['widget']['reset_mode'] = self.reset_mode
        context['widget']['unit'] = self.unit or ''
        return context

    def value_from_datadict(self, data, files, name):
        """
        Given a dictionary of data and this widget's name, return the value
        of this widget or None if it's not provided.
        """
        low = data.get(name + "_low", None)
        if low is not None:
            try:
                low = int(low)
                if low < self.min:
                    low = None
            except ValueError:
                low = None

        high = data.get(name + "_high", None)
        if high is not None:
            try:
                high = int(high)
                if high > self.max:
                    high = None
            except ValueError:
                high = None

        if high is not None:
            high += 1  # upper boundary is excluded

        return [low, high]
