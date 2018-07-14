# Ardana Heat Orchestration Template Generator

The `generate-heat.yml` top-level ansible playbook, aided by the `heat-generator` ansible role, implements the task of 
converting an Ardana input model into an OpenStack heat orchestration template that, when deployed, accurately 
emulates the hardware infrastructure described by the input model.

The following principles are baked into the design of this mechanism:

* _accurate conversion_: the virtualized environment deployed from the generated heat template emulates the hardware
infrastructure described by the input model as accurately as possible. Of particular difficulty is emulating the various
networking options that the input model is able to describe, such as VLAN trunk ports, bonds and routes, as well as 
processing the correct configuration that the neutron provider networks require from the underlying infrastructure 
networks and routers.
* _requires nothing but the input model_: the conversion process makes efficient use of the information provided in the 
input model and is able to figure out most of the details, requiring just the minimum of virtualization specific 
configuration in addition to it
* _minimal input model alteration_: there are some aspects of the input model that a virtual infrastructure just can't 
emulate with complete accuracy (e.g. the NIC mappings). Whenever this is the case, and only as a last resort, the input 
model is slightly altered to reflect the characteristics of a virtual environment and the conversion process minimizes 
the extent of modifications being done to it
* _idempotence_: running the conversion process a second time in a sequence, even on the same input model being updated 
by the previous iteration, yields the same result


## Modus Operandi

To generate heat, simply do the following:

_Step 1._ provide the path of an input model definition:

    ansible-playbook generate-heat-template.yml \
      -e input_model_path=./ardana-input-model/2.0/ardana-ci/deployerincloud-lite \
      -e heat_template_file=heat.yaml

_Step 2._ ...

_Step 3._ profit: `heat.yml` has been generated and the input model was updated in-place with virtualized 
infrastructure information

## Internum Modus Operandi

The following diagram depicts the heat generator design:



              +------------------------------------------------+
              |                                                |
              |                                                |
     +--------v-------+       +-----------------+              |
     |   input model  +------->                 |              |
     +----------------+       |   input model   |              |
                              |     loader      |              |
                              |                 |              |
                              +--------|--------+              |
                                       |                       |
                                       |                       |
                              +--------v--------+              |
                              |  input model    |              |
                              |  ansible var    |              |
                              +--------+--------+              |
                                       |                       |
                                       |                       |
                              +--------v--------+              |
                              |                 |              |
                              |   input model   |              |
                              |    processor    |              |
                              |                 |              |
                              +-----------------+              |
                              |                 |              |
     +----------------+       |   heat model    |      +-------+-------+
     | virtual config +------->   converter     -------> updated input |
     +----------------+       |                 |      |     model     |
                              +--------|--------+      +---------------+
                                       |
                                       |
                              +--------v--------+
                              |   heat model    |
                              |  ansible var    |
                              +--------+--------+
                                       |
                                       |
                              +--------v--------+
                              |                 |
                              |  heat template  |      +---------------+
                              |    generator    -------> heat template |
                              |                 |      +---------------+
                              +-----------------+


Composing modules:
* input model loader (ansible module): that takes in the path where an input model definition files are located and 
loads the input model into an ansible dictionary variable
* input model processor (ansible module): enhances the input model data structure to make it easier to navigate
* heat model converter (ansible module): takes in the enhanced input model data structure and another data structure 
describing the virtual configuration and returns:
  * a heat model ansible variable which briefly describes the configuration of heat orchestration resources necessary 
  to emulate the input model
  * the supplied input model data structure updated to reflect the virtualized infrastructure
* heat template generator (ansible template file): generates a heat orchestration template file based on the provided
heat model ansible variable  

The comprising modules are fully reusable for other purposes. Moreover, the heat model data structure accepted as input
by the heat template generator doesn't contain any information specific to Ardana, which means it the module can be 
easily reused (e.g. to generate heat orchestration templates to support Crowbar deployments).

The information captured in an Ardana input model does not provide all the necessary parts required to generate a 
complete heat orchestration template. There are virtualization specific bits that are missing from the input model, 
which need to be provided separately:

* the OpenStack images and flavors used for instantiated servers
* the size of the attached volumes

This missing information is already covered by the `default_virt_config` ansible role variable, which fits most of the
input model definitions available in the `ardana-input-model` repository, but it can be customized and provided to the 
`generate-heat.yml` playbook by supplying the `virt_config` parameter.

TODO: example

