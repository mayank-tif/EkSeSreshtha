from rest_framework import serializers


class GenerateAppTokenSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=15,required=True, allow_blank=False)
    deviceid = serializers.CharField(max_length=250,required=True, allow_blank=False)

    def validate(self, attrs):
        request = self.context.get('request')
        deviceid = attrs.get('deviceid')
        message = mobile_number_validation(mobile_number)
        if message:
            raise serializers.ValidationError({"error": str(message)})

        return attrs