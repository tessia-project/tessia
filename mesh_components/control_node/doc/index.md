<!--
Copyright 2021 IBM Corp.

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
# tessia-control-node

Last update: v0.0.1

This component manages tessia mesh instance. It can be used to start a new mesh
instance or as an agent to run additional instances.

## Structure

As is common with tessia mesh, components have an API module (Flask application)
and a library module. Control-node also provides a command-line interface to
interactively deploy an instance.

```
├ api             REST API module
├ conf            Configuration examples
├ control_node    Library module
├ doc             Documentation
└ tests           Tests
__init__.py       Package initialization
__main__.py       Command-line interface
```

## Configuration

Control-node configuration specifies the mode of operation for the node and may
also contain configuration for other components. For example:
```
{
    "mode": "detached",
    "components": {
        "control_node": {
            "listen": "localhost",
            "port": 7350,
            "configuration": {}
        },
        "permission_manager": {
            "listen": "localhost",
            "port": 7351,
            "configuration": {}
        },
        "resource_manager": {
            "listen": "localhost",
            "port": 7352,
            "configuration": {}
        },
        "scheduler": {
            "listen": "localhost",
            "port": 7354,
            "configuration": {
                "scheduler": {
                    "permission-manager": {
                        "url": "http://localhost:7351"
                    },
                    "resource-manager": {
                        "url": "http://localhost:7352"
                    }
                }
            }
        }
    }
}
```
`components` is a dictionary with mesh components to be started. When an
instance is started with the configuration above, it deploys permission manager,
resource manager, scheduler (with indication to use permission and resource
managers) **and a new control node** that can start additional instances.

`mode` defines mode of operation:
- `detached`: components start as Flask processes at indicated `listen` and
  `port`.

A working example configuration is provided in `conf/default.json`.

## Usage

### CLI mode

Start a tessia mesh instance:
```
python3 -m control_node --config control_node/conf/default.json
```

### Flask application

Start control node server:
```
FLASK_APP=control_node.api flask run --port 7350
```

Refer to [API documentation](./api.md) for API usage.

### As a library

Start instances via instance factory:
```python
from control_node.factory import InstanceFactory

with InstanceFactory.create_instance(configuration) as instance:
   instance.setup()
   instance.run()
   ...
```

`configuration` is a dictionary with configuration as above

