#!/usr/bin/python
#
# (c) Copyright 2018 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#

DOCUMENTATION = '''
---
module: generate_heat_model
short_description: Generate heat template structure from input model
description: |
  Take an input model as input and generate a data structure
  describing a heat orchestration template and an updated input
  model with NIC mappings corresponding to the virtual setup described
  by the generated heat orchestration template. 
author: SUSE Linux GmbH
options:
  input_model: 
    description: Input model data structure 
  virt_config: 
    description: Virtual configuration descriptor (images, flavors, disk sizes)
output:
  heat_template: 
    description: Heat orchestration template descriptor 
  input_model: 
    description: Updated input model data structure 
'''

EXAMPLES = '''
- generate_heat_model:
    input_model: '{{ input_model }}'
    virt_config: '{{ default_virt_config }}'
  register: _result
- debug: msg="{{ _result.heat_template }} {{ _result.input_model }}"
'''

import re
from collections import OrderedDict
from copy import deepcopy
from netaddr import IPNetwork, IPAddress


def enhance_input_model(input_model):
    """
    Enhance the input model structure:
      - use dictionaries instead of lists (to simplify lookup operations)
      - use references instead of attributes (to simplify dereference operations)
      - delete unused elements

    :param input_model: the input model loaded from disk
    """

    def list_attr_to_map(element, attr_name, key='name'):
        if attr_name in element:
            element[attr_name] = OrderedDict([(item[key], item,) for item in element[attr_name]])
        else:
            element[attr_name] = OrderedDict()
        return element[attr_name]

    def link_element(element, attr_name, target_element, target_key_attr='name'):
        element_map = element.setdefault(attr_name, {})
        element_map.setdefault(target_element[target_key_attr], target_element)

    def link_element_list(element, attr_name, target_element_list, target_key_attr='name'):
        for target_element in target_element_list:
            link_element(element, attr_name, target_element, target_key_attr)

    def foreign_key_attr_to_ref(element, attr_name, target_map, ref_list_attr=None, key_attr='name'):
        foreign_key = element.setdefault(attr_name)
        if isinstance(foreign_key, basestring) and foreign_key in target_map:
            element[attr_name] = target_map[foreign_key]
            if ref_list_attr:
                if key_attr:
                    target_map[foreign_key].setdefault(ref_list_attr, OrderedDict())[element[key_attr]] = element
                else:
                    target_map[foreign_key].setdefault(ref_list_attr, []).append(element)

    def foreign_key_list_attr_to_ref_list(element, attr_name, target_map, ref_list_attr=None, key_attr='name'):
        foreign_key_list = element.setdefault(attr_name, [])
        for idx, foreign_key in enumerate(foreign_key_list):
            if isinstance(foreign_key, basestring) and foreign_key in target_map:
                foreign_key_list[idx] = target_map[foreign_key]
                if ref_list_attr:
                    if key_attr:
                        target_map[foreign_key].setdefault(ref_list_attr, OrderedDict())[element[key_attr]] = element
                    else:
                        target_map[foreign_key].setdefault(ref_list_attr, []).append(element)

    def prune_unused_items(element_map, ref_list_attrs):
        for name, element in element_map.items():
            for ref_list_attr in ref_list_attrs:
                if element.get(ref_list_attr):
                    break
            else:
                del element_map[name]

    input_model = deepcopy(input_model)

    for top_level_list in ['control-planes',
                           'configuration-data',
                           'server-roles',
                           'disk-models',
                           'interface-models',
                           'networks',
                           'network-groups',
                           'nic-mappings',
                           'servers',
                           'server-groups',
                           'firewall-rules']:
        list_attr_to_map(input_model, top_level_list,
                                 'id' if top_level_list == 'servers' else 'name')

    neutron_config_data = []

    for cp in input_model['control-planes'].itervalues():
        list_attr_to_map(cp, 'load-balancers')
        list_attr_to_map(cp, 'clusters')
        list_attr_to_map(cp, 'resources')
        foreign_key_list_attr_to_ref_list(cp, 'configuration-data',
                                          input_model['configuration-data'], ref_list_attr='control-planes')

        for cluster in cp['clusters'].itervalues():
            cluster['control-plane'] = cp
            foreign_key_attr_to_ref(cluster, 'server-role',
                                    input_model['server-roles'], ref_list_attr='clusters')
            foreign_key_list_attr_to_ref_list(cluster, 'configuration-data',
                                              input_model['configuration-data'], ref_list_attr='clusters')
            neutron_config_data += filter(lambda config_data: 'neutron' in config_data['services'],
                                          cluster['configuration-data'])
        for resource in cp['resources'].itervalues():
            resource['control-plane'] = cp
            foreign_key_attr_to_ref(resource, 'server-role',
                                    input_model['server-roles'], ref_list_attr='resources')
            foreign_key_list_attr_to_ref_list(resource, 'configuration-data',
                                              input_model['configuration-data'], ref_list_attr='resources')
            neutron_config_data += filter(lambda config_data: 'neutron' in config_data['services'],
                                          resource['configuration-data'])

        neutron_config_data += filter(lambda config_data: 'neutron' in config_data['services'],
                                      cp['configuration-data'])

    # Assume there is at most one neutron configuration data
    neutron_config_data = input_model['neutron-config-data'] = neutron_config_data[0] if neutron_config_data else None

    # Delete configuration elements that aren't referenced by
    # control planes, clusters or resources
    prune_unused_items(input_model['configuration-data'], ['control-planes', 'clusters', 'resources'])

    # Delete server roles that aren't referenced by clusters or resources
    prune_unused_items(input_model['server-roles'], ['clusters', 'resources'])

    for server_role in input_model['server-roles'].itervalues():
        foreign_key_attr_to_ref(server_role, 'interface-model',
                                input_model['interface-models'], ref_list_attr='server-roles')
        foreign_key_attr_to_ref(server_role, 'disk-model',
                                input_model['disk-models'], ref_list_attr='server-roles')

    # Delete interface models and disk models that aren't referenced by server roles
    prune_unused_items(input_model['interface-models'], ['server-roles'])
    prune_unused_items(input_model['disk-models'], ['server-roles'])

    for interface_model in input_model['interface-models'].itervalues():
        list_attr_to_map(interface_model, 'network-interfaces')
        for interface in interface_model['network-interfaces'].itervalues():
            interface['interface-model'] = interface_model
            foreign_key_list_attr_to_ref_list(interface, 'network-groups',
                                              input_model['network-groups'], ref_list_attr='network-interfaces')
            foreign_key_list_attr_to_ref_list(interface, 'forced-network-groups',
                                              input_model['network-groups'], ref_list_attr='network-interfaces')

    # Delete network groups that aren't referenced by network interfaces
    prune_unused_items(input_model['network-groups'], ['network-interfaces'])

    # Collect all network group tags in a single map, indexed by neutron group name
    neutron_network_tags = dict()
    # Collect all neutron provider/external networks in a single map, indexed by network name
    neutron_networks = input_model['neutron-networks'] = dict()

    def add_neutron_network_tags(network_group_name, tags):
        tag = neutron_network_tags.setdefault(network_group_name, {'network-group': network_group_name})
        foreign_key_attr_to_ref(tag, 'network-group',
                                input_model['network-groups'], ref_list_attr='neutron-tags',
                                key_attr=None)  # Use a null key_attr value to create a list of references
        tag.setdefault('tags', []).extend(tags)

    if neutron_config_data:
        # Starting in SUSE OpenStack Cloud 8, network tags may be defined as part of a Neutron configuration-data
        # object rather than as part of a network-group object.
        for network_tag in neutron_config_data.get('network-tags', []):
            add_neutron_network_tags(network_tag['network-group'], network_tag['tags'])

        external_networks = list_attr_to_map(neutron_config_data['data'], 'neutron_external_networks')
        provider_networks = list_attr_to_map(neutron_config_data['data'], 'neutron_provider_networks')
        neutron_networks.update(external_networks)
        neutron_networks.update(provider_networks)
        for network in external_networks.itervalues():
            network['external'] = True
        for network in provider_networks.itervalues():
            network['external'] = False

    for network_group in input_model['network-groups'].itervalues():
        if neutron_config_data and 'tags' in network_group:
            add_neutron_network_tags(network_group['name'], network_group['tags'])
        #foreign_key_list_attr_to_ref_list(network_group, 'load-balancers', network_group, ref_list_attr='network-groups')
        foreign_key_list_attr_to_ref_list(network_group, 'routes',
                                          input_model['network-groups'], ref_list_attr='network-group-routes')
        foreign_key_list_attr_to_ref_list(network_group, 'routes',
                                          neutron_networks, ref_list_attr='network-group-routes')

    # Based on the collected neutron networks and network tags, identify
    # which network group is linked to which neutron network, by looking
    # at the provider physical network settings
    neutron_physnets = dict()
    for neutron_network in neutron_networks.itervalues():
        # The only neutron network without a provider is the external "bridge" network.
        # Assume a default 'external' physnet value for this network.
        if 'provider' not in neutron_network:
            if neutron_network['external']:
                physnet='external'
            else:
                continue
        else:
            physnet = neutron_network['provider'][0]['physical_network']
        neutron_physnets[physnet] = neutron_network
    for network_tag in neutron_network_tags.itervalues():
        for tag in network_tag['tags']:
            if isinstance(tag, dict):
                tag = tag.values()[0]
            # The only relevant tag without a provider is the external "bridge" network.
            # Assume a default 'external' physnet value for this network.
            if 'provider-physical-network' not in tag:
                if tag == 'neutron.l3_agent.external_network_bridge':
                    physnet = 'external'
                else:
                    continue
            else:
                physnet = tag['provider-physical-network']
            if physnet not in neutron_physnets:
                continue

            # Create a 'neutron-networks' attribute in the network group element as
            # a map of neutron networks indexed by physical network name
            network_tag['network-group'].setdefault('neutron-networks', dict())[physnet] = neutron_physnets[physnet]
            # Create a 'network-groups' attribute in the neutron network element as
            # a map of neutron groups indexed by network group name
            neutron_physnets[physnet].setdefault('network-groups', dict())[network_tag['network-group']['name']] = network_tag['network-group']

    # Delete networks that reference a non-existing network group
    input_model['networks'] = \
        OrderedDict(filter(lambda net: net[1]['network-group'] in input_model['network-groups'],
                           input_model['networks'].items()))

    for network in input_model['networks'].itervalues():
        foreign_key_attr_to_ref(network, 'network-group',
                                input_model['network-groups'], ref_list_attr='networks')

    # Delete firewall rules that reference a non-existing network group
    input_model['firewall-rules'] = \
        OrderedDict(filter(lambda rule: not set(rule[1]['network-groups']) - set(input_model['network-groups'].keys()),
                           input_model['firewall-rules'].items()))

    for firewall_rule in input_model['firewall-rules'].itervalues():
        foreign_key_list_attr_to_ref_list(firewall_rule, 'network-groups',
                                          input_model['network-groups'], ref_list_attr='firewall-rules')

    # Delete servers that reference a non-existing server role
    input_model['servers'] = \
        OrderedDict(filter(lambda server: server[1]['role'] in input_model['server-roles'],
                           input_model['servers'].items()))

    for server in input_model['servers'].itervalues():
        foreign_key_attr_to_ref(server, 'role', input_model['server-roles'],
                                ref_list_attr='servers', key_attr='id')
        foreign_key_attr_to_ref(server, 'nic-mapping', input_model['nic-mappings'],
                                ref_list_attr='servers', key_attr='id')
        foreign_key_attr_to_ref(server, 'server-group', input_model['server-groups'],
                                ref_list_attr='servers', key_attr='id')

    # Delete NIC mappings that aren't referenced by servers
    prune_unused_items(input_model['nic-mappings'], ['servers'])

    for server_group in input_model['server-groups'].itervalues():
        foreign_key_list_attr_to_ref_list(server_group, 'networks',
                                          input_model['networks'], ref_list_attr='server-groups')
        foreign_key_list_attr_to_ref_list(server_group, 'server-groups',
                                          input_model['server-groups'], ref_list_attr='server-group-parents')

    # Delete server groups that aren't referenced by servers or other server groups
    prune_unused_items(input_model['server-groups'], ['servers', 'server-group-parents'])

    return input_model


