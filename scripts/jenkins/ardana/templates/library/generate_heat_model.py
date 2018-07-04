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
  describing a heat orchestration template.
author: SUSE Linux GmbH
options:
  input_model: 
    description: Input model data structure 
'''

EXAMPLES = '''
- generate_heat_model:
    input_model: '{{ input_model }}'
  register: _result
- debug: msg="{{ _result.heat_template }}"
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

    def convert_list_attr_to_map(element, attr_name, key='name'):
        if attr_name in element:
            element[attr_name] = OrderedDict({item[key]: item for item in element[attr_name]})
        else:
            element[attr_name] = OrderedDict()

    def link_attr_to_element(element, attr_name, target_map, ref_list_attr=None):
        key = element.setdefault(attr_name)
        if isinstance(key, basestring) and key in target_map:
            element[attr_name] = target_map[key]
            if ref_list_attr:
                target_map[key].setdefault(ref_list_attr, OrderedDict())[element.get('name', element.get('id'))] = element

    def link_attr_list_to_element(element, attr_name, target_map, ref_list_attr=None):
        key_list = element.setdefault(attr_name, [])
        for idx, key in enumerate(key_list):
            if isinstance(key, basestring) and key in target_map:
                key_list[idx] = target_map[key]
                if ref_list_attr:
                    target_map[key].setdefault(ref_list_attr, OrderedDict())[element.get('name', element.get('id'))] = element

    def prune_unused_items(element_map, ref_list_attrs):
        for name, element in element_map.items():
            for ref_list_attr in ref_list_attrs:
                if element.get(ref_list_attr):
                    break
            else:
                continue
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
                           # NOTE: servers are intentionally kept as a list because the order is significant
                           # e.g. when deciding how many of them to keep as compute nodes
                           # 'servers',
                           'server-groups',
                           'firewall-rules']:
        convert_list_attr_to_map(input_model, top_level_list,
                                 'id' if top_level_list == 'servers' else 'name')

    for cp in input_model['control-planes'].itervalues():
        convert_list_attr_to_map(cp, 'load-balancers')
        convert_list_attr_to_map(cp, 'clusters')
        convert_list_attr_to_map(cp, 'resources')
        link_attr_list_to_element(cp, 'configuration-data', input_model['configuration-data'], ref_list_attr='control-planes')
        for cluster in cp['clusters'].itervalues():
            link_attr_to_element(cluster, 'server-role', input_model['server-roles'], ref_list_attr='clusters')
            link_attr_list_to_element(cluster, 'configuration-data', input_model['configuration-data'], ref_list_attr='clusters')
        for resource in cp['resources'].itervalues():
            link_attr_to_element(resource, 'server-role', input_model['server-roles'], ref_list_attr='resources')
            link_attr_list_to_element(resource, 'configuration-data', input_model['configuration-data'], ref_list_attr='resources')

    # Delete configuration elements that aren't referenced by
    # control planes, clusters or resources
    prune_unused_items(input_model['configuration-data'], ['control-planes', 'clusters', 'resources'])

    # Delete server roles that aren't referenced by clusters or resources
    prune_unused_items(input_model['server-roles'], ['clusters', 'resources'])

    for server_role in input_model['server-roles'].itervalues():
        link_attr_to_element(server_role, 'interface-model', input_model['interface-models'], ref_list_attr='server-roles')
        link_attr_to_element(server_role, 'disk-model', input_model['disk-models'], ref_list_attr='server-roles')

    # Delete interface models and disk models that aren't referenced by server roles
    prune_unused_items(input_model['interface-models'], ['server-roles'])
    prune_unused_items(input_model['disk-models'], ['server-roles'])

    for interface_model in input_model['interface-models'].itervalues():
        convert_list_attr_to_map(interface_model, 'network-interfaces')
        for interface in interface_model['network-interfaces'].itervalues():
            link_attr_list_to_element(interface, 'network-groups', input_model['network-groups'], ref_list_attr='interface-models')
            link_attr_list_to_element(interface, 'forced-network-groups', input_model['network-groups'], ref_list_attr='interface-models')

    # Delete network groups that aren't referenced by interface models
    prune_unused_items(input_model['network-groups'], ['interface-models'])

    for network_group in input_model['network-groups'].itervalues():
        #link_attr_list_to_element(network_group, 'load-balancers', network_group, ref_list_attr='network-groups')
        # TBD: include neutron networks here (i.e. iterate through neutron config networks
        # and call the same function) !
        link_attr_list_to_element(network_group, 'routes', input_model['network-groups'], ref_list_attr='network-group-routes')

    # Delete networks that reference a non-existing network group
    input_model['networks'] = \
        OrderedDict(filter(lambda net: net[1]['network-group'] in input_model['network-groups'],
                           input_model['networks'].items()))

    for network in input_model['networks'].itervalues():
        link_attr_to_element(network, 'network-group', input_model['network-groups'], ref_list_attr='networks')

    # Delete firewall rules that reference a non-existing network group
    input_model['firewall-rules'] = \
        OrderedDict(filter(lambda rule: not set(rule[1]['network-groups']) - set(input_model['network-groups'].keys()),
                           input_model['firewall-rules'].items()))

    for firewall_rule in input_model['firewall-rules'].itervalues():
        link_attr_list_to_element(firewall_rule, 'network-groups', input_model['network-groups'], ref_list_attr='firewall-rules')

    # Delete servers that reference a non-existing server role
    input_model['servers'] = filter(lambda server: server['role'] in input_model['server-roles'],
                                    input_model['servers'])

    for server in input_model['servers']:
        link_attr_to_element(server, 'role', input_model['server-roles'], ref_list_attr='servers')
        link_attr_to_element(server, 'nic-mapping', input_model['nic-mappings'], ref_list_attr='servers')
        link_attr_to_element(server, 'server-group', input_model['server-groups'], ref_list_attr='servers')

    # Delete NIC mappings that aren't referenced by servers
    prune_unused_items(input_model['nic-mappings'], ['servers'])

    for server_group in input_model['server-groups'].itervalues():
        link_attr_list_to_element(server_group, 'networks', input_model['networks'], ref_list_attr='server-groups')
        link_attr_list_to_element(server_group, 'server-groups', input_model['server-groups'], ref_list_attr='server-group-parents')

    # Delete server groups that aren't referenced by servers or other server groups
    prune_unused_items(input_model['server-groups'], ['servers', 'server-group-parents'])

    return input_model


