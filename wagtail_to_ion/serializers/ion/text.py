from __future__ import annotations
from typing import List, Any, Union, Dict, Optional, Type

import re
from bs4 import BeautifulSoup

from wagtail.core.rich_text import RichText

from .base import IonSerializer


replacements = [
    (re.compile(r'<p>\s*(<br/?>)*</p>'), ''),  # All empty paragraphs filled only with whitespace or <br> tags
    (re.compile(r'<br/?>\s*</li>'), '</li>')   # All lists that end with a <br> tag before the closing </li>
]


def parse_correct_html(content_type):
    content = str(content_type)
    for (regex, replacement) in replacements:
        content = regex.sub(replacement, content)
    return content.strip()


class IonTextSerializer(IonSerializer):
    """
    This serializer handles text of all sorts. It checks if the text is HTML and does some
    re-formatting if it is. This grabs the ``str`` datatype without any sanity check. So
    if you want to override ``str`` handling, register a new serializer on your own and include
    a sanity check in there to fall back to this one just in case.
    """

    def __init__(self, name: str, data: Union[str, RichText], **kwargs) -> None:
        super().__init__(name, **kwargs)

        try:
            # check if text is html
            self.is_html = bool(BeautifulSoup(data, "html.parser").find())
        except TypeError:
            self.is_html = isinstance(data, RichText)
        if self.is_html:
            self.text = parse_correct_html(data)
        else:
            self.text = data.strip()

    def serialize(self) -> Optional[Dict[str, Any]]:
        result = super().serialize()
        if result is None:
            return None
        result.update({
            'type': 'textcontent',
            'is_multiline': self.is_html,
            'mime_type': 'text/html' if self.is_html else 'text/plain',
            'text': self.text,
        })
        return result

    @classmethod
    def supported_types(cls) -> List[Type]:
        return [str, RichText]


IonSerializer.register(IonTextSerializer)
