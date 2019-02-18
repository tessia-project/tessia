<!--
Copyright 2016, 2017 IBM Corp.

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
# Database

## Considerations

For database handling we use sqlachemy's ORM (Object Relational Mapper) and [alembic](http://alembic.zzzcomputing.com/en/latest/tutorial.html) to manage the migrations.

The declarative base and all the models are located in the file `db/models.py`. Any modifications to the database layout are done in this file.

Below it is possible to see a visual representation of the database models. Some differences may exist between the chart and the actual models therefore you should always refer to the models file for accurate information.

![Database diagram](../img/db_diagram.png)

Even though we use sqlalchemy to abstract database access and in theory could use different backends, we are currently relying on specific postgres types (like INET and JSONB) so only postgres is supported by the application.

## How to make changes to the database schema

Once you have a dev environment ready to go (see [How to get a dev environment](dev_env.md)), follow these steps:

- Due to the fact that the git repository files inside the docker container are read-only you won't be able to create a new alembic version file from inside the docker container.
For that reason it's best to have a virtualenv deployed by tox for that operation.
- On a shell with your tox's virtualenv activated, set the correct db credentials in `.tox/devenv/etc/tessia/server.yaml`
- All database handling should be done through the command `tess-dbmanage`, so type `tess-dbmanage init` to create the database tables (if it already exists, you can clear it first with
`tess-dbmanage reset`)
- Apply the desired changes to the `tessia/server/db/models.py` file
- Create a new revision in alembic to have the database migration versioned: `tess-dbmanage rev-create '0.0.2 (add new table foo)'`.
  Alembic creates a new revision and a migration script (python file) under `tessia/server/db/alembic/versions` for you.
- Alembic is configured to autogenerate the changes in the migration script, but it's not 100% safe. Check the file to make sure the correct changes are being applied.
  You might also want to see the resulting sql for verification, this can be accomplished by using the -s option of the upgrade option as in `tess-dbmanage upgrade -s +1`.
  Only the sql is generated but no actual changes are applied to the database so you can run it as many times as you want.
  In case something is wrong in the script you can edit it and generate the sql again. If the error was in the models file you can delete the migration file and repeat the previous step.
- Apply the changes to the database with `tess-dbmanage upgrade +1`
- Exercise the downgrade as well with `tess-dbmanage downgrade -1`
- If everything looks good, commit the new migration script and the changes in the models file.
- Get yourself a coffee while you wait for your colleagues to review your patch ;)
