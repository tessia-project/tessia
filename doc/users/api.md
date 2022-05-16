<!--
Copyright 2021, 2022 IBM Corp.

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

# Tessia API

Tessia server provides a REST API for use by other clients and services, and tessia
command line interface also uses the same API.

Base URI for API requests is `/`, and server location can be obtained from CLI with `tess conf show`.

## REST semantics

All resources that can be operated on are available as collections (with URIs as `/systems`, `/jobs` etc.)
and individual resources (`/systems/:id`, `/jobs/:id` etc.).

The following verbs are used in requests:

- GET: retrieve resource collection or individual resource
- POST: create a new resource in a collection
- PATCH: update a resource
- DELETE: delete a resource

JSON schema is provided for all resources; an overview is provided at `/schema` endpoint, 
and schema for a resource type at `/<resource>/schema`.
[Schema overview](../../mesh_components/resource_manager/doc/index.md) is included into documentation for reference.

Requests and responses are in general JSON-encoded.

## Authentication 

All requests require authentication. There are two schemes that can be used, basic and with user keys.

### Basic

To use basic authentication, provide an `Authorization` header with base64-encoded `username:password` string:
```
Authorization: Basic <encoded string>
```

### User keys

Alternatively, a user key can be first created by `POST` to `/user-keys`:
```
POST /user-keys
Authentication: Basic <as above>
```

The response will be a (JSON-encoded) list of two strings:
```
['key id', 'key secret']
```

The pair of `id:secret` can be used without base64 encoding
instead of basic authentication with the following header:
```
Authorization: X-Key id:secret
```

## Usage examples

### Retrieve a collection
```
GET https://server:5000/systems
```

Collections are returned page-by-page, so the response will include a `Link` header with relative pages:
```
Link: </systems?page=1&per_page=100>; rel="self",</systems?page=2&per_page=100>; rel="next",</systems?page=5&per_page=100>; rel="last"

[{"$uri": "/systems/29", "desc": "Test system", "hostname": "sys1.example.com", "hypervisor": "cpc1", "model": "Z14", "modified": {"$date": 1565180698000}, "modifier": "admin@example.com", "name": "sys1", "owner": "devops@example.com", "project": "tessia", "state": "AVAILABLE", "type": "LPAR"}, ...]
```

From a page:
```
GET https://server:5000/systems?page=2&per_page=100
```

With filter and sorting:
```
GET https://server:5000/systems?where={"project":{"$eq":"pool"}}&sort={"$uri":false}
```

Refer to JSON schema for available query fields and operators.

### Update an item

A request like this:
```
PATCH /systems/29
Content-Type: application/json

{"project":"omp"}
```

will update project on the specified system.

### Submit a job

Jobs cannot be instantiated directly - they are created by scheduler. Instead, a job request should be submitted:
```
POST /job-requests
Content-Type: application/json

{
   "action_type":"SUBMIT",
   "job_type":"autoinstall",
   "parameters": "..."
}
```

`action_type` may be "SUBMIT" or "CANCEL", job_type indicates the [state machine](../../tessia/server/state_machines) that will execute the job.
Since each machine has its own set of parameters, `parameters` is a only a string representation of an object that state machine expects. Currently this results in double encoding=, so in future this may be relaxed to represent an arbitrary object.

Response will be a job request ID:
```
45
```
which can be further queried:
```
GET /job-requests/45
```
```
{
   "$uri": "/job-requests/45", 
   "action_type": "SUBMIT", 
   "job_id": 38, 
   "job_type": "autoinstall", 
   "parameters": "{\"system\": \"sys1\", \"profile\": \"default\", \"os\": \"fedora34\", \"verbosity\": \"DEBUG\"}", 
   "priority": 0, 
   "request_id": 45, 
   "requester": "devops@example.com", 
   "result": "OK", 
   "start_date": null, 
   "state": "COMPLETED", 
   "submit_date": {"$date": 1565180705000}, 
   "time_slot": "DEFAULT", 
   "timeout": 0
}
```
This response will contain `job_id` after scheduler has processed the request and queued the job for execution.
Job state and output will be available at `/jobs/38` and `/jobs/38/output` endpoints.

### Get job output

There are two endpoints for job output: `/jobs/:id/output` and `/jobs/:id/download`.

`/output` endpoint provides job output as a JSON-encoded string with optional offset and limit:
```
GET /jobs/38/output
GET /jobs/38/output?qty=250
GET /jobs/38/output?offset=1000&qty=250
GET /jobs/38/output?offset=2000&qty=-1
```

`offset` and `qty` parameters represent number of output lines to skip and to return (`qty=-1` denotes all lines to the end).

The examples above request, respectively:
- complete output
- the first 250 lines of output
- 250 lines of output, starting from line 1000
- and the rest of the output, starting from line 2000.

Output is unconditionally provided with gzip compression, regardless of client request headers.

`/download` endpoint provides a link to download the output as a gzip-compressed file.
```

`/download` endpoint does not perform JSON encoding; it provides job output as a single file, either output only or a tarball with all files created by job exectution.

```
GET /jobs/38/download
GET /jobs/38/download?content=all
GET /jobs/38/download?content=output&encoding=raw
```

`content=all` parameter prepares a tar-gz archive with all files created by job execution, `content=output` (default) returns only output.

`encoding` indicates content encoding, used regardless of client request headers. `encoding=gzip` is default for `content=output` and has no effect for other options.
If the client does not support gzip, they can use `encoding=raw` to get uncompresssed output.

Examples above return respectively:

- complete output as a file (transferred with gzip encoding)
- gzipped tar archive with all job files, which include output, profile and runtime information
- complete output as a file (transferred without gzip encoding)

Browsers understand gzip encoding and automatically decompress received output. `curl` will download a compressed stream instead:
```
curl -s -u username:password https://server:5000/jobs/38/download | gzip -d > output.txt
```

To decompress output on the fly, add `--compressed` flag:
```
curl -s -u username:password --compressed https://server:5000/jobs/38/download > output.txt
```
