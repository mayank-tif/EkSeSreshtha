from rest_framework import serializers
from .utils import mobile_number_validation


class GenerateAppTokenSerializer(serializers.Serializer):
    deviceid = serializers.CharField(max_length=250, required=True, allow_blank=False)


class LoginSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=15, required=True, allow_blank=False)
    password = serializers.CharField(required=True, allow_blank=False, trim_whitespace=False)

    def validate(self, attrs):
        mobile_number = attrs.get("mobile_number")
        message = mobile_number_validation(mobile_number)
        if message:
            raise serializers.ValidationError({"mobile_number": str(message)})

        if not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required."})

        return attrs


def openapi_serializer_field(schema, required=False):
    schema_type = schema.get("type", "string")
    schema_format = schema.get("format")
    kwargs = {"required": required, "allow_null": bool(schema.get("nullable", False))}

    if schema_type == "integer":
        return serializers.IntegerField(**kwargs)
    if schema_type == "number":
        return serializers.FloatField(**kwargs)
    if schema_type == "boolean":
        return serializers.BooleanField(**kwargs)
    if schema_type == "array":
        item_schema = schema.get("items", {})
        if item_schema.get("format") == "binary":
            return serializers.ListField(child=serializers.FileField(), **kwargs)
        return serializers.ListField(child=openapi_serializer_field(item_schema), **kwargs)
    if schema_format == "binary":
        return serializers.FileField(**kwargs)
    if schema_format == "date-time":
        return serializers.DateTimeField(**kwargs)
    if schema_format == "uuid":
        return serializers.UUIDField(**kwargs)

    kwargs["allow_blank"] = not required
    return serializers.CharField(**kwargs)


class OpenAPISchemaSerializer(serializers.Serializer):
    def __init__(self, *args, fields=None, body_schema=None, **kwargs):
        super().__init__(*args, **kwargs)
        if body_schema is not None:
            required_fields = set(body_schema.get("required_fields", []))
            properties = body_schema.get("properties", {})
            for field_name, schema in properties.items():
                self.fields[field_name] = openapi_serializer_field(
                    schema, required=field_name in required_fields
                )
            return

        for field in fields or []:
            field_name = field.get("name")
            if not field_name:
                continue
            self.fields[field_name] = openapi_serializer_field(
                field.get("schema", {}), required=field.get("required", False)
            )


class OpenAPIQuerySerializer(OpenAPISchemaSerializer):
    pass


class OpenAPIBodySerializer(OpenAPISchemaSerializer):
    pass