def generate_heat_model(input_model, virt_config):
    """
    Create a data structure that more or less describes the heat resources required to deploy
    the input model. The data structure can then later be used to generate a heat orchestration
    template.

    :param input_model: enhanced input model data structure
    :param virt_config: additional information regarding the virtual setup (images, flavors, disk sizes)
    :return: dictionary describing heat resources
    """
    heat_template = dict(
        description='Template for deploying Ardana {}'.format(input_model['cloud']['name'])
    )

    clm_cidr = IPNetwork(input_model['baremetal']['subnet'],
                         input_model['baremetal']['netmask'])
    clm_network = None
    heat_networks = heat_template['networks'] = dict()

    # First, add L2 neutron provider networks defined in the input model's neutron configuration
    for neutron_network in input_model['neutron-networks'].itervalues():
        heat_network = dict(
            name=neutron_network['name'],
            is_mgmt=False,
            external=neutron_network['external']
        )
        if neutron_network.get('cidr'):
            heat_network['cidr'] = neutron_network['cidr']
        if neutron_network.get('gateway'):
            heat_network['gateway'] = neutron_network['gateway']
        if neutron_network.get('provider'):
            provider = neutron_network['provider'][0]
            if provider['network_type'] == 'vlan':
                if not provider.get('segmentation_id'):
                    # Neutron network is incompletely defined (VLAN tag is dynamically allocated),
                    # so it cannot be defined as an individual heat network
                    continue
                heat_network['vlan'] = provider['segmentation_id']
            elif provider['network_type'] not in ['flat', 'vlan']:
                # Only layer 2 neutron provider networks are considered
                continue
        heat_networks[heat_network['name']] = heat_network

    # Collect all the routers required by routes configured in the input model,
    # as pairs of networks
    routers = set()

    # Next, add global networks
    for network in input_model['networks'].itervalues():
        cidr = None
        vlan = network['vlanid'] if network.get('tagged-vlan') else None
        gateway = IPAddress(network['gateway-ip']) if network.get('gateway-ip') else None
        if network.get('cidr'):
            cidr = IPNetwork(network['cidr'])

        heat_network = dict(
            name=network['name'],
            is_mgmt=False,
            external=False
        )
        if cidr:
            heat_network['cidr'] = str(cidr)
        if gateway:
            heat_network['gateway'] = str(gateway)

        # There is the special case of global networks being used to implement flat neutron provider
        # networks. For these networks, we need to create a heat network based on the global network
        # parameters (i.e. VLAN) and a heat subnet based on the neutron network parameters
        for neutron_network in network['network-group'].get('neutron-networks', {}).itervalues():
            heat_neutron_network = heat_networks.get(neutron_network['name'])
            if not heat_neutron_network or heat_neutron_network.get('vlan'):
                # Ignore neutron networks that:
                #   - were not already considered at the previous step (i.e. are not fully defined
                #   or are not layer 2 based)
                #   - have a vlan (i.e. are not flat)
                continue

            # Replace the heat neutron network with this global network
            # This is the same as updating the heat global network with subnet attributes
            # taken from the neutron network
            del heat_networks[neutron_network['name']]
            heat_network = heat_neutron_network
            heat_network['name'] = network['name']

            # Only one flat neutron provider network can be associated with a global network
            break

        if vlan:
            heat_network['vlan'] = vlan

        # For each route, track down the target network
        for route in network['network-group']['routes']:
            if route == 'default':
                # The default route is satisfied by adding the network to the external router
                heat_network['external'] = True
            else:
                routers.add((heat_network['name'], route['name'],))

        if cidr == clm_cidr:
            clm_network = heat_network
            heat_network['external'] = heat_network['is_mgmt'] = True

            # Create an address pool range that excludes the list of server static IP addresses
            fixed_ip_addr_list = [IPAddress(server['ip-addr'])
                                  for server in input_model['servers'].itervalues()]
            if gateway:
                fixed_ip_addr_list.append(gateway)
            start_addr = clm_cidr[1]
            end_addr = clm_cidr[-2]
            for fixed_ip_addr in sorted(list(set(fixed_ip_addr_list))):
                if start_addr <= fixed_ip_addr <= end_addr:
                    if fixed_ip_addr-start_addr < end_addr-fixed_ip_addr:
                        start_addr=fixed_ip_addr+1
                    else:
                        end_addr = fixed_ip_addr-1
            heat_network['allocation_pools'] = [[str(start_addr), str(end_addr)]]

        heat_networks[network['name']] = heat_network

    heat_template['routers'] = []
    for network1, network2 in routers:
        if network1 not in heat_template['networks'] or \
           network2 not in heat_template['networks']:
            continue
        network1 = heat_template['networks'][network1]
        network2 = heat_template['networks'][network2]
        # Re-use the external router, if at least one of the networks is already
        # attached to it
        if network1['external'] or network2['external']:
            network1['external'] = network2['external'] = True
        else:
            heat_template['routers'].append([network1['name'], network2['name']])

    heat_interface_models = heat_template['interface_models'] = dict()

    for interface_model in input_model['interface-models'].itervalues():
        heat_interface_model = heat_interface_models[interface_model['name']] = dict(
            name=interface_model['name'],
            ports=[]
        )
        ports = dict()
        clm_ports = dict()
        for interface in interface_model['network-interfaces'].itervalues():
            devices = interface['bond-data']['devices'] if 'bond-data' in interface else [interface['device']]
            for device in devices:
                port_list = ports
                port = dict(
                    name=device['name'],
                    networks=[]
                )
                if 'bond-data' in interface:
                    port['bond'] = interface['device']['name']
                    port['primary'] = (device['name'] == interface['bond-data']['options'].get('primary', device['name']))

                for network_group in interface.get('network-groups', []) + interface.get('forced-network-groups', []):
                    port['networks'].extend([network['name']
                                             for network in network_group['networks'].itervalues()])
                    # Attach the port only to those neutron networks that have been validated during the previous steps
                    port['networks'].extend([network['name']
                                             for network in network_group.get('neutron-networks', dict()).itervalues()
                                             if network['name'] in heat_networks])

                    if clm_network['name'] in network_group['networks']:
                        # if the CLM port is a bond port, then only the primary is considered if configured
                        if not clm_ports and port.get('primary', True):
                            # Collect the CLM port separately, to put it at the top of the list and
                            # to mark it as the "management" port - the port to which the server's
                            # management IP address is assigned
                            port_list = clm_ports

                port_list[device['name']] = port

        # Add a port for each device, starting with those ports attached to the CLM network
        # while at the same time preserving the order of the original ports. Ultimately,
        # the port names will be re-aligned to those in the input model by an updated NIC
        # mappings input model configuration
        heat_interface_model['ports'] =[port[1]
                                        for _, port in enumerate(sorted(clm_ports.items()) + sorted(ports.items()))]

    # Generate storage setup (volumes)
    #
    # General strategy:
    #  - one volume for each physical volume specified in the disk model
    #  - the size of each volume cannot be determined from the input model,
    #  so this information needs to be supplied separately (TBD)

    heat_disk_models = heat_template['disk_models'] = dict()
    disks = virt_config['disks']

    for disk_model in input_model['disk-models'].itervalues():
        heat_disk_model = heat_disk_models[disk_model['name']] = dict(
            name=disk_model['name'],
            volumes=[]
        )
        devices = []
        for volume_group in disk_model.get('volume-groups', []):
            devices += volume_group['physical-volumes']
        for device_group in disk_model.get('device-groups', []):
            devices += [device['name'] for device in device_group['devices']]
        for device in sorted(list(set(devices))):
            if device == '/dev/sda_root': continue
            device = device.replace('/dev/sd', '/dev/vd')
            volume_name = device.replace('/dev/', '')
            size = disks.get(disk_model['name'], disks['default'])
            if isinstance(size, dict):
                size = size.get(volume_name, size.get('default', disks['default']))
            heat_disk_model['volumes'].append(dict(
                name=volume_name,
                mountpoint=device,
                size=size
            ))

    # Generate VM setup (servers)
    #
    # General strategy:
    #  - one server for each server specified in the disk model
    #  - the CLM server is special:
    #    - identification: server hosting the lifecycle-manager service component
    #    - the floating IP is associated with the "CLM" port attached to it
    #  - the image and flavor used for the server cannot be determined from the input model
    #  so this information needs to be supplied separately (TBD)

    heat_servers = heat_template['servers'] = []
    images = virt_config['images']
    flavors = virt_config['flavors']

    clm_server = None
    for server in input_model['servers'].itervalues():

        heat_server = dict(
            name=server['id'],
            ip_addr=server['ip-addr'],
            role=server['role']['name'],
            interface_model=server['role']['interface-model']['name'],
            disk_model=server['role']['disk-model']['name'],
            image=images.get(server['id'], images.get(server['role']['name'], images['default']))[server.get('distro-id', virt_config['default_distro_id'])],
            flavor=flavors.get(server['id'], flavors.get(server['role']['name'])),
            is_admin=False,
            is_controller=False,
            is_compute=False
        )
        # Figure out which server is the CLM host, which are controllers and which are computes
        for service_group in server['role'].get('clusters', {}).values() + server['role'].get('resources', {}).values():
            # The CLM server is the first server hosting the lifecycle-manager service component
            # Compute nodes host the nova-compute service component
            if 'nova-compute' in service_group['service-components']:
                heat_server['is_compute'] = True
                if not heat_server['flavor']:
                    heat_server['flavor'] = flavors['default_compute_flavor']
            # Every server that is not a compute node and hosts service components
            # other than those required by the CLM is considered a controller node
            else:
                if filter(lambda sc: sc not in virt_config['clm_service_components'],
                          service_group['service-components']):
                    heat_server['is_controller'] = True
                    if not heat_server['flavor']:
                        heat_server['flavor'] = flavors['default_controller_flavor']
            if not clm_server and 'lifecycle-manager' in service_group['service-components']:
                clm_server = heat_server
                heat_server['is_admin'] = True
                if not heat_server['flavor']:
                    heat_server['flavor'] = flavors['default_clm_flavor']

        heat_servers.append(heat_server)

    return heat_template

