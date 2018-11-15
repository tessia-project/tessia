# Copyright 2016, 2017 IBM Corp.
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
Extend the potion client with custom functionality
"""

#
# IMPORTS
#
from potion_client import Client as PotionClient
from potion_client import resource as potion_resource
from requests.auth import AuthBase
from tessia.cli.config import CONF
from tessia.cli.utils import build_expect_header

#
# CONSTANTS AND DEFINITIONS
#

#
# CODE
#
class Client(PotionClient):
    """
    Potion client extended with customizations
    """
    class XKeyAuth(AuthBase):
        """
        Implements support to our key token based authentication
        """
        def __init__(self, key_id, key_secret):
            """
            Constructor, store values.
            """
            self._key_id = key_id
            self._key_secret = key_secret
        # __init__()

        def __call__(self, request):
            """
            Add the auth header and return the request, this is how the
            requests library works with custom functions that add headers to a
            request before submitting it.

            Args:
                request (requests.Request): Request instance

            Returns:
                requests.Request: the same object with Authorized header added

            Raises:
                None
            """
            secret = 'x-key {}:{}'.format(
                self._key_id, self._key_secret).encode('ascii')
            request.headers['Authorization'] = secret
            return request
        # __call__()
    # XKeyAuth

    @staticmethod
    def _patch_update():
        """
        Patch the Resource.update method in potion client
        """
        def patched_update(self, *args, **kwargs):
            """
            Patched version of Resource.update which send update requests
            containing only the properties specified as arguments to the
            method. If no properties are specified all of them are sent in the
            request.
            """
            # pylint: disable=protected-access
            orig_props = self._properties

            # user specified which properties to update: set properties dict
            # to contain only them so that the update request do not update
            # unwanted fields
            if args or kwargs:
                self._properties = dict()
                if '$uri' in orig_props:
                    self._properties['$uri'] = orig_props['$uri']

            # perform the request
            self._properties.update(*args, **kwargs)
            self.save()

            # restore all properties
            if args or kwargs:
                orig_props.update(self._properties)
                self._properties = orig_props
        # patched_update()
        potion_resource.Resource.update = patched_update
    # _patch_update()

    def __init__(self, *args, **kwargs):
        """
        Constructor, initialize authentication information and default headers

        Args:
            args (list): packed argument to be forwarded to potion_client's
                         constructor
            kwargs (dict): packed keyword arguments, the key 'basic_auth' is
                           custom and not forwarded to potion_client's
                           constructor

        Raises:
            PermissionError: in case basic_auth is not provided and auth key is
                             missing in tessia client's configuration
            RuntimeError: in case server url is missing from tessia client's
                          configuration
        """
        self._patch_update()

        # basic_auth tuple (user, passwd) specified: use it as the credentials
        # for basic authorization for potion's client
        if kwargs.get('basic_auth') is not None:
            kwargs['auth'] = kwargs['basic_auth']
            kwargs.pop('basic_auth')
        # no auth specified: use key from local configuration
        else:
            auth_token = CONF.get_key()
            # token is missing from config: should never happen as the client
            # always verify missing token and generates one prior to using the
            # Client class in this mode
            if auth_token is None:
                raise PermissionError('Credentials not available')
            kwargs['auth'] = Client.XKeyAuth(auth_token[0], auth_token[1])

        # use server url provided in method call
        if args:
            server = args[0]
        # no server url provided: use from config file
        else:
            try:
                server = CONF.get_config()['server_url']
            except KeyError:
                raise RuntimeError('Server address missing')

        ca_file = CONF.get_cacert_path()
        # trusted ca file available: use it to verify ssl connection
        if ca_file:
            kwargs['verify'] = ca_file

        # add the default 'Expect' header to tell server which api version the
        # client wants
        kwargs['headers'] = kwargs.get('headers', {})
        kwargs['headers']['Expect'] = build_expect_header()
        super().__init__(server, *args, **kwargs)
    # __init__()
# Client
