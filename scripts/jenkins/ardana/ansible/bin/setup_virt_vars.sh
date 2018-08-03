#!/usr/bin/env bash

set -ex

NETWORK_MGMT_ID=$(openstack --os-cloud ${os_cloud} stack output show $heat_stack_name mgmt-network-id -c output_value -f value)
sed -i "s/^ardana-virt.*/ardana-virt      ansible_host=$CLM_IP/g" inventory

cat inventory

cat << EOF > host_vars/ardana-virt.yml
---
input_model_path: "$input_model_path"
deployer_mgmt_ip: $(openstack --os-cloud ${os_cloud} stack output show $heat_stack_name admin-mgmt-ip -c output_value -f value)
EOF

controller_mgmt_ips=$(openstack --os-cloud ${os_cloud} stack output show $heat_stack_name controller-mgmt-ips -c output_value -f value|grep -o '[0-9.]*')
if [ -n "$controller_mgmt_ips" ]; then
echo "controller_mgmt_ips:" >> host_vars/ardana-virt.yml
for ip in $controller_mgmt_ips; do
    cat << EOF >> host_vars/ardana-virt.yml
  - $ip
EOF
done
fi

compute_mgmt_ips=$(openstack --os-cloud ${os_cloud} stack output show $heat_stack_name compute-mgmt-ips -c output_value -f value|grep -o '[0-9.]*')
if [ -n "$compute_mgmt_ips" ]; then
echo "compute_mgmt_ips:" >> host_vars/ardana-virt.yml
for ip in $compute_mgmt_ips; do
    cat << EOF >> host_vars/ardana-virt.yml
  - $ip
EOF
done
fi

# Get the IP addresses of the dns servers from the mgmt network
echo "mgmt_dnsservers:" >> host_vars/ardana-virt.yml
openstack --os-cloud ${os_cloud} port list --network $NETWORK_MGMT_ID \
        --device-owner network:dhcp -f value -c 'Fixed IP Addresses' | \
  sed -e "s/^ip_address='\(.*\)', .*$/\1/" | \
  while read line; do echo "  - $line" >> host_vars/ardana-virt.yml; done;

cat host_vars/ardana-virt.yml
