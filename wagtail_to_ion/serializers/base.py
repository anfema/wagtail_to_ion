# Copyright © 2017 anfema GmbH. All rights reserved.
from rest_framework import serializers


class DataObject(serializers.ModelSerializer):

    def to_representation(self, obj):
        api_object_name = self.Meta.model.__name__.lower()
        context = {
            api_object_name: [super().to_representation(obj)],
        }
        return context
