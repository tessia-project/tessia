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
Tessia control node class unit tests
"""

#
# IMPORTS
#
import subprocess

from ..control_node.certificate_authority import CertificateAuthority, \
    export_key_cert_bundle, certificate_matches_key

#
# CONSTANTS AND DEFINITIONS
#


#
# CODE
#

def test_ca_creates_self_signed():
    """Create a CA and validate itself"""
    cert_auth = CertificateAuthority.create_self_signed()

    key = cert_auth.dump_ca_private_key(None)
    crt = cert_auth.dump_ca_certificate()

    proc_key = subprocess.run(args=['openssl', 'ec', '-pubout'],
                              input=key, capture_output=True, check=True)
    proc_crt = subprocess.run(args=['openssl', 'x509', '-noout', '-pubkey'],
                              input=crt, capture_output=True, check=True)

    assert proc_key.stdout == proc_crt.stdout
    assert b'BEGIN PRIVATE KEY' in key
    assert b'BEGIN CERTIFICATE' in crt


def test_component_certificate_is_valid():
    """Create a component certificate and check its data"""
    cert_auth = CertificateAuthority.create_self_signed()
    key, crt = cert_auth.create_component_server_certificate(
        'node', 'localhost')

    assert certificate_matches_key(crt, key)
    assert crt.issuer == cert_auth.root.subject


def test_client_certificate_is_valid():
    """Create a component client certificate and check its data"""
    cert_auth = CertificateAuthority.create_self_signed()
    key, crt = cert_auth.create_component_client_certificate('node')

    assert certificate_matches_key(crt, key)
    assert crt.issuer == cert_auth.root.subject


def test_certificate_bundle_is_valid_pkcs12():
    """Create a certificate bundle and test its contents"""
    cert_auth = CertificateAuthority.create_self_signed()
    key, crt = cert_auth.create_component_client_certificate('node')
    export_key = '1234'

    bundle = export_key_cert_bundle(key, crt, cert_auth.root, export_key)

    key_and_cert = subprocess.run(
        args=['openssl', 'pkcs12', '-nodes', '-clcerts',
              '-password', f'pass:{export_key}'],
        input=bundle, capture_output=True, check=True)

    ca_cert = subprocess.run(
        args=['openssl', 'pkcs12', '-nokeys', '-cacerts',
              '-password', f'pass:{export_key}'],
        input=bundle, capture_output=True, check=True)

    assert b'BEGIN PRIVATE KEY' in key_and_cert.stdout
    assert b'BEGIN CERTIFICATE' in key_and_cert.stdout
    assert b'BEGIN CERTIFICATE' in ca_cert.stdout
