<!--
Copyright 2017 IBM Corp.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
# Architecture topics

## Authentication explained

The tessia client authenticates the user with the API server by using an authentication token which is generated on first usage.
The use of tokens is a secure method for user authentication because it does not store the password locally, instead relying on a pair (token and secret) of long
generated hashes (UUID) which are transmitted to the server on each request. This method has some advantages:

* In case of a compromise of the token (compromise of server database or the token file on local users' computer), an attacker would only be able
to access the tool itself and cannot use it to access other systems (as opposed to storing the password). The token can then be revoked and a new one
generated.
* It's possible to generate multiple tokens for the same user, each for a different purpose. Say, a token for use with the command line client
and another one for the user's custom tooling that communicates directly with the API server. That makes accounting more precise and allow the possibility
to fine control permissions for each token based on their different purposes.
