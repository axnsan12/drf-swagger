import copy
import json
from collections import OrderedDict

from coreapi.compat import force_bytes
from future.utils import raise_from
from rest_framework.serializers import CurrentUserDefault
from ruamel import yaml

from . import openapi
from .app_settings import swagger_settings
from .errors import SwaggerValidationError


def _validate_flex(spec, codec):
    from flex.core import parse as validate_flex
    from flex.exceptions import ValidationError
    try:
        validate_flex(spec)
    except ValidationError as ex:
        raise_from(SwaggerValidationError(str(ex), 'flex', spec, codec), ex)


def _validate_swagger_spec_validator(spec, codec):
    from swagger_spec_validator.validator20 import validate_spec as validate_ssv
    from swagger_spec_validator.common import SwaggerValidationError as SSVErr
    try:
        validate_ssv(spec)
    except SSVErr as ex:
        raise_from(SwaggerValidationError(str(ex), 'swagger_spec_validator', spec, codec), ex)


#:
VALIDATORS = {
    'flex': _validate_flex,
    'ssv': _validate_swagger_spec_validator,
}


class _OpenAPICodec(object):
    media_type = None

    def __init__(self, validators):
        self._validators = validators

    @property
    def validators(self):
        """List of validator names to apply"""
        return self._validators

    def encode(self, document):
        """Transform an :class:`.Swagger` object to a sequence of bytes.

        Also performs validation and applies settings.

        :param openapi.Swagger document: Swagger spec object as generated by :class:`.OpenAPISchemaGenerator`
        :return: binary encoding of ``document``
        :rtype: bytes
        """
        if not isinstance(document, openapi.Swagger):
            raise TypeError('Expected a `openapi.Swagger` instance')

        spec = self.generate_swagger_object(document)
        for validator in self.validators:
            # validate a deepcopy of the spec to prevent the validator from messing with it
            # for example, swagger_spec_validator adds an x-scope property to all references
            VALIDATORS[validator](copy.deepcopy(spec), self)
        return force_bytes(self._dump_dict(spec))

    def encode_error(self, err):
        """Dump an error message into an encoding-appropriate sequence of bytes"""
        return force_bytes(self._dump_dict(err))

    def _dump_dict(self, spec):
        """Dump the given dictionary into its string representation.

        :param dict spec: a python dict
        :return: string representation of ``spec``
        :rtype: str
        """
        raise NotImplementedError("override this method")

    def generate_swagger_object(self, swagger):
        """Generates the root Swagger object.

        :param openapi.Swagger swagger: Swagger spec object as generated by :class:`.OpenAPISchemaGenerator`
        :return: swagger spec as dict
        :rtype: OrderedDict
        """
        swagger.security_definitions = swagger_settings.SECURITY_DEFINITIONS
        return swagger.as_odict()


class OpenAPICodecJson(_OpenAPICodec):
    media_type = 'application/json'

    def _dump_dict(self, spec):
        """Dump ``spec`` into JSON."""
        return json.dumps(spec)


class SaneYamlDumper(yaml.SafeDumper):
    """YamlDumper class usable for dumping ``OrderedDict`` and list instances in a standard way."""

    def ignore_aliases(self, data):
        """Disable YAML references."""
        return True

    def increase_indent(self, flow=False, indentless=False, **kwargs):
        """https://stackoverflow.com/a/39681672

        Indent list elements.
        """
        return super(SaneYamlDumper, self).increase_indent(flow=flow, indentless=False, **kwargs)

    @staticmethod
    def represent_odict(dump, mapping, flow_style=None):  # pragma: no cover
        """https://gist.github.com/miracle2k/3184458

        Make PyYAML output an OrderedDict.

        It will do so fine if you use yaml.dump(), but that generates ugly, non-standard YAML code.

        To use yaml.safe_dump(), you need the following.
        """
        tag = u'tag:yaml.org,2002:map'
        value = []
        node = yaml.MappingNode(tag, value, flow_style=flow_style)
        if dump.alias_key is not None:
            dump.represented_objects[dump.alias_key] = node
        best_style = True
        if hasattr(mapping, 'items'):
            mapping = mapping.items()
        for item_key, item_value in mapping:
            node_key = dump.represent_data(item_key)
            node_value = dump.represent_data(item_value)
            if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
                best_style = False
            if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
                best_style = False
            value.append((node_key, node_value))
        if flow_style is None:
            if dump.default_flow_style is not None:
                node.flow_style = dump.default_flow_style
            else:
                node.flow_style = best_style
        return node


SaneYamlDumper.add_representer(OrderedDict, SaneYamlDumper.represent_odict)
SaneYamlDumper.add_multi_representer(OrderedDict, SaneYamlDumper.represent_odict)


def yaml_sane_dump(data, binary):
    """Dump the given data dictionary into a sane format:

        * OrderedDicts are dumped as regular mappings instead of non-standard !!odict
        * multi-line mapping style instead of json-like inline style
        * list elements are indented into their parents
        * YAML references/aliases are disabled

    :param dict data: the data to be serializers
    :param bool binary: True to return a utf-8 encoded binary object, False to return a string
    :return: the serialized YAML
    :rtype: str,bytes
    """
    return yaml.dump(data, Dumper=SaneYamlDumper, default_flow_style=False, encoding='utf-8' if binary else None)


class OpenAPICodecYaml(_OpenAPICodec):
    media_type = 'application/yaml'

    def _dump_dict(self, spec):
        """Dump ``spec`` into YAML."""
        return yaml_sane_dump(spec, binary=True)
