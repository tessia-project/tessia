# Copyright 2021 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tessia instance factory component
"""

#
# IMPORTS
#
import base64

# TODO: update to 2020 validator
from jsonschema import Draft7Validator

from control_node.control_node.certificate_authority import CertificateAuthority

from .detached import DetachedInstance
from .errors import ValidationError
from .supervisord import SupervisordInstance

#
# CONSTANTS AND DEFINITIONS
#

SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'title': 'Tessia instance configuration',
    'definitions': {
        'keystore': {
            'type': 'object',
            'properties': {
                'type': {'enum': ['raw', 'base64', 'base85', 'file']},
                'value': {'type': 'string'}
            },
            'required': ['type', 'value']
        }
    },
    'properties': {
        'mode': {
            'enum': ['detached', 'supervisord']
        },
        'components': {
            'type': 'object'
        },
        'certificate-authority': {
            'oneOf': [
                {
                    'type': 'object',
                    'description': 'Certificate and key in PEM format',
                    'properties': {
                        'certificate': {'$ref': '#/definitions/keystore'},
                        'private-key': {'$ref': '#/definitions/keystore'},
                    },
                    'required': ['certificate', 'key']
                },
                {
                    'type': 'object',
                    'description': 'Certificate and key in PKCS12 container',
                    'properties': {
                        'pkcs12-bundle': {'$ref': '#/definitions/keystore'},
                        'import-key': {'$ref': '#/definitions/keystore'},
                    },
                    'required': ['pkcs12-bundle', 'import-key']
                },
            ]
        }
    },
    'required': ['mode', 'components'],
    'additionalProperties': True
}


#
# CODE
#


# Schema validator
_VALIDATOR = Draft7Validator(SCHEMA)


class InstanceFactory:
    """Configures and launched an instance of tessia"""

    @staticmethod
    def create_instance(configuration: dict):
        """Create an instance from configuration"""
        if not _VALIDATOR.is_valid(configuration):
            raise ValidationError(_VALIDATOR.iter_errors(configuration))

        cert_authority = InstanceFactory.create_certificate_authority(
            configuration.get('certificate-authority')
        )

        if configuration['mode'] == 'detached':
            return DetachedInstance(configuration['components'],
                                    cert_authority)

        if configuration['mode'] == 'supervisord':
            return SupervisordInstance(configuration['components'])

        raise ValueError("Unknown instance mode requested")
    # create_instance()

    @staticmethod
    def create_certificate_authority(
            configuration: dict) -> CertificateAuthority:
        """Create a CA from configuration"""
        if not configuration:
            return CertificateAuthority.create_self_signed()

        if 'pkcs12-bundle' in configuration:
            pkcs = load_bytes(configuration['pkcs12-bundle']['type'],
                              configuration['pkcs12-bundle']['value'])
            import_key = load_bytes(configuration['import-key']['type'],
                                    configuration['import-key']['value'])
            return CertificateAuthority.create_from_bundle(pkcs, import_key)
        if 'certificate' in configuration:
            certificate = load_bytes(configuration['certificate']['type'],
                                     configuration['certificate']['value'])
            private_key = load_bytes(configuration['private-key']['type'],
                                     configuration['private-key']['value'])
            return CertificateAuthority.create_from_certificate_and_key(
                certificate, private_key
            )

        raise ValueError("Invalid Certificate Authority configuration")
    # create_certificate_authority()

# InstanceFactory


def load_bytes(storage: str, value: str) -> bytes:
    """
    Given a storage, load bytes

    Storage may be a 'raw', 'base64', 'base85', 'file'
    Value is an encoded string or a path to local file
    """
    if storage == 'raw':
        return value.encode('utf-8')
    if storage == 'base64':
        return base64.b64decode(value)
    if storage == 'base85':
        return base64.b85decode(value)
    if storage == 'file':
        with open(value, "rb") as file:
            return file.read()

    # ease formatting
    if len(value) > 20:
        condensed_value = f'{value[:8]}...{value[-8:]}'
    else:
        condensed_value = value
    raise ValueError(f"Unknown storage {storage} for value {condensed_value}")
# load_bytes()
