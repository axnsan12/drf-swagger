from collections import OrderedDict

from django.core.validators import RegexValidator
from django.utils.encoding import force_text
from rest_framework import serializers
from rest_framework.mixins import RetrieveModelMixin, DestroyModelMixin, UpdateModelMixin
from rest_framework.settings import api_settings

from . import openapi
from .errors import SwaggerGenerationError

#: used to forcibly remove the body of a request via :func:`.swagger_auto_schema`
no_body = object()


def is_list_view(path, method, view):
    """Check if the given path/method appears to represent a list view (as opposed to a detail/instance view).

    :param str path: view path
    :param str method: http method
    :param APIView view: target view
    :rtype: bool
    """
    # for ViewSets, it could be the default 'list' action, or a list_route
    action = getattr(view, 'action', '')
    method = getattr(view, action, None)
    detail = getattr(method, 'detail', None)
    suffix = getattr(view, 'suffix', None)
    if action in ('list', 'create') or detail is False or suffix == 'List':
        return True

    if action in ('retrieve', 'update', 'partial_update', 'destroy') or detail is True or suffix == 'Instance':
        # a detail_route is surely not a list route
        return False

    # for APIView, if it's a detail view it can't also be a list view
    if isinstance(view, (RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin)):
        return False

    # if the last component in the path is parameterized it's probably not a list view
    path_components = path.strip('/').split('/')
    if path_components and '{' in path_components[-1]:
        return False

    # otherwise assume it's a list view
    return True


def swagger_auto_schema(method=None, methods=None, auto_schema=None, request_body=None, query_serializer=None,
                        manual_parameters=None, operation_description=None, responses=None):
    """Decorate a view method to customize the :class:`.Operation` object generated from it.

    `method` and `methods` are mutually exclusive and must only be present when decorating a view method that accepts
    more than one HTTP request method.

    The `auto_schema` and `operation_description` arguments take precendence over view- or method-level values.

    :param str method: for multi-method views, the http method the options should apply to
    :param list[str] methods: for multi-method views, the http methods the options should apply to
    :param .SwaggerAutoSchema auto_schema: custom class to use for generating the Operation object
    :param .Schema,.SchemaRef,.Serializer request_body: custom request body, or :data:`.no_body`. The value given here
        will be used as the ``schema`` property of a :class:`.Parameter` with ``in: 'body'``.

        A Schema or SchemaRef is not valid if this request consumes form-data, because ``form`` and ``body`` parameters
        are mutually exclusive in an :class:`.Operation`. If you need to set custom ``form`` parameters, you can use
        the `manual_parameters` argument.

        If a ``Serializer`` class or instance is given, it will be automatically converted into a :class:`.Schema`
        used as a ``body`` :class:`.Parameter`, or into a list of  ``form`` :class:`.Parameter`\ s, as appropriate.

    :param .Serializer query_serializer: if you use a ``Serializer`` to parse query parameters, you can pass it here
        and have :class:`.Parameter` objects be generated automatically from it.

        If any ``Field`` on the serializer cannot be represented as a ``query`` :class:`.Parameter`
        (e.g. nested Serializers, file fields, ...), the schema generation will fail with an error.

        Schema generation will also fail if the name of any Field on the `query_serializer` conflicts with parameters
        generated by ``filter_backends`` or ``paginator``.

    :param list[.Parameter] manual_parameters: a list of manual parameters to override the automatically generated ones

        :class:`.Parameter`\ s are identified by their (``name``, ``in``) combination, and any parameters given
        here will fully override automatically generated parameters if they collide.

        It is an error to supply ``form`` parameters when the request does not consume form-data.

    :param str operation_description: operation description override
    :param dict[str,(.Schema,.SchemaRef,.Response,str,Serializer)] responses: a dict of documented manual responses
        keyed on response status code. If no success (``2xx``) response is given, one will automatically be
        generated from the request body and http method. If any ``2xx`` response is given the automatic response is
        suppressed.

        * if a plain string is given as value, a :class:`.Response` with no body and that string as its description
          will be generated
        * if a :class:`.Schema`, :class:`.SchemaRef` is given, a :class:`.Response` with the schema as its body and
          an empty description will be generated
        * a ``Serializer`` class or instance will be converted into a :class:`.Schema` and treated as above
        * a :class:`.Response` object will be used as-is; however if its ``schema`` attribute is a ``Serializer``,
          it will automatically be converted into a :class:`.Schema`

    """

    def decorator(view_method):
        data = {
            'auto_schema': auto_schema,
            'request_body': request_body,
            'query_serializer': query_serializer,
            'manual_parameters': manual_parameters,
            'operation_description': operation_description,
            'responses': responses,
        }
        data = {k: v for k, v in data.items() if v is not None}

        # if the method is a detail_route or list_route, it will have a bind_to_methods attribute
        bind_to_methods = getattr(view_method, 'bind_to_methods', [])
        # if the method is actually a function based view (@api_view), it will have a 'cls' attribute
        view_cls = getattr(view_method, 'cls', None)
        http_method_names = getattr(view_cls, 'http_method_names', [])
        if bind_to_methods or http_method_names:
            # detail_route, list_route or api_view
            assert bool(http_method_names) != bool(bind_to_methods), "this should never happen"
            available_methods = http_method_names + bind_to_methods
            existing_data = getattr(view_method, 'swagger_auto_schema', {})

            if http_method_names:
                _route = "api_view"
            else:
                _route = "detail_route" if view_method.detail else "list_route"

            _methods = methods
            if len(available_methods) > 1:
                assert methods or method, \
                    "on multi-method %s, you must specify swagger_auto_schema on a per-method basis " \
                    "using one of the `method` or `methods` arguments" % _route
                assert bool(methods) != bool(method), "specify either method or methods"
                assert not isinstance(methods, str), "`methods` expects to receive a list of methods;" \
                                                     " use `method` for a single argument"
                if method:
                    _methods = [method.lower()]
                else:
                    _methods = [mth.lower() for mth in methods]
                assert not any(mth in existing_data for mth in _methods), "method defined multiple times"
                assert all(mth in available_methods for mth in _methods), "method not bound to %s" % _route

                existing_data.update((mth.lower(), data) for mth in _methods)
            else:
                existing_data[available_methods[0]] = data
            view_method.swagger_auto_schema = existing_data
        else:
            assert method is None and methods is None, \
                "the methods argument should only be specified when decorating a detail_route or list_route; you " \
                "should also ensure that you put the swagger_auto_schema decorator AFTER (above) the _route decorator"
            view_method.swagger_auto_schema = data

        return view_method

    return decorator