Conversely, a small part of the hardware infrastructure configuration covered in the input model needs to be updated 
to accurately reflect the OpenStack virtualized setup. The heat generator goes to great lengths to be minimally 
invasive, but it still needs to update the input model with this information:

* NIC mappings - the bus address numbering used by OpenStack's virtual network interfaces cannot be controlled to
reflect those configured in the input model
* mount points for virtual disk volumes are different than those used for hardware disks (e.g /dev/vda instead of 
/dev/sda)
* DNS addresses cannot be statically configured in advance. They can only be extracted from OpenStack after the heat 
template is deployed, as they correspond to DHCP server addresses dynamically allocated by OpenStack 

### Networking Complications

Most of the complexity of the implementation is concentrated around extracting and processing the necessary information 
related to the configuration of OpenStack networking resources (ports, networks, subnets and routers).

The following points capture the detailed strategy used during the conversion:

* one openstack network and one subnet resources are created for every network in the input model
* every neutron external or provider network configured in the input model that has a complete
  layer 2 definition (flat/vlan, with the provider physnet type and segment ID configured) is a
  network that must also be associated with an openstack network/subnet resource pair. This is needed
  to provide NAT, routing, external access, etc. Those neutron provider networks that are
  incompletely defined in the input model or are layer 3 based (e.g. VXLAN) are excluded from this rule.
* port security is disabled for all networks, to prevent filtering and to make the virtual infrastructure
  behave as much as possible as a hardware one
* the CIDR and gateway settings for the subnet are taken from the input model
  network configuration, when supplied. The subnet CIDR value is not really relevant (port security is
  disabled) unless it needs to be used for DHCP, NAT or routing services.
  If a CIDR is not supplied and there are no other means of determining the CIDR (see special network
  handling below), one is be generated (NOTE: currently, not implemented)
* dhcp is turned off for subnets, with the exception of the "CLM" network (see below) - IP addresses
  are allocated and configured by ansible based on the CIDRs set for the input model networks
* on every openstack server, the first port (which is usually configured in the VM to perform
  DHCP and enable SSH) needs to be forcefully associated with the "CLM" network, to receive its pre-allocated
  address. However, this is not needed if the VM image is configured to perform DHCP on other ports, so
  it can be an optional feature (or enabled/disabled for each individual server based on an image attribute
  - currently not implemented)
  NOTE: the port also has to be configured in the VM image to accept default routes provided via DHCP,
  otherwise accessing the VM via the floating IP will not work !
* the neutron network trunk feature is needed to accurately emulate the various input model interface model
  options, such as connecting the same interface to two or networks differentiated by VLAN tagging. The 
  trunk port feature is available in Newton/Neutron, but needs to be activated in Newton/Heat by backporting
  the `OS::Neutron::Trunk` resource support from Pike (already done for SOC7 and activated in the engineering
  cloud). This is how it's used:
  * the heat trunk "parent" port is attached to the heat network/subnet corresponding to the untagged input model
    network to which the interface is attached. If no untagged network is associated with an interface,
    the parent port is attached to a dummy network/subnet that has port security enabled, to emulate the
    fact that the native port isn't activated in the external switch
  * one heat trunk "child" port is configured for every VLAN tagged network attached to the interface
* emulating bond interfaces is accomplished by attaching two or more ports to the same network/subnet.
  This is currently supported by OpenStack Newton and older.
* information about DHCP, NAT and routing requirements for the openstack networks is extracted from
  the input model (see special networks below)

The following are networks that are special and/or require special handling:

* the "CLM" or "management" network:

  * identification: the input model network with the same CIDR value as that configured
    in the baremetal server settings. This network is also associated with the lifecycle manager
    component endpoints because the server IP addresses belong to it and this is the only
    connectivity info that the CLM has associated with the configured the servers
  * the openstack subnet CIDR must be the same as that configured for the input model network
  * DHCP must be enabled and the IP addresses allocated to VMs must correspond exactly to
    those configured in the server settings
    NOTE: openstack will also allocate a number of IP addresses for various service ports associated
    with this network, such as DHCP server ports, which may conflict with the statically assigned
    IP addresses. To prevent this, an address pool is configured for the "CLM" network's subnet
    that excludes the static IP addresses
  * the openstack subnet must be connected to the external router (see next point)
  * a floating IP must be associated with the "CLM" IP of the "CLM" node
  * ports attaching OpenStack servers to the CLM network must usually translate into the lowest
  interface index (i.e. eth0), because this is the interface that is usually configured in the guest
  OS to perform DHCP

