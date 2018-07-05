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

    def list_attr_to_map(element, attr_name, key='name'):
        if attr_name in element:
            element[attr_name] = OrderedDict({item[key]: item for item in element[attr_name]})
        else:
            element[attr_name] = OrderedDict()

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
                target_map[foreign_key].setdefault(ref_list_attr, OrderedDict())[element[key_attr]] = element

    def foreign_key_list_attr_to_ref_list(element, attr_name, target_map, ref_list_attr=None, key_attr='name'):
        foreign_key_list = element.setdefault(attr_name, [])
        for idx, foreign_key in enumerate(foreign_key_list):
            if isinstance(foreign_key, basestring) and foreign_key in target_map:
                foreign_key_list[idx] = target_map[foreign_key]
                if ref_list_attr:
                    target_map[foreign_key].setdefault(ref_list_attr, OrderedDict())[element[key_attr]] = element

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
                           # NOTE: servers are intentionally kept as a list because the order is significant
                           # e.g. when deciding how many of them to keep as compute nodes
                           # 'servers',
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

    input_model['neutron-config-data'] = neutron_config_data
    list_attr_to_map(input_model, 'neutron-config-data')

    # Delete configuration elements that aren't referenced by
    # control planes, clusters or resources
    prune_unused_items(input_model['configuration-data'], ['control-planes', 'clusters', 'resources'])

    # Delete server roles that aren't referenced by clusters or resources
    prune_unused_items(input_model['server-roles'], ['clusters', 'resources'])

    for server_role in input_model['server-roles'].itervalues():
        # NOTE: for now assume there is a single control plane
        server_role['control-plane'] = server_role.get('clusters', server_role.get('resources')).values()[0][
            'control-plane']
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

    for network_group in input_model['network-groups'].itervalues():
        tags = network_group.get('tags', [])
        '''
        if 'neutron.networks.vlan' in tags or 'neutron.networks.flat' in tags:
            provider_net = ... ['provider-physical-network']
        elif 'neutron.networks.vxlan' in tags:
        elif 'neutron.l3_agent.external_network_bridge' in tags:
        '''


            #foreign_key_list_attr_to_ref_list(network_group, 'load-balancers', network_group, ref_list_attr='network-groups')
        # TBD: include neutron networks here (i.e. iterate through neutron config networks
        # and call the same function) !
        foreign_key_list_attr_to_ref_list(network_group, 'routes',
                                          input_model['network-groups'], ref_list_attr='network-group-routes')

    # Delete networks that reference a non-existing network group
    input_model['networks'] = \
        OrderedDict(filter(lambda net: net[1]['network-group'] in input_model['network-groups'],
                           input_model['networks'].items()))

    for network in input_model['networks'].itervalues():
        foreign_key_attr_to_ref(network, 'network-group', input_model['network-groups'], ref_list_attr='networks')

    # Delete firewall rules that reference a non-existing network group
    input_model['firewall-rules'] = \
        OrderedDict(filter(lambda rule: not set(rule[1]['network-groups']) - set(input_model['network-groups'].keys()),
                           input_model['firewall-rules'].items()))

    for firewall_rule in input_model['firewall-rules'].itervalues():
        foreign_key_list_attr_to_ref_list(firewall_rule, 'network-groups', input_model['network-groups'], ref_list_attr='firewall-rules')

    # Delete servers that reference a non-existing server role
    input_model['servers'] = filter(lambda server: server['role'] in input_model['server-roles'],
                                    input_model['servers'])

    for server in input_model['servers']:
        foreign_key_attr_to_ref(server, 'role', input_model['server-roles'], ref_list_attr='servers', key_attr='id')
        foreign_key_attr_to_ref(server, 'nic-mapping', input_model['nic-mappings'], ref_list_attr='servers', key_attr='id')
        foreign_key_attr_to_ref(server, 'server-group', input_model['server-groups'], ref_list_attr='servers', key_attr='id')

    # Delete NIC mappings that aren't referenced by servers
    prune_unused_items(input_model['nic-mappings'], ['servers'])

    for server_group in input_model['server-groups'].itervalues():
        foreign_key_list_attr_to_ref_list(server_group, 'networks', input_model['networks'], ref_list_attr='server-groups')
        foreign_key_list_attr_to_ref_list(server_group, 'server-groups', input_model['server-groups'], ref_list_attr='server-group-parents')

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