def serializer_field_to_swagger(field, swagger_object_type, definitions=None, **kwargs):
    """Convert a drf Serializer or Field instance into a Swagger object.

    :param rest_framework.serializers.Field field: the source field
    :param type[openapi.SwaggerDict] swagger_object_type: should be one of Schema, Parameter, Items
    :param .ReferenceResolver definitions: used to serialize Schemas by reference
    :param kwargs: extra attributes for constructing the object;
       if swagger_object_type is Parameter, ``name`` and ``in_`` should be provided
    :return: the swagger object
    :rtype: openapi.Parameter, openapi.Items, openapi.Schema
    """
    assert swagger_object_type in (openapi.Schema, openapi.Parameter, openapi.Items)
    assert not isinstance(field, openapi.SwaggerDict), "passed field is already a SwaggerDict object"
    title = force_text(field.label) if field.label else None
    title = title if swagger_object_type == openapi.Schema else None  # only Schema has title
    title = None
    description = force_text(field.help_text) if field.help_text else None
    description = description if swagger_object_type != openapi.Items else None  # Items has no description either

    def SwaggerType(**instance_kwargs):
        if swagger_object_type == openapi.Parameter and 'required' not in instance_kwargs:
            instance_kwargs['required'] = field.required
        if swagger_object_type != openapi.Items and 'default' not in instance_kwargs:
            default = getattr(field, 'default', serializers.empty)
            if default is not serializers.empty:
                if callable(default) and hasattr(default, 'set_context'):
                    default = str(default)
                instance_kwargs['default'] = default
        if swagger_object_type == openapi.Schema and 'read_only' not in instance_kwargs:
            if field.read_only:
                instance_kwargs['read_only'] = True
        instance_kwargs.update(kwargs)
        return swagger_object_type(title=title, description=description, **instance_kwargs)

    # arrays in Schema have Schema elements, arrays in Parameter and Items have Items elements
    ChildSwaggerType = openapi.Schema if swagger_object_type == openapi.Schema else openapi.Items

    # ------ NESTED
    if isinstance(field, (serializers.ListSerializer, serializers.ListField)):
        child_schema = serializer_field_to_swagger(field.child, ChildSwaggerType, definitions)
        return SwaggerType(
            type=openapi.TYPE_ARRAY,
            items=child_schema,
        )
    elif isinstance(field, serializers.Serializer):
        if swagger_object_type != openapi.Schema:
            raise SwaggerGenerationError("cannot instantiate nested serializer as " + swagger_object_type.__name__)
        assert definitions is not None, "ReferenceResolver required when instantiating Schema"

        serializer = field
        if hasattr(serializer, '__ref_name__'):
            ref_name = serializer.__ref_name__
        else:
            ref_name = type(serializer).__name__
            if ref_name.endswith('Serializer'):
                ref_name = ref_name[:-len('Serializer')]

        def make_schema_definition():
            properties = OrderedDict()
            required = []
            for key, value in serializer.fields.items():
                properties[key] = serializer_field_to_swagger(value, ChildSwaggerType, definitions)
                if value.required:
                    required.append(key)

            return SwaggerType(
                type=openapi.TYPE_OBJECT,
                properties=properties,
                required=required or None,
            )

        if not ref_name:
            return make_schema_definition()

        definitions.setdefault(ref_name, make_schema_definition)
        return openapi.SchemaRef(definitions, ref_name)
    elif isinstance(field, serializers.ManyRelatedField):
        child_schema = serializer_field_to_swagger(field.child_relation, ChildSwaggerType, definitions)
        return SwaggerType(
            type=openapi.TYPE_ARRAY,
            items=child_schema,
            unique_items=True,  # is this OK?
        )
    elif isinstance(field, serializers.RelatedField):
        # TODO: infer type for PrimaryKeyRelatedField?
        return SwaggerType(type=openapi.TYPE_STRING)
    # ------ CHOICES
    elif isinstance(field, serializers.MultipleChoiceField):
        return SwaggerType(
            type=openapi.TYPE_ARRAY,
            items=ChildSwaggerType(
                type=openapi.TYPE_STRING,
                enum=list(field.choices.keys())
            )
        )
    elif isinstance(field, serializers.ChoiceField):
        return SwaggerType(type=openapi.TYPE_STRING, enum=list(field.choices.keys()))
    # ------ BOOL
    elif isinstance(field, serializers.BooleanField):
        return SwaggerType(type=openapi.TYPE_BOOLEAN)
    # ------ NUMERIC
    elif isinstance(field, (serializers.DecimalField, serializers.FloatField)):
        # TODO: min_value max_value
        return SwaggerType(type=openapi.TYPE_NUMBER)
    elif isinstance(field, serializers.IntegerField):
        # TODO: min_value max_value
        return SwaggerType(type=openapi.TYPE_INTEGER)
    # ------ STRING
    elif isinstance(field, serializers.EmailField):
        return SwaggerType(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL)
    elif isinstance(field, serializers.RegexField):
        return SwaggerType(type=openapi.TYPE_STRING, pattern=find_regex(field))
    elif isinstance(field, serializers.SlugField):
        return SwaggerType(type=openapi.TYPE_STRING, format=openapi.FORMAT_SLUG, pattern=find_regex(field))
    elif isinstance(field, serializers.URLField):
        return SwaggerType(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI)
    elif isinstance(field, serializers.IPAddressField):
        format = {'ipv4': openapi.FORMAT_IPV4, 'ipv6': openapi.FORMAT_IPV6}.get(field.protocol, None)
        return SwaggerType(type=openapi.TYPE_STRING, format=format)
    elif isinstance(field, serializers.CharField):
        # TODO: min_length max_length (for all CharField subclasses above too)
        return SwaggerType(type=openapi.TYPE_STRING)
    elif isinstance(field, serializers.UUIDField):
        return SwaggerType(type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID)
    # ------ DATE & TIME
    elif isinstance(field, serializers.DateField):
        return SwaggerType(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE)
    elif isinstance(field, serializers.DateTimeField):
        return SwaggerType(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME)
    # ------ OTHERS
    elif isinstance(field, serializers.FileField):
        # swagger 2.0 does not support specifics about file fields, so ImageFile gets no special treatment
        # OpenAPI 3.0 does support it, so a future implementation could handle this better
        err = SwaggerGenerationError("FileField is supported only in a formData Parameter or response Schema")
        if swagger_object_type == openapi.Schema:
            # FileField.to_representation returns URL or file name
            result = SwaggerType(type=openapi.TYPE_STRING, read_only=True)
            if getattr(field, 'use_url', api_settings.UPLOADED_FILES_USE_URL):
                result.format = openapi.FORMAT_URI
            return result
        elif swagger_object_type == openapi.Parameter:
            param = SwaggerType(type=openapi.TYPE_FILE)
            if param['in'] != openapi.IN_FORM:
                raise err  # pragma: no cover
            return param
        else:
            raise err  # pragma: no cover
    elif isinstance(field, serializers.DictField) and swagger_object_type == openapi.Schema:
        child_schema = serializer_field_to_swagger(field.child, ChildSwaggerType, definitions)
        return SwaggerType(
            type=openapi.TYPE_OBJECT,
            additional_properties=child_schema
        )

    # TODO unhandled fields: TimeField DurationField HiddenField ModelField NullBooleanField? JSONField

    # everything else gets string by default
    return SwaggerType(type=openapi.TYPE_STRING)


def find_regex(regex_field):
    """Given a ``Field``, look for a ``RegexValidator`` and try to extract its pattern and return it as a string.

    :param serializers.Field regex_field: the field instance
    :return: the extracted pattern, or ``None``
    :rtype: str
    """
    regex_validator = None
    for validator in regex_field.validators:
        if isinstance(validator, RegexValidator):
            if regex_validator is not None:
                # bail if multiple validators are found - no obvious way to choose
                return None  # pragma: no cover
            regex_validator = validator

    # regex_validator.regex should be a compiled re object...
    return getattr(getattr(regex_validator, 'regex', None), 'pattern', None)


def param_list_to_odict(parameters):
    """Transform a list of :class:`.Parameter` objects into an ``OrderedDict`` keyed on the ``(name, in_)`` tuple of
    each parameter.

    Raises an ``AssertionError`` if `parameters` contains duplicate parameters (by their name + in combination).

    :param list[.Parameter] parameters: the list of parameters
    :return: `parameters` keyed by ``(name, in_)``
    :rtype: dict[tuple(str,str),.Parameter]
    """
    result = OrderedDict(((param.name, param.in_), param) for param in parameters)
    assert len(result) == len(parameters), "duplicate Parameters found"
    return result