def update_input_model(input_model, heat_template):
    """
    Updates the input model structure with the correct values required to reflect the
    virtual setup defined in the generated heat template model:
      - generate new NIC mappings
      - update the selected servers to use the new NIC mappings

    :param input_model:
    :param heat_template:
    :return:
    """
    for server in input_model['servers']:
        heat_server = filter(lambda s: server['id'] == s['name'], heat_template['servers'])
        if not heat_server:
            # Skip servers that have been filtered out by the heat template generator
            continue
        server['nic-mapping'] = "HEAT-{}".format(heat_server[0]['interface_model'])

    for interface_model in heat_template['interface_models'].itervalues():
        mapping_name = "HEAT-{}".format(interface_model['name'])
        physical_ports = []
        nic_mapping = {
            'name': mapping_name,
            'physical-ports': physical_ports
        }
        for port_idx, port in enumerate(interface_model['ports']):
            physical_ports.append({
                'logical-name': port['name'],
                'type': 'simple-port',
                'bus-address': "0000:00:{:02x}.0".format(port_idx+3)
            })

        # Overwrite the mapping, if it's already defined
        existing_mapping = filter(lambda mapping: mapping[1]['name'] == mapping_name, enumerate(input_model['nic-mappings']))
        if existing_mapping:
            input_model['nic-mappings'][existing_mapping[0][0]] = nic_mapping
        else:
            input_model['nic-mappings'].append(nic_mapping)

    return input_model

def main():

    argument_spec = dict(
        input_model=dict(type='dict', required=True),
        virt_config=dict(type='dict', required=True)
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False)
    input_model = module.params['input_model']
    virt_config = module.params['virt_config']
    try:
        enhanced_input_model = enhance_input_model(input_model)
        heat_template = generate_heat_model(enhanced_input_model, virt_config)
        input_model = update_input_model(input_model, heat_template)
    except Exception as e:
        module.fail_json(msg=e.message)
    module.exit_json(rc=0, changed=False,
                     heat_template=heat_template,
                     input_model=input_model)


from ansible.module_utils.basic import AnsibleModule

if __name__ == '__main__':
    main()
