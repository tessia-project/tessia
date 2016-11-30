#version=DEVEL
# System authorization information
auth --enableshadow --passalgo=sha512
sshpw --username=root somepasswd --plaintext
# Use network installation
url --url="{{config["parameters"]["repo_url"]}}"
repo --name="Server-HighAvailability" --baseurl={{config["parameters"]["repo_url"]}}/addons/HighAvailability
repo --name="Server-ResilientStorage" --baseurl={{config["parameters"]["repo_url"]}}/addons/ResilientStorage
# Use graphical install
graphical
# Run the Setup Agent on first boot
firstboot --enable
ignoredisk --only-use=vda
# Keyboard layouts
keyboard --vckeymap=us --xlayouts='us'
# System language
lang en_US.UTF-8

# Network information
{% for iface in config["parameters"]["ifaces"] %}
network  --bootproto=static --device={{iface["osname"]}} --ip={{iface["ip"]}} --netmask={{iface["mask"]}} --noipv6 --activate {% if iface["is_gateway"] %}--gateway={{iface["gateway"]}} --nameserver={{iface["dns_1"]}} {% endif %}
{% endfor %}
network  --hostname={{config["parameters"]["hostname"]}}

# Root password
rootpw --iscrypted {{config["parameters"]["sha512rootpwd"]}}
# System timezone
timezone America/New_York
# System bootloader configuration
{% for volume in config["parameters"]["storage_volumes"] %}
{% if volume["is_root"] %}
bootloader --append=" crashkernel=auto" --location=mbr --boot-drive={{volume["system_attributes"]["device"]}}
{% endif %}
# Partition clearing information
clearpart --all --initlabel --drives={{volume["system_attributes"]["device"]}}
# Disk partitioning information
{% for entry in volume["part_table"]["table"] %}
part {{entry["mp"]}} --fstype="{{entry["fs"]}}" --ondisk={{volume["system_attributes"]["device"]}} --size={{entry["size"]}} {% if entry.get("mo") %} --fsoptions="{{entry["mo"]}}" {% endif %}
{% endfor %}
{% endfor %}
%packages
@^minimal
@core
kexec-tools

%end

%addon com_redhat_kdump --enable --reserve-mb='auto'

%end