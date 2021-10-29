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
# API for tessia-control-node

Note: this is an unstable interface that may change at any moment.

Control node provides a REST API interface for communication.

## List API versions

```
GET /
```

Response:
```json
{
  "apis": [
    {
      "min_version": "0.0.0",
      "root": "/v1",
      "version": "0.0.1"
    }
  ],
  "name": "control_node"
}
```

## API v1

### Schema

```
GET /v1/schema
```
Response:
```json
{
  "/": "api root",
  "/instances": "Create or show instance"
}
```

### List instances
```
GET /v1/instances
```
Response:
```json
[
  "679e3c89ac323e19b9c55b550551669e2fae285fa4200985cd7b58ca867c45a6"
]
```

### Create new instance
```
POST /v1/instances
Content-Type: application/json

{...configuration data}
```
Response:
```json
{
    "instance_id": "679e3c89ac323e19b9c55b550551669e2fae285fa4200985cd7b58ca867c45a6",
    "success": true
}
```

### Get instance details
```
GET /v1/isntances/<instance_id>
```
Response:
```json
{
  "instance_id": "679e3c89ac323e19b9c55b550551669e2fae285fa4200985cd7b58ca867c45a6",
  "status": {
    "permission_manager": true,
    "resource_manager": true,
    "scheduler": true
  }
}
```

### Delete an instance
```
DELETE /v1/instances/<instance_id>
```
Response:
```
204 Deleted
```

