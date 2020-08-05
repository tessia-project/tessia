<!--
Copyright 2020 IBM Corp.

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

# Stand-alone components

In order to keep core tessia code focused on general tasks, specialized functionality is kept as separate components.

## Installer-webhook

Installer webhook is a webserver to collect installation logs for systems that are designed to use remote logging facilities. An example is a [curtin-based][curtin] Ubuntu 20.04 installer.

Installer-webhook runs as a service under supervisord; it has its incoming (webhook) port open on the container and a private control port. Normally webhook rejects all requests on its incoming port.

Autoinstaller state machine communicates over control port to allow certain requests to go thorugh. It shares a secret token between installation autofile and webhook, the webhook can then verify incoming requests using the secret token. 

Installer-webhook logs incoming requests and allows state machine to retrieve them.

[Subiquity][sm_subiquity] autoinstaller state machine is currently the one that uses webhook component.

### Webhook configuration

Webhook configuration is provided in `/etc/tessia/server.yaml` in section `installer-webhook` with the following sefaults:
```yaml
installer-webhook:
  cleanup_interval: 600
  control_port: 7224
  webhook_port: 7223
  log_path: /var/log/tessia
  log_rotate_size: 52428800
  log_rorate_keep: 3
```

`cleanup_interval`: how often does the component cleanup stale sessions that were not reclaimed by autoinstaller state machine. This is only a precautionary measure; normally job cancellation removes the session on the webhook.

`control_port`: port for control server; it is opened on localhost, which is limited to container.

`log_path`: path to store web server requests, both webhook and control.

`webhook_port`: port for webhook server; opened on all interfaces, exposed via Dockerfile and docker-compose

[curtin]: https://curtin.readthedocs.io/en/latest/index.html
[sm_subiquity]: https://gitlab.com/tessia-project/tessia/-/tree/master/tessia/server/state_machines/autoinstall/sm_subiquity.py