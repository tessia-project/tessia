<!--
Copyright 2018 IBM Corp.

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
# Autoinstall machine

The autoinstall feature allows you to perform Linux installations using the distro's installer capabilities by means of an autofile (i.e. kickstart/autoinst/preseed).
The autofiles are [jinja2](http://jinja.pocoo.org) templates stored in the tool's database which can be managed via the `tess autotemplate ...` family of commands.

As an example, to list what templates are available and see the content of the template `distro_template_name`, type:

```
$ tess autotemplate list

(many entries...)

$ tess autotemplate print --name=distro_template_name
```

The tool already provides a set of templates for the supported operating systems and users can also create their own templates with `tess autotemplate add ...`.
For a reference of which variables/objects are available in a template, see the section [Autotemplate variables](#autotemplate-variables).

For each supported operating system there is a default template associated so that installations can be performed without the need for the user to specify which template to use.
You can list all OSes supported and their corresponding default templates by typing `tess os list`.
Although users can create their own templates, *only administrators* can register new OSes. This is to prevent the creation of multiple redundant entries for the same OS version.

# How the auto installation works

What happens when the user submits a job to perform a Linux installation with the following command:

```
$ tess system autoinstall --os=ubuntu16.04.1 --system=cpc3lp25
```

- As no profile was specified, the system's default profile is used (to specify one enter `--profile=`)
- As no custom template was specified, the default template for the OS is used (to specify one enter `--template=`)
- As no custom repository was specified, the tool queries the database for a repository associated with the target OS.
If multiple entries are available, the tool uses preferably the repository which is on the same subnet as the system being installed to improve network performance (it's also possible to specify custom repositories with `--repo=`, see the section [Using custom repositories](#using-custom-repositories) for details)
- The template then gets rendered using the determined values; the resulting file is a valid distro installer autofile (kickstart, autoinst, preseed)
- Autofile is placed on tessia's HTTP server
- Target system is booted with distro's installer image (kernel and initrd) downloaded from the distro's install repository
- The distro installer downloads the generated autofile from tessia's HTTP server and performs the automated installation
- Once the installation is finished tessia's autoinstaller machine validates the parameters of the resulting system (network interfaces, IP addresses, disks and partitions sizes, etc.) to assure the installation completed successfully

# Using custom repositories

There are two types of repositories recognized by the autoinstaller machine:

- install repository: can be used for distro installation; provides distro's installer image files (kernel and initrd)
- package repository: not used during system installation; instead it is added after installation to the package manager configuration of the resulting installed filesystem

Only repositories registered in the database and associated with a target OS are recognized as install repositories and as such suitable for use in distro installations.
You can check which install repositories are available for a given OS by typing:

```
$ tess repo list --os=os_version
```

If a repository in the database does not have an associated OS then it is regarded by the tool as a package repository only.

It's possible to specify custom repositories for a system installation by using the `--repo=` parameter for both types of repository. Examples:

```
# system installation using install repository named 'osinstall-1'
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=osinstall-1

# system installation using default install repository (therefore not specified)
# and 'packages-1' as a package repository (gets added to the resulting installed system):
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=packages-1

# package repositories can also be entered multiple times or directly in URL form:
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=packages-1 --repo=http://myserver.com/packages/mydistro/

# and you can also combine both types in the same installation:
$ tess system autoinstall --os=os_version --system=cpc3lp25 --repo=osinstall-1 --repo=packages-1 --repo=http://myserver.com/packages/mydistro/
```

# Custom kernel command line arguments

For Linux systems you can specify additional kernel command line arguments both for the target (installed) system as well as for the Linux distro's installer during installation time.

To define additional custom kernel command line arguments for your installed system (final state), edit the desired system activation profile with the `--kargs-target` parameter. Example:

```
$ tess system prof-edit --name=default --system=cpc3lp25 --kargs-target='selinux=0 nosmt=false'
```

These arguments will then be added to the generated autofile and included in the boot loader configuration of the resulting installation by the distro installer.

If you want to define additional kernel arguments for the distro installer to be used only during installation time, edit the desired profile with the `--kargs-installer` parameter. Example:

```
$ tess system prof-edit --name=default --system=cpc3lp25 --kargs-installer='nosmt=true zfcp.allow_lun_scan=0'
```

Any kernel arguments for the distro installer defined in this manner will take precedence over default values used by the autoinstall machine.

# Autotemplate variables

TODO
