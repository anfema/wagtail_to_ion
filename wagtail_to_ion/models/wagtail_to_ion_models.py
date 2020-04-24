# Copyright © 2017 anfema GmbH. All rights reserved.
from wagtail.core import blocks


class ColorBlock(blocks.StructBlock):
    r = blocks.IntegerBlock()
    g = blocks.IntegerBlock()
    b = blocks.IntegerBlock()
    a = blocks.IntegerBlock()

    class Meta:
        icon = 'snippet'