* neutron external "bridge" networks:

  * identification: networks tagged with `neutron.l3_agent.external_network_bridge`
  * the CIDR and gateway are not specified for this input model network. They must be
    taken from the `neutron_external_networks` neutron configuration data, if present
  * the openstack subnet must be connected to the external router to provide external access
  * all this is needed to make the network behave like an external network
  * __DEPRECATED__: see https://bugzilla.suse.com/show_bug.cgi?id=1100583

* neutron external provider networks:

  * identification: `neutron_external_networks` neutron configuration data elements
    paired with network groups tagged with `neutron.networks.<vlan|flat>` which have
    `'provider-physical-network' == 'physical_network'`
     NOTE: currently only allowed in the input model if no network group is tagged with
    `neutron.l3_agent.external_network_bridge`
  * the CIDR and gateway are not specified for the input model network associated with the
    neutron external provider network. They must be taken from the `neutron_external_networks`
    neutron configuration data, if present.
  * the openstack subnet must be connected to the external router to provide external access
  * all this is needed to make the network behave like an external network

* neutron provider networks:

  * identification: `neutron_provided_networks` neutron configuration data elements
    paired with network groups tagged with `neutron.networks.<vlan|flat>` which have
    `'provider-physical-network' == 'physical_network'`
  * the CIDR and gateway might not specified for this input model network. They must be
    taken from the `neutron_provider_networks` neutron configuration data, if present.

* networks-groups with routes configured. The route can point to either:

  * default: this network needs external access (needs to be added to the external router)
    NOTE: this is usually the "CLM" network
  * one of the other network groups: networks associated with both network groups need to be added to the
    same router (note: doesn't need to be the external router, if external access isn't required/recommended)
    A matching route is usually configured for the other network group, or a default route
  * one of the neutron networks: both this network and the one used as a physical network for the
    neutron network need to be added to the same router (not the external router, if at least one of them
    doesn't need external access)
    NOTE: this means that there's another route configured for the other network, or that its
    default route leads to this network
    
    
### Addendum - how Ardana uses the input model neutron configuration and network group tag

External neutron network configuration (provisioned via `neutron-cloud-configure.yml`):
  * an external network/subnet is created for every network listed in `neutron_external_networks`
    * provider attrs (type, physnet, segment id) are taken from the `neutron_external_networks`
   element, if provided.
   NOTE: __DEPRECATED__ (see https://bugzilla.suse.com/show_bug.cgi?id=1100583)
  * if no `neutron_external_networks` items are configured, but there's at least one network group
    tagged with `neutron.l3_agent.external_network_bridge`, a default `ext-net` external network
    will be generated with a CIDR value taken from the `EXT_NET_CIDR` ansible var value passed to
    `neutron-cloud-configure.yml` (default = 172.31.0.0/16)
Neutron provider network configuration (provisioned via `neutron-deploy.yml`):
  * a provider network/subnet is created for every network listed in `neutron_provider_networks`
    * provider attrs (type, physnet) are taken from the `neutron_provider_networks` element.
    * segmentation id, CIDR, routes, gateway, DHCP and shared settings are taken from the
      `neutron_provider_networks` element, if provided
Neutron configuration (various neutron-ansible configuration playbooks)
  * on every node where the neutron L3 agent is running, the `external_network_bridge` configuration
    option is set to the interface attached to the network group tagged with neutron.l3_agent.external_network_bridge
    NOTE: this option has been removed in Pike - see https://bugzilla.suse.com/show_bug.cgi?id=1100583. Instead of configuring
    `external_network_bridge`, a physnet mapping should be added, same as with regular provider networks
  * on every neutron node, the ML2 plugin configuration is set up according to the `neutron.networks.vxlan/flat/vlan`
      tags set for the network groups with interfaces attached to them:
    * neutron-server settings:
      * `flat_networks` set to the list of `neutron.networks.flat/provider-physical-network` tag values
      * `vni_ranges` set to the list of `neutron.networks.flat/tenant-vxlan-id-range` values
        NOTE: only one VXLAN net can be defined
      * `network_vlan_ranges` set to a list of form `<physnet>[:<range>]` for each `neutron.networks.vlan
           /provider-physical-network, /tenant-vlan-id-range` tag values
    * OVS L2 agent settings:
      * `bridge_mapping` set to map between the `provider-physical-network` values of `neutron.networks.flat/vlan`
          tags and the port bridges associated with those tags
      * `local_ip` set to the IP of the port associated with the `neutron.networks.vxlan` tag
          NOTE: only one VXLAN net can be defined