def generate_heat_model(input_model):
    """
    Create a data structure that more or less describes the heat resources required to deploy
    the input model. The data structure can then later be used to generate a heat orchestration
    template.

    :param input_model:
    :return: dictionary describing heat resources
    """
    heat_template = OrderedDict()

    # Generate networks setup (networks, subnets, routers)
    #
    # General strategy:
    #  - one heat network and one subnet resources are created for every network in the input model
    #  - the CIDR and gateway settings for the subnet are taken from the input model
    #  network configuration, when supplied. If a CIDR is not supplied and there are no
    #  other means of determining the CIDR (see special network handling below), one will be generated
    #  - dhcp is turned off for the subnet, with the exception of the "CLM" network (see below)
    #
    # The following are networks that require special handling:
    #  - the "CLM" network:
    #    - identification: the input model network with the same CIDR value as that configured
    #    in the baremetal server settings
    #    - the heat subnet CIDR must be the same as that configured for the input model network
    #    - DHCP must be enabled and the IP addresses allocated to VMs must correspond exactly to
    #    those configured in the server settings
    #    - the heat subnet must be connected to the external router (see next point)
    #    - a floating IP must be associated with the "CLM" IP of the "CLM" node
    #    NOTE: this network is also associated with the lifecycle manager component endpoints,
    #    because the server IP addresses belong to it and this is the only
    #    connectivity info that the CLM has associated with the configured the servers
    #  - neutron external networks:
    #    - identification: network references a network group tagged with
    #    neutron.l3_agent.external_network_bridge
    #    - the CIDR and gateway are not specified for this input model network. They must be
    #    taken from the neutron configuration data, if present
    #    - the heat subnet must be connected to the external router to provide external access
    #    - all this is needed to make the network behave like an external network
    #  - neutron provider networks:
    #    - identification: tagged with neutron.networks.<vlan/vxlan/...>
    #    - a CIDR and gateway are usually configured for the input model network if needed by underlay (vxlan/gre)
    #    Q: what happens when this is shared (e.g. with the "management" network) ?
    #  - the Ardana VMs need access to the "external API" network via the neutron external networks and vice-versa
    #    - the "external API" network must be added to the external router
    #  - networks-groups with routes configured. The route can point to either:
    #    - default: this network needs external access (needs to be added to the external router)
    #    - one of the other global networks: both global networks need to be added to the same router
    #    (not the external router, if at least one of them doesn't need external access)
    #    NOTE: this means that there's another route configured for the other network, or that its
    #    default route leads to this network
    #    - one of the neutron networks: both this network and the one used to implement the
    #    neutron network need to be added to the same router (not the external router, if at least one of them
    #    doesn't need external access)
    #    NOTE: this means that there's another route configured for the other network, or that its
    #    default route leads to this network

    # Get default CIDR for external neutron networks
    # { %
    # for network_group in input_model['network-groups'] if network['network-group'] == network_group.name and
    #                 'neutron.l3_agent.external_network_bridge' in network_group.tags | default([]) %}
    # { %
    # for config_data in ns.cp['configuration-data'] if 'neutron' in input_model['configuration-data'][config_data] %}
    # { %
    # for ext_net in input_model['configuration-data'][config_data].data.neutron_external_networks | default([]) %}
    # { % set
    # ns.default_cidr = ext_net.cidr %}
    # { % set
    # ns.default_gateway = ext_net.gateway %}
    # { % endfor %}
    # { % endfor %}
    # { % endfor %}

    clm_cidr = IPNetwork(input_model['baremetal']['subnet'],
                         input_model['baremetal']['netmask'])
    networks = heat_template['networks'] = OrderedDict()
    for network in input_model['networks'].itervalues():

        net_name = re.sub('_net$', '', network['name'].lower().replace('-', '_').replace('_net$', ''))
        if network.get('cidr'):
            cidr = IPNetwork(network['cidr'])
        elif 'neutron.l3_agent.external_network_bridge' in network['network-group'].get('tags', []):
            pass
        gateway = IPAddress(network['gateway-ip']) if network.get('gateway-ip') else None

        heat_network = OrderedDict({
            'name': net_name,
            'enable_dhcp': cidr == clm_cidr
        })

        if cidr:
            heat_network['cidr'] = str(cidr)
        if gateway:
            heat_network['gateway'] = str(gateway)

        networks[heat_network['name']] = heat_network

    return heat_template


def main():

    argument_spec = dict(
        input_model=dict(type='dict', required=True)
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False)
    input_model = module.params['input_model']
    try:
        input_model = enhance_input_model(input_model)
        heat_template = generate_heat_model(input_model)
    except Exception as e:
        module.fail_json(msg=e.message)
    module.exit_json(rc=0, changed=False, heat_template=heat_template)


from ansible.module_utils.basic import AnsibleModule
if __name__ == '__main__':
    main()
