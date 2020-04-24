from django.dispatch import Signal

page_created = Signal(providing_args=["request", "page"])
