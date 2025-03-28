# Ananke
This is Ananke (əˈnæŋki): a lightweight, model-based network automation stack.

This started as an internal project, so it was written to suit our needs at the time. We
encourage contribution to extend functionality if others would find it useful.

## Motivation
I wrote this software because I couldn't find anything else which did the job at the
time. The three tenets that I started with were:

- **Repository-based**: The solution needs to be model-driven and repository-based in that
  we store our device configs in a modeled format in a version-controlled repository.
- **API for configuration changes**: Other business units should be able to influence
  network behavior via a set of APIs.
- **gNMI support**: The only southbound interface protocol we used at the time was gNMI.

## Config repo
Your actual device configs should be stored in a separate repo. This repo is referenced
with the environment variable $ANANKE_CONFIG, and it should be of a structure similar to
the example [here](./ananke/sample/config-repo/).

There should be at least two directories in your config repo, one called "devices" and
another called "roles". The devices directory is rather self-explanatory, with a directory
per device. The roles directory has shared content that is inherited by a device via the
[device's roles](#roles), similarly to Ansible.

The devices directory can be hierarchical, in that you can have subdirectories for sites
or org units, but the penultimate item in the path should always be the device itself,
and all paths under devices must be of the same length (i.e. you cannot mix and match with
and without sites).

The roles directory must not be hierarchical, with a directory named after the role
immediately under roles/ with the applicable files inside that.

The last directory in either case should contain the files themselves. These are .yaml.j2
(more on that later) files that contain the config data you want deployed to your device.

### File structure
The sample directory illustrates this, but the structure of the files is a YAML dict with
a path key and the contents to be inserted under that path as the value. The path concept
is common and native for data modeled in YANG, and can be applied to other types of data
as well. Some considerations about path depth are covered in the [Dealing with replace](#dealing-with-replace)
section.

Files have no technical limit on the number of path/content pairs they contain, but the
NetworkConfig API can not handle files with more than one. Thus, for files that you plan
to interact with using the NetworkConfig API you are limited to one path/content pair.
For other files (like common role config, etc) you can use as many as you like.

Ananke has no stake in how your files are formatted, as long as it's YAML (with optional
jinja2). In most cases this will be YANG data modeled according to the model(s) that your
device supports. You can mix and match models, such that interfaces (for example) are
defined in openconfig and other, vendor-specific attributes are in a native model.

## How does Ananke help me?

There are basically three "tiers" of usability for Ananke, going from less complex (and
less powerful) to more complex (and more powerful).

1) The first tier is using Ananke by itself, simply as a config delivery mechanism. The
  benefits to this approach (change and revision control) are fairly marginal, and come at
  the cost of needing to deal with your configs as modeled data rather than the (probably)
  more familiar device-native (e.g. CLI) approach. However, this approach can be consumed
  pretty easily and without any programming knowledge.

2) The second tier is using the built-in Jinja2 support for templating in your config files.
  With this, you can generate portions of config standalone or pulling from variables stored
  in the device vars.yaml files (or elsewhere) similarly to Ansible. This allows you to do
  things like generate large lists of BGP neighbors or interfaces based on fairly small
  definitions. It's a bit more powerful, but also limited and static. Likewise, the presence
  of jinja syntax in your config files prevents you from interacting with the config in
  python.

