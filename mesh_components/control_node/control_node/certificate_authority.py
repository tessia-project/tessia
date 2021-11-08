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
Certificate authority for mesh certificates

Mesh components interact by calling API methods over HTTP.
To make inter-component connection secure, a mesh is brought up with a common
certificate authority, which signs server and client certificates
for the components.
"""

#
# IMPORTS
#
from datetime import datetime, timedelta
from os import path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, rsa, dsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID

#
# CONSTANTS AND DEFINITIONS
#
DEFAULT_CA_NAME = 'Tessia mesh default CA'
DEFAULT_CA_ORG = 'Example Org'
DEFAULT_CA_COUNTRY = 'DE'

ACCEPTABLE_KEYS = (rsa.RSAPrivateKey, dsa.DSAPrivateKey,
                   ec.EllipticCurvePrivateKey)

#
# CODE
#


class CertificateAuthority:
    """
    CA for mesh TLS certificates
    """

    def __init__(self, certificate, key) -> None:
        """
        Create CA instance with certificate and key objects.
        It is recommended to use a specialized constructor::

            ca = CertificateAuthority.create_self_signed()
        """
        if not isinstance(certificate, x509.Certificate):
            raise ValueError("Certificate must be a x509.Certificate object")

        if not isinstance(key, ACCEPTABLE_KEYS):
            raise ValueError("Key must be a RSA/DSA/EC private key object")

        if not certificate_matches_key(certificate, key):
            raise ValueError("Certificate and key do not match")

        self._ca = certificate
        self._ca_key = key
    # __init__()

    @property
    def root(self):
        """Our own certificate"""
        return self._ca
    # root()

    @classmethod
    def create_self_signed(cls) -> "CertificateAuthority":
        """
        Create self-signed CA
        """
        ca_key = ec.generate_private_key(ec.SECP256R1())
        valid_from = datetime.today() - timedelta(days=1)
        valid_until = valid_from + timedelta(days=3656)
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, DEFAULT_CA_NAME),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, DEFAULT_CA_ORG),
            x509.NameAttribute(NameOID.COUNTRY_NAME, DEFAULT_CA_COUNTRY),
        ])

        cert = x509.CertificateBuilder(
            issuer_name=subject,
            subject_name=subject,
            public_key=ca_key.public_key(),
            serial_number=x509.random_serial_number(),
            not_valid_before=valid_from,
            not_valid_after=valid_until
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True).sign(ca_key, hashes.SHA256(), None)

        return cls(cert, ca_key)
    # create_self_signed()

    @classmethod
    def create_from_bundle(cls, pkcs12_bundle: bytes,
                           import_key: bytes) -> "CertificateAuthority":
        """
        Create CertificateAuthority object from a pkcs12 bundle
        """
        bundle = pkcs12.load_key_and_certificates(pkcs12_bundle, import_key)
        # safe unpack
        key, cert, ca_certs = (list(bundle) + [None]*3)[:3]
        if key is None:
            raise ValueError("Private key not found in PKCS12 bundle")
        if cert is None:
            # consider that in a bundle the actual certificate was placed into
            # "CA certificates" section (technically, a user error)
            if not isinstance(ca_certs, list) or not ca_certs:
                raise ValueError("Certificate not found in PKCS12 bundle")
            # if that is the case, pick a certificate from CA section
            cert = ca_certs[0]

        return cls(cert, key)
    # create_from_bundle()

    @classmethod
    def create_from_certificate_and_key(
            cls, certificate_serialized: bytes,
            key_serialized: bytes) -> "CertificateAuthority":
        """
        Create CertificateAuthority object from a pkcs12 bundle
        """
        cert = x509.load_pem_x509_certificate(certificate_serialized)
        key = serialization.load_pem_private_key(key_serialized, None)

        return cls(cert, key)
    # create_from_certificate_and_key()

    def dump_ca_private_key(self, key_passphrase):
        """
        Dump private key in PEM encoding

        Specifying key passphrase is higly recommended,
        but it may be empty or None to disable key encryption.
        """
        return export_private_key(self._ca_key, key_passphrase)
    # dump_private_key()

    def dump_ca_certificate(self):
        """
        Dump CA certificate in PEM encoding
        """
        return export_certificate(self._ca)
    # dump_certificate()

    def create_component_server_certificate(self, component_name, hostname):
        """
        Create server certificates for a component to use
        """
        key = ec.generate_private_key(ec.SECP256R1())
        valid_from = datetime.today() - timedelta(days=1)
        valid_until = valid_from + timedelta(days=3656)
        cert = x509.CertificateBuilder(
            issuer_name=self._ca.subject,
            subject_name=x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, component_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, DEFAULT_CA_ORG),
                x509.NameAttribute(NameOID.COUNTRY_NAME, DEFAULT_CA_COUNTRY)
            ]),
            public_key=key.public_key(),
            serial_number=x509.random_serial_number(),
            not_valid_before=valid_from,
            not_valid_after=valid_until
        ).add_extension(x509.SubjectAlternativeName([
            x509.DNSName(hostname)
        ]), critical=False).sign(self._ca_key, hashes.SHA256())

        return (key, cert)
    # create_component_server_certificate()

    def create_component_client_certificate(self, component_name):
        """
        Create client certificates for a component to use
        """
        key = ec.generate_private_key(ec.SECP256R1())
        valid_from = datetime.today() - timedelta(days=1)
        valid_until = valid_from + timedelta(days=3656)
        cert = x509.CertificateBuilder(
            issuer_name=self._ca.subject,
            subject_name=x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, component_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, DEFAULT_CA_ORG),
                x509.NameAttribute(NameOID.COUNTRY_NAME, DEFAULT_CA_COUNTRY)
            ]),
            public_key=key.public_key(),
            serial_number=x509.random_serial_number(),
            not_valid_before=valid_from,
            not_valid_after=valid_until
        ).add_extension(x509.ExtendedKeyUsage([
            x509.ExtendedKeyUsageOID.CLIENT_AUTH
        ]), critical=False).sign(self._ca_key, hashes.SHA256())

        return (key, cert)
    # create_component_server_certificate()

    def export_key_cert_to_directory(self, directory, key, certificate):
        """
        Export a private key, certificate and its CA as separate PEM files to
        the specified directory.

        Returns:
            Tuple(str, str, str): paths to key, certificate and CA certificate
        """
        crt_path = path.join(directory, 'crt.pem')
        key_path = path.join(directory, 'key.pem')
        ca_path = path.join(directory, 'ca.pem')
        with open(crt_path, 'wb') as file:
            file.write(export_certificate(certificate))
        with open(key_path, 'wb') as file:
            file.write(export_private_key(key, None))
        with open(ca_path, 'wb') as file:
            file.write(self.dump_ca_certificate())

        return (key_path, crt_path, ca_path)
    # export_key_cert_to_directory()

# CertificateAuthority


def certificate_matches_key(certificate: x509.Certificate, private_key) -> bool:
    """
    Check if certificate and key match
    """
    cert_public_key = get_public_key_part(certificate)
    key_public_part = get_public_key_part(private_key)
    return cert_public_key == key_public_part
# check_certificate_matches_key()


def export_private_key(key, key_passphrase: str) -> bytes:
    """
    Export private key in PEM encoding

    Specifying key passphrase is higly recommended,
    but it may be empty or None to disable key encryption.
    """
    if not key_passphrase:
        return key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())

    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(key_passphrase.encode('utf-8')))
# export_private_key()


def export_certificate(certificate: x509.Certificate) -> bytes:
    """
    Export certificate in PEM encoding
    """
    return certificate.public_bytes(serialization.Encoding.PEM)
# export_certificate()


def export_key_cert_bundle(
        key, certificate: x509.Certificate,
        ca_certificate: x509.Certificate, export_key: str) -> bytes:
    """
    Export key, certificate and CA into PKCS12 container.
    Note that "export key", while consitutes a pass phrase,
    is not a security measure, see "pkcs12.serialize_key_and_certificates" at
    https://cryptography.io/en/latest/hazmat/primitives/asymmetric/serialization/

    """
    return pkcs12.serialize_key_and_certificates(
        b'export-bundle',
        key, certificate,
        [ca_certificate],
        serialization.BestAvailableEncryption(export_key.encode('utf-8'))
    )
# export_key_cert_bundle()


def get_public_key_part(key_or_certificate) -> bytes:
    """
    Get public key part from key or certificate object in OpenSSH format

    This is not a complete key export, but a mechanism to compare used keys
    """
    # calls are actually identical for private keys and certificates
    return key_or_certificate.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH)
# get_public_key_part()