3) The third tier is using Ananke's NetworkConfig API to manage your device configs with
  external tools. This of course requires some programming knowledge, and the development
  of your own tools, but it unlocks a lot of powerful functionality. Using this, you can
  write your own tools to do what you need. This could be providing network engineers with
  CLI tools to create BGP neighborships, port configs, or other common tasks, creating a
  slack integration to allow people to change port status with a message to a slack channel,
  or even exposing similar funtionality to other platforms and systems via an abstraction
  API. Some ideas on how to use it can be found [here](#how-we-use-it).

## CLI tool
There is a [built-in CLI tool](./ananke/actions/ananke_cli.py) which you can use out of the box
to get config from a device and set config on the device. The help prompt from the tool
is quite useful, but here is a brief outline of the capabilities:

### set
The set command allows you to set config on a device:

    ./ananke/actions/ananke_cli.py set device1

Minimally it requires a single host, but you can supply a space-separated list of hosts
and/or roles, and it will figure out which hosts to apply to.

|Flag|Function|
|-----|-------|
|-s|The -s flag allows you to supply a free-form string which is matched against the gNMI path or filenames associated with the device. This allows you to send only some portions of the config if desired. You can provide multiple matches with repeated -s flags|
|-m|The -m flag allows you to update the config rather than replace it, the default is a replace operation unless otherwise specified in the settings.yaml file.|
|-d|The -d flag returns the JSON formatted config sent to the target as well as the target's response|
|-D|The -D flag runs in "dry-run" mode, which prints the JSON body without actually sending anything to the target.|
|-C|The -C flag indicates number of post checks you wish to run|
|-I|The -I flag, used with the -C flag, indicates the interval between post checks in seconds|
|-T|The -T flag, used with the -C flag, indicates the tolerance percentage for diffs integer fields in diffs. E.g. -T 10 means that a variance of 10% or less in integer fields is not considered a diff|
|-S|The -S flag sends the post checks reports to a slack webhook, if one is defined in the settings|

### get
The get command will run a gNMI get operation and return the contents at a given path

    ./ananke/actions/ananke_cli.py get device1 openconfig:/interfaces

|Flag|Function|
|-----|-------|
|-O|The -O flag returns the content without line breaks, which is sometimes useful for programmatic purposes.|
|-o|The -o flag returns operational data as well as config data. The default is only config data.|

## Config Section Matching
The Config object takes an optional sections argument which is a tuple of free-form string
which is compared to the gNMI path of all specified config sections for a device and/or a
filename. If it's a filename the gNMI paths in that file will be resolved behind the scenes.
If there is a match, only the contents matching those paths is pushed. If there is no match
the operation is skipped for the target. This behavior allows you to successfully pass
multiple targets and config sections that don't necessarily correspond to each other.

## Platform Matching
The shared templates need a way of matching the platform to which they are being
deployed. This is because you might have a repo that contains multiple device types and
if you are using native YANG models then those will be different for different platforms.
As such, the software attempts to find a file in the format of <file_name>_<platform>.yaml.j2
(where platform matches exactly what is set under platform/os in vars.yaml). It will apply
these platform-specific files **in addition** to files without a platform specification,
so if you have a file called mgmt.yaml.j2 and one called mgmt_cisco-xr.yaml.j2 in roles/all
it will apply both for platforms set to cisco-xr, and only mgmt.yaml.j2 for all others.

**Since the _ character is used to delimit the fields of the file name, it cannot be used
as a standard character in the file names.**

## Device roles
A device can have one or more roles associated with it, and from those roles it can
inherit config. The device roles are defined in the [vars.yaml file](#device-variables) underneath the device
directory. The ananke_cli.py tool (and dispatch class) are able to figure out which devices are
part of a role, and so you can use a role as a target in ananke_cli.py and the software will
extrapolate the actual hosts to run it against.

## Device Variables
In each device directory there needs to be a file called vars.yaml. This file minimally
contains the device type (defined at platform/os) and management IP. You can also
include a list of roles that the device should have, and you can optionally override some
of the default settings like username and gNMI port.

```yaml
platform:
  os: "cisco-xr" # same as netmiko device types except with - instead of _
management:
  ip: 10.0.0.1 # management IP
  username: "root" # username to log into device
  gnmi-port: 57777 # gNMI port
  certificate: "myhost.pem" # custom certificate name if different from global
  disable-set: true # option to disable config push to device
roles:
  - "edge"
```

Those are the only attributes used by Ananke natively, but you can store all sorts of other
device-specific information which can be used by the config API as well, like peering
details, etc.

## Settings
Global settings can be stored in $ANANKE_CONFIG/settings.yaml. We will go over the sections
of the settings file here.

### Vault:
There is native support for integration with a Hashicorp Vault instance from which Ananke
can fetch passwords or other secrets.

This field is either a boolean false to disable Hashicorp vault entirely, or a dict defining
some attributes of your vault installation:

```yaml
vault: false
```

```yaml
vault:
  url: https://my.vault.url
  mount-point: SOME_VAULT_MOUNT
  role-id: vault-role-uuid
  paths:
    - 'path/1'
    - 'path/2'
```

Your vault secret needs to be stored in the environment variable ANANKE_VAULT_SECRET.

### Username
The global username to use when connecting to devices. This can be overriden in a device's
vars.yaml file.

```yaml
username: admin
```

### Priority
You can optionally supply a priority definition in the settings file, which instructs
the software to apply paths in a particular order. This is important for some vendor
implementations. "priority" is a list of regex expressions that match a path in your config.
The location of the path in the list represents where in the overall sequence of configuration
items the path's contents will be applied.

```yaml
priority:
  - System\/fm-items
  - Cisco-IOS-XR-policy-repository-cfg:\/routing-policy
  - openconfig:\/interfaces\/interface[name=po\d{4}]
```

If a path regex doesn't match it is simply skipped, so paths of all models can coexist, and
you can define priorities for several different vendor implementations in the same list. In
the example above, if the target platform is NX-OS, then contents under fm-items would be
applied first followed by openconfig:/interfaces for port-channel interfaces, if the target
platform is IOS-XR then routing-policy would be applied first.

Remember that these are regular expressions though, so slashes in the path need to be
escaped.

### Write methods
The write method can be changed from the default by using the -m flag of the ananke_cli.py
tool which applies to an entire transaction, but it can also be specified per-path in the
write-methods section of the settings.yaml file in case you need control over a specific
path:

```yaml
write-methods:
  default: replace
  openconfig:/interfaces: update
```

Default applies to all paths that are not otherwise listed. The same technique can be
applied to a device's vars.yaml file if you need more granular control over individual
devices. The write method passed in on the CLI takes precedence over everything defined
in the write-methods settings/vars sections.

### Certificates
You can provide information on where your certificates are stored with the certificate
setting. You can either omit entirely or set the value to false in order to disable
TLS (use with caution, and be aware that several gNMI implementations don't work at all
in insecure mode), or you can define and set your default certificate name and the
directory in which your certificates are stored.

```yaml
certificate:
  name: 'wildcard.pem'
  directory: '/path/to/certs'
```

You can override this default certificate name on a per device basis by setting the
certificate value in the device vars.yaml file. You can also override the directory
by exporting the ANANKE_CERTIFICATE_DIR environment variable to a path.

### Merge Bindings
Ananke supports merging the config sections if they are specified at the exact same path.
This allows you to have device-specific configuration in a device directory and more general,
role-based configuration for the same path in a role directory. They will be merged into the
same payload when sending to the device so that neither will get overwritten (as would otherwise
happen with replace calls). It does this by importing the contents to a pyangbind binding, and
then exporting them again. This means that if you want to use this functionality, you need
to both generate the required binding and put it somewhere importable for python. I keep mine
in /var/lib/pyang_bindings and make sure that's in my python path. You can then import them
directly. Once that is complete, define the binding that should apply to a particular path in
the "merge-bindings" section of settings.yaml like so:

```yaml
merge-bindings:
  Cisco-IOS-XR-infra-objmgr-cfg:object-group:
    binding: xr_object_groups
    object: object_group
  Cisco-IOS-XR-ipv4-acl-cfg:ipv4-acl-and-prefix-list/accesses:
    binding: xr_acl
    object: ipv4_acl_and_prefix_list.accesses
```

The binding field is the name of your object in the bindings directory and the object
is the name used when instantiating an object of a given binding. The parts above correspond
to the following python (assuming you have a binding at /var/lib/pyang_bindings called
xr_object_groups and that /var/lib/pyang_bindings is in your python path):

```python
from xr_object_groups import object_group

binding = object_group.object_group()
```

The bindings directory needs to be maintained by you, as bindings can get very large and
you will probably only need a few. You can find more details about the pyangbind project
[here](https://github.com/robshakir/pyangbind). But an example command for generating a
binding follows (assuming you have the [YANG models](https://github.com/YangModels/yang)
repo cloned to /tmp):

```
pyang --plugindir ${PYBINDPLUGIN} --split-class-dir /var/lib/pyang_bindings/xr_object_groups \
  --use-xpathhelper \
  -p /tmp/yang/standard/ietf/RFC \
  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
  -f pybind \
  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-infra-objmgr-cfg.yang
```

### Transforms
There are unfortunately sometimes situations which require us to transform our config data
(modify one or more parts of it) before it gets sent to the device while still maintaining
the same content in our repo. If configured, Ananke will pass the ConfigPack objects to a
platform-specific transform function to achieve this. The ConfigPack object is a python
dataclass consisting of the following attributes:

- **path**: The gNMI path that the config contents should be applied to
- **content**: A python dict of the JSON body of the config content to be applied
- **write_method**: Either "update" or "replace"

The transform functions are defined by you. Ananke must be informed of where it can find
the modules via the transforms field in settings.yaml like so:

```yaml
transforms:
  module-directory: '/var/lib/ananke_transforms'
```

This directory needs to be reachable for Ananke to import from (defined in PYTHONPATH,
for example). If configured, Ananke will look there for a python module named after the
current device platform name (as defined in vars.yaml) with "-" replaced by "_", (e.g. a
file called cisco_nxos.py), and expects there to be a function in that module called
transform that takes a ConfigPack object as an argument and returns a ConfigPack object
(presumably after some modifications to the content attribute have been made). You can
define the behavior of the transform function to suit your needs.

An example of such a transform that I needed to do to get this working with NX-OS can be
found in the [sample file](./ananke/sample/transforms/cisco_nxos.py)

### Post checks
Ananke supports monitoring specific gNMI paths for changes after a change is pushed. If
a diff is reported at one of these paths it will be printed to stdout if using the CLI
tool, or made available on the Dispatch object if using the API. This system in theory
can support any paths you want, but in practice it has only been tested with OpenConfig
paths listed in the example below. Any others probably won't work out of the box. There
is sometimes variation in how different device types and vendors return OpenConfig data
via subscribe, so changes may need to be made to account for different vendors as well.

The diff output is the native [dictdiffer](https://pypi.org/project/dictdiffer/) output.

Minimally, a list of paths to monitor must be given. E.g.

```yaml
post-checks:
  paths:
    - "openconfig:/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state"
    - "openconfig:/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/afi-safis/afi-safi/state/prefixes"
    - "openconfig:/interfaces/interface/state"
    - "openconfig:/interfaces/interface/ethernet/state/counters"
    - "openconfig:/lldp/interfaces/interface/neighbors/neighbor/state"
```

You can specify a slack webhook URL to be used in conjunction with CLI-run tests (along
with the -S flag) if you want the report sent to a slack channel:

```yaml
post-checks:
  slack-webhook: https://hooks.slack.com/services/FOO/BAR/BAT
```

Alternatively you can define the slack webhook with the environment variable
ANANKE_SLACK_WEBHOOK. The environment variable takes precedence over the settings field.

An example of a python API integration:

```python
from ananke.struct.dispatch import Dispatch

targets = {
  "device1": set("interfaces", "bgp")
}
dispatch = Dispatch(targets=targets, post_checks=True)
dispatch.concurrent_deploy("replace")
while len(dispatch.deploy_results) != len(dispatch.targets) and retry > 0:
    sleep(0.2)
print(dispatch.deploy_results)
sleep(60)
dispatch.post_status.poll(tolerance=10)
print(dispatch.post_status.results)
```

## Environment Variables
    ANANKE_CONFIG: OS path to config file directory
    Optional:
    ANANKE_VAULT_SECRET: Vault secret
    ANANKE_CONNECTOR_PASSWORD: Password for login username
    ANANKE_REPO_TARGET: Either gitlab project ID or local path to git repo, used for config API
    ANANKE_CERTIFICATE_DIR:

## Credentials
Credentials for gNMI authentication are resolved according to this priority:

    1: Vault value for key ANANKE_CONNECTOR_PASSWORD
    2: Vault value for key ANANKE_CONNECTOR_PASSWORD_<username>
    3: Environment variable ANANKE_CONNECTOR_PASSWORD
    4: Environment variable ANANKE_CONNECTOR_PASSWORD_<username>

A combination of these techniques can be used, and the password is username-specific.

## Dispatch API
The software can be called with the [ananke_cli.py](./ananke/actions/ananke_cli.py) tool, but you can also bypass that and integrate
it directly with other software by importing the Dispatch object from [dispatch.py](./ananke/struct/dispatch.py).
An example of how this is done:

```python
from ananke.struct.dispatch import Dispatch

targets = {
  "device1": set("interfaces", "bgp")
}
dispatch = Dispatch(targets=targets, deploy_tags=["dry-run"])
dispatch.concurrent_deploy(method)
while len(dispatch.deploy_results) != len(dispatch.targets) and retry > 0:
    sleep(0.2)
print(dispatch.deploy_results)
```

The targets argument to Dispatch() takes a dict with devices as keys and sections to
deploy for those devices.

The concurrent_deploy() method uses map() from concurrent.futures.ProcessPoolExecutor()
to deploy the config to the given targets concurrently.

## Config API
Ananke provides a framework for programmatic config modification. A lot of the work still
needs to be done by you since it will vary from org to org, but Ananke gives you a useful
framework for developing your tools.

The first step is defining your repo target using the ANANKE_REPO_TARGET environment variable.
This is where the config API will look to find your configuration files. This can be the
same as ANANKE_CONFIG, if you want to do your modifications locally, but it also supports
a GitLab project to make modifications directly to the remote repo. If ANANKE_REPO_TARGET
is entirely numerical, it is interpreted as a GitLab project ID, and therefore also requires
a project access token to gain access to the repo. The project access token can either be
set in your Vault (key name ANANKE_CONFIG_PAT) or can be set as an environment variable
called ANANKE_CONFIG_PAT (the latter takes precedence over the former).

### RepoConfigInterface
Your interface for the config repo is an object called the RepoConfigInterface (RCI) from
ananke.config_api.network_config. This object provides some tools you can use to interact
with your config repo. In general, you will instantiate one of these objects and then pass it
around to your various functions or classes in order for them to interact with the repo.

A basic instantiation like so `rci = RepoConfigInterface()` will create a read-only instance
which can read from your repo but not write to it. If you want to write to it as well you
need to specify a branch name or boolean True to the branch argument like
`rci = RepoConfigInterface(branch=True)` or `rci = RepoConfigInterface(branch="feature/branch")`
which checks out a branch with an automatically generated or given name.

#### content_map
The main functionality of the RCI is the content_map, which is a mapping of file paths to
RepoConfigSection (RCS) objects, which hold various information about the config in the file,
including an optional binding, the python dict representation of the config, etc.

#### commit
Once you have made your changes, you can call the rci.commit() method in order to commit
your changes to the repo. This takes various git-related arguments like commit message,
author, etc, but will automatically generate everything if not given any arguments. Running
commit() will clear the content_map as the changes will have already been committed to the
repo at that point.

### Workflow
A sample project can be found in the [sample](./ananke/sample/config-tools/) directory.
There is a minimal example of a tool for adding a BGP neighbor to an OpenConfig
BGP definition. Ananke supports interacting with the config content either via a pyangbind
object or directly as JSON. The [example provided](./ananke/sample/config-tools/bgp_neighbor.py)
shows both approaches. If you are working with the python dict format of your config
(OcBgpNeighborNoBind) however YANG lists are rendered as normal python lists (unkeyed) so
you need to use some logic similar to the get_yang_list_element() function to look up a
list element based on a match criteria. You also need to explicitly create each level in
your structure with a dict. In general it's a lot nicer to work with a binding if you can.

The process is shown in the create_neighborship() function. First, you instantiate your
RCI, then you populate the content_map for the file you want to modify, then the rest is
up to you, but in the example given we pass the RCS object to the class, make our modifications,
then run rci.commit(), and if you're using a GitLab repo you can also create a PR with the
rci.repo.create_pr() function (which returns the URL of the pull request).

This is just the tip of the iceberg. You can get much more sophisticated with your config
generation if you want.

## Connectors

* gNMI: This is the only southbound connector that Ananke supports at the moment

## Order of Operations
In some rare cases you can technically model a device's entire config in a single file
and deliver it as such in one transaction, but in most cases this is not possible. As a
result, we send chunks of config in separate transactions, which sometimes has implications
on the order in which config is sent, especially if we are doing replace calls. Some devices
are less strict about this than others, but IOS-XR, for example, tends to do a lot of data
validation before committing a transaction. For these devices You can usually get around
most issues with the [priority](###priority) mapping. However, in a case like adding a
route-policy and a BGP neighbor using that route-policy, you'd need to deploy the route-policy
first. But if you wanted to later remove that configuration it would need to be done in the
reverse order (remove BGP neighbor first, then route-policy). There is no built-in mechanism
for handling this with Ananke, but you can often get around it by pushing one section first,
followed by the rest:

```
./ananke/actions/ananke_cli.py set device1 -s bgp
./ananke/actions/ananke_cli.py set device1
```

## Dealing with Replace

Since a replace write mode is in many cases desirable to enforce intended network state,
writing config can get tricky if you aren't careful with your path depths. For example,
if you had config at the exact same path specified in both a device file and a role file,
the last one processed would overwrite the first one. Likewise, if you had paths of different
lengths you may also end up with unintended consequences. Ananke supports explicit merging
of config at the same level [as discussed here](##merge-bindings), but there are a few
other strategies for dealing with it as well.

The config sections are pushed in most specific to least specific order, so host-specific
files first, followed by role-specific, followed by all. This allows you to supply shallow
paths at the host level and more specific paths at the group level, which means that nothing
will be overwritten. However, this can get complicated when a host has multiple roles.

Some platforms deal with replace calls differently as well. Notably NX-OS with it's non
commit-based configuration interface. Some config structures don't handle this well, like
interfaces, for example, where if you run a replace call towards the interfaces it destroys
everything and recreates it, which causes an outage of up to a minute while interface config
reconverges (ports bind to port-channels, etc). There is basic functionality to help
circumvent this with custom [write methods](###write-methods) and [transforms](###transforms).


## How we use it

As is probably clear at this point, Ananke is not exactly a turnkey solution to all your
network automation requirements. It's intended to be used as a framework around which you can
build your own complete solution. Much of the external functionality however is bespoke and
organization-specific, so we don't provide it here. But here is a high level idea of what
we use the framework for, which can maybe give you some ideas or point you in the right
direction for your own solutions.

### Pipeline integration

When you make a change to a device config it of course doesn't actually affect the device
until you push the changes. In our GitLab repo we have a pipeline which is run when a commit
is made against either the devices or roles .yaml.j2 files. The pipeline compares the latest
commit on the target branch with the latest commit on the branch to be merged and figures
out the roles and/or devices that have been updated and runs the dispatch class against them.
This means that any time config is changed, the updated config is pushed to the relevant
set of devices.

### Config Tools

#### Edge config
We automatically generate our edge device config by storing our transit and peering definitions
in PeeringManager. We have a list of peer organizations that we want to peer with and some
software that reads from the PeeringDB API to determine which IXes we have in common with
them and configures the relevant devices with the relevant peer organization BGP neighbors
and settings.

#### Netbox integration
We of course want our Netbox instance to be the source of truth, so we have Netbox send a
webhook when a device interface has been modified which then updates the configuration in
the repo accordingly and creates a PR for the network team to review and approve.

This makes it possible for other teams to use Netbox in order to activate an interface
according to how they want it. For example, the SRE team can update an access port with
a new VLAN or IP in Netbox and the actual changes are made to the network after the PR
is approved.

#### Cloud interconnects
We have cloud interconnects that are managed by the devops team, but our gear needs to
be updated any time an interconnect is changed (BGP peer, VLAN ID, etc). We expose the
API to the devops team that allows them to request for this change to be made based on
the output of their tasks.