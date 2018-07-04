This etherpad contains notes on the effort of unifying the automation tools and scripts currently being used by two individual processes, each with
its dedicated git repository: the Ardana regression CI (backed by \url{https://github.com/SUSE-Cloud/automation/} and implemented as
\url{https://ci.suse.de/view/Cloud/view/Cloud8%20Ardana/} ) and the Ardana QA automation (backed by \url{https://gitlab.suse.de/flaviosr/ardana-deploy/}
and implemented as \url{http://10.84.144.253:8080/view/Ardana%20Automation/} ).

###Overview


   * QA setups are often reused during subsequent (re)runs of different stages. For instance, a setup, once deployed, might be reused to run the
   * update workflow periodically. Having separate roles and top-level playbooks for the different cloud operations (install CLM, deploy, update, run
   * tempest) makes this possible. The virtual deployments created by the CI are ephemeral. Keeping them running and re-using them for subsequent
   * job runs is currently not possible, mostly because they have limited resources and run into out-of-memory errors not long after they are deployed.
   * However, this shouldn't stop us from allowing this feature, at least in theory, to be also applicable to virtual environments.
   *

   * SES integration and RHEL compute node support is not currently supported by the Ardana CI. The unification will also add these two missing items to the CI. Also, updating to specific MUs

   * associating a single input model with each QA h/w setup has a very limited flexibility. Ideally, every target QA h/w setup should
   * be able to accommodate several input models and test scenarios. There should be a way to decouple the "service" side of an input model definition
   * (i.e. describing which services are assigned to which roles etc.) from the "hardware" side (i.e. describing the available servers, interfaces etc.)
   * which would allow them to be defined independently and to be combined dynamically.
###Roles used by QA

**    - prepare\_deployer\_vm:**
        Target: gate-qeXXX
        User: root
        Starts a fresh SLES12-SP3 virtual machine from a pre-configured image which will be used as ardana deployer (ardana-qeXXX)
**    - bootstrap\_deployer:**
        Target: ardana-qeXXX (deployer)
        User: root
        1. Download Cloud and SLES medias and set them up as zypper repository
        2. Install ardana patterns
        3. Mount Cloud and SLES repos (Pool and Updates) locally from clouddata server and add them as zypper repository
        4. If maintenance updates are provided, will also mount the MU's repository and add them as zypper repository
        5. If the input model includes a RHEL compute,  will download the RHEL image and packages from \url{http://ardana.suse.provo.cloud/yum-extras/yum-internal-rhel73-20180118-1320.tgz}
        6. Run zypper update and ardana-init after updating, if there is a kernel update a reboot of the node will be triggered
**    - ardana\_deploy:**
        Target: ardana-qeXXX
        User: ardana
        1. Copy the input model to the deployer node
        2. If the input model includes a RHEL compute, will copy a playbook to enable an RHEL repository on deployer
        3. WIll cofigure ardana-extensions-ses and set rbd as glance default store if SES is enabled
        4. Run playbooks from openstack path (config-processor-run.yml, cobbler-deploy.yml, ready-deployment.yml, prepare-sles-grub2.yml,  bm-reimage.yml)
        5. Run playbooks to enable RHEL repo on deployer (set-deployer-rhel-repo.yml, ready-deployment.yml)
        6. If maintenance updates are provided, will add the maintenance update repos on the nodes provisioned by cobbler, update them and reboot if there is a kernel update
        7. Run the ardana playbooks from scratch folder: wipe\_disks.yml, site.yml, ardana-cloud-configure.yml
**    - ardana\_update**
        Target: ardana-qeXXX
        User: ardana
        Updates an existing ardana deployment with the provided maintenace updates
**    - ardana\_qe\_tests**
        Target: ardana-qeXXX
        User: ardana
        Run IVerify tests on the target QE environment
**    - ardana\_tempest**
        Target: ardana-qeXXX
        User: ardana
        Run tempest tests with the specified filter on the target QE environment
**    - ses\_ardana\_integration**
        Target: ardana-qeXXX
        User: ardana
        Configures and existing ardana deployment with SES (glance, nova, cinder, swift)
**    - ses\_configure**
        Target: ses-cluster
        User: root
        Configures an existing SES cluster for integration with ardana
**    - jenkins\_artifacts**
        Collects artificats to be stored by jenkins
**    - rocketchat\_notify**
        Reports deployment status/tests results on rocket chat
**    - sed\_to\_os\_health**
       Submit tests results to OpenStack-Health

###The Jenkins jobs

Notable differences between QA and CI:

   * the CI uses a single parameterized JJB (openstack-ardana) that runs all the required steps (install CLM, deploy, run tests, etc),
   * whereas QA has individual JJBs for each step (deploy, update, tempest, iverify, etc) which can be combined or run independently
   * and repeatedly on the same target setup. This ability on the QA side comes from the fact that the QA cloud setups are long-lived
   * and can be reused for subsequent job runs.
###The Jenkins worker host(s)

Notable differences between QA and CI:

   * Different ansible versions:
          * QA (the "gate" for every QA setup - e.g. gate.qa4.cloud.suse.de): (pip/venv based) 2.5.3
       * CI (10.86.0.5): (unknown source) 2.2.3
   * QA automation has optional integration with RocketChat
###Generating the input model

Notable differences between QA and CI:

   * infrastructure bits of QA input model (interfaces, network layout, disks layout) are dictated by the physical H/W.
   * They are specific for each of the target QA setup and therefore are fully stored in the repository (one input model for
   * each available QA setup. The CI input
   * model is partially templated, partially automated:
       * the input model (specified with a job input param) from *ardana-input-model/2.0/ardana-ci *is used as a baseline
       * servers.yml file is generated:
                  * variable number of controller/compute nodes and deployer/controller colocation are accepted as job input params
           * IP addresses are extracted from the heat stack, post-creation
       * dns-settings and ntp-servers are overwritten in cloudConfig.yml
       * the following files are replaced with versions stored in the automation repo for each input model:
           * disks\_controller.yml
           * firewall\_rules.yml
           * interfaces\_set\_1.yml
           * net\_global.yml
           * network\_groups.yml
           * nic\_mappings.yml
   * CI doesn't use cobbler:
       * some input model attributes required by cobbler (e.g. interface MAC addresses, ilo credentials) are just fake values
       * the node IP addresses are already assigned when the heat stack is created
###Installing the CLM

Both QA and CI deploy the CLM as a virtual machine.

Notable differences between QA and CI:

   * QA creates the CLM VM on the "gate" machine of the supplied QA setup, as a separate first step, whereas CI creates the entire virtual setup, including the CLM, as a heat stack
   * CI doesn't use cobbler (cloud nodes are already provisioned using the proper SLES/CentOS image, independently from the CLM); QA cloud nodes need to be provisioned using cobbler/bm-reimage, which requires the CLM to be already provisioned and have the proper images set up in cobbler (TODO: is this true for RHEL nodes ?) Yes, when the input model includes a RHEL compute we also download the RHEL image to the ardana home
###Deploying the cloud

Process should be almost the same.

Notable differences between QA and CI:

   * CI doesn't use cobbler. QA cloud nodes need to be provisioned using cobbler/bm-reimage
###Updating the cloud

Process should be almost the same.

##Proposed unification of QA/CI automation process

###Main targets


   * implement a template that can be used to generate a large number of input models (including those already being used by automation/QA) to be used by test automation or other purposes
       * uses a scenario descriptor as input, containing a limited amount of information that can be used to generate a large number of input models
       * allow service grouping to be configured independently from H/W or virtual infrastructure configuration
       * allow optional h/w based information to be supplied to fully define existing h/w setups
   * implement a template that can be used to generate a heat template from an input model
       * uses full definition of an input model as input
       * optionally uses additional information defined by the user, to refine the heat template
   * separate roles/top-level playbooks and JJBs for the various operations (install CLM, deploy, update, run-tempest, etc.)
       * roles/top-level playbooks/JJBs for cloud operations that are h/w-independent (e.g. deploy, update, run-tempest) must have the same definition for both virtual and h/w setups
###Concerns


   * sensitive data (RC credentials, username/passwords for QA H/W) shouldn't be stored in a public repository
###Limitations


   * cobbler test scenarios cannot be covered by virtual environments (TODO: confirm that this is indeed true)
   * Update: there seems to be a way to boot machines through iPXE in Openstack:
       * disable dhcp on the neutron management network
       * create and use a custom PXE glance image, as described here: \url{https://kimizhang.wordpress.com/2013/08/26/create-pxe-boot-image-for-openstack/}
   * not all network attachment configurations that can be modeled through an Ardana input model can be accurately emulated using openstack computes
###Input model generation - virtual case

The mid-scale input model provides a great example of how different service groups can be split and clustered independently from each-other. Most of the other
input models can be defined starting from the more general mid-scale case and applying one or more of the following modifications:

   * resizing a cluster (e.g. 1 CORE-ROLE nodes instead of 2)
   * merging two or more clusters (e.g. DBMQ-ROLE and MTRMON-ROLE as a single cluster)
   * removing a cluster (e.g. MTRMON-ROLE)
   * adding or removing common service components (e.g. monasca-agent and freezer-agent)
Inputs:

   * scenario template with the following information:
       * description of the way that services are grouped in clusters/resources
           * ability to indicate groups of services in addition to individual services, e.g.: CLM, core API services, database/rabbitmq services, MML services
           * number of servers assigned to each service group
       * description of the way component endpoints are grouped in network groups
           * ability to indicate groups of component endpoints in addition to individual component endpoints, e.g.: CLM, management, internal/external API
       * TBD
   * volume sizes for each *disk-model* used
   * flavor for each server role
Outputs:

   * full input model definition
       * server management subnet and IP addresses updated to those assigned by the heat stack (servers.yml)
       * **Q**: what are mac addresses used for ?
       * **A**: only used by cobbler to populate the net-boot configuration, so they're not relevant for virtual environments
       * NIC mappings updated to reflect the PCI bus addresses used by the heat stack (servers.yml and/or nic-mappings.yml)
       * NOTE: nic mappings are needed by Ardana to configure udev rules to pin down the order and names of interfaces, so these need to be accurate
       *

###Heat template generation from input model

General implementation:

   * networks
       * one OS network for each input model *network*
       * port security disabled, to allow any traffic between ports attached to this network
   * subnets
       * one OS subnet for each input model *network*
       * CIDR/DHCP settings are relevant only for the following:
           * the "management" network - the one used for the *bare-metal* server settings. IPs need to be correctly assigned to "management" interfaces during boot
           * cases involving routing between networks (e.g. external to management). Traffic between OS networks is routed according to the configured CIDRs.
   * ports/port attachments
       * bonds are emulated by attaching two (or more) ports to the same OS network/subnet (tested that this is possible)
       * limitation: cannot attach an OS port to several OS subnets, which means that an input model *interface-model/network-interfaces* element referencing several *network-groups* cannot be emulated with a virtual environment.
       * solution 1: override the *interface-model* definitions in the input model and split one-to-many references into one-to-one references
       * solution 2: use an OS network/subnet to represent several input model *network* elements (requires a more complex analysis of the whole networking model, to determine when this needs to be done)
       * solution 3: use a single OS network to represent all input model *network* elements and create one OS subnet for each port attachment
       * limitation: *nic-mappings* will not be reflected in the virtual environment
   * routers
       * one router to provide external access and floating IPs
   * router interfaces
       * attach to the external router every *network/network-group* which requires external access:
           * the "management" network. Required to implement access to the CLM node via a floating IP
           * the neutron "external" network(s) (those tagged with *neutron.l3\_agent.external\_network\_bridge*).
           * This is required:
                          * for Ardana hosted VMs to have external access
               * to enable access to the Ardana hosted VMs from other networks, via Ardana allocated floating IPs
           * TBD: some default/ routes and/or subnets also need to be configured to correspond to the neutron configuration
           * the "external API" network(s) ( those which have a *load-balancer *with a* public* *role* associated with them).
           * Required for two reasons:
               * to allow access to the external API from the management network (when both are not locally available)
               * TBD: this requires routes to be explictily configured
               * so that Ardana hosted VMs can have access to the public API (e.g. to accommodate scenarios such as magnum)
   * floating-ips
       * one: associated with the "management" IP address of the "deployer" node
       * problem: associating a floating IP with the "external API" VIP address
       * problem: how to "detect" which server is the "deployer" node
       * solution 1: the *server* with a *server-role* that has the 'lifecycle-manager' *service-component* associated with it. If several meet this criteria (i.e. a cluster), then the first one is chosen.
       * solution 2: use additional input from user, as an extension to the input model
   * volumes
       * one OS volume for each unique *volume-groups/physical-volumes and device-groups/devices* attribute occurrence in the *disk-models* element (excluding the templated /dev/sda\_root value)
       * limitation: the volume size cannot be determined from the input model
       * solution 1: use a predefined size for all virtual volumes
       * solution 2: determine the volume size based on the service(s) or service group(s) that will be using it and a predefined size associated with each service/service group
       * solution 3: use additional input info from user, as an extension to the input model, for some/all of the *disk-models* elements
   * volume attachments:
       * as determined by the *servers - server-roles - disk-models* relationship
   * servers:
       * one OS server for each *server* in the input model
       * limitation: the flavor cannot be determined from the input model
       * solution 1: use a predefined flavor for all OS servers (NOTE: also covers the root volume)
       * solution 2: determine the flavor based on the service(s) or service group(s) that will be running on it and a predefined flavor associated with each service/service group
       * solution 3: use additional input info from user, as an extension to the input model, for some/all of the *servers* elements or *service-roles* elements
       * problem: which image to use for each server ?
       * solution 1: determine the image distro based on the *servers/distro-id* attribute and a predefined set of images associated with each distro
       * solution 2: use additional input info from user, as an extension to the input model, for some/all of the *servers* elements or *service-roles* elements
       * solution 3: combination of 1. and 2.


###Reusable test automation tasks/modules

    1. bootstrapping the CLM VM (hardware scenarios)
    
    Inputs:
        - host hypervisor (e.g. the QE setup "gate")
        - image:
            - base SLES image file location or
            - snapshot image created from previous CLM installation
        - some network connectivity parameters specific to the QE setup
            - management IP address
            - TBD
        
    Outputs:
        - running VM
        
    Process:
    
    2. CLM installation (universal)
    
    Inputs:
        - CLM management IP
        - media/repositories
        
    Output:
        - base OS updated/rebooted to reflect the configured repos
        - CLM installed on the target machine
        
    Process:
    
    3. create CLM snapshot 
    
    
    4. generate input model
    
    Inputs:
        - scenario
            - service model
            - network model
            - disk model
            - scenario parameters (e.g. number of nodes in each cluster)
        - target resources
            - virtual model
                - flavors
            - hardware setup:
                - server list
                - h/w network layout
                - disk layout ?
                - NIC mappings
                
     Outputs:
        - complete input model
        - virtual configuration (virtual case):
            - flavors
            - images
                - SLES base image
                - RHEL base image
                - CLM snapshot
        
    5. generate heat template
    
    Inputs:
        - imput model (e.g. from 4, or existing input model from the ardana-input-model repo, QA setup or from a customer deployment, etc.
        - virtual configuration
            - external network (e.g. floating)
            - flavors
            - volume sizes
        
    Outputs:
        - heat template
     
    6. create virtual environment
    
    Inputs:
        - heat template from 5.
        
    Output:
        - virtual setup
    
    7. cloud installation (universal)
     
     Inputs:
        - CLM management IP
        - input model
        
     Output:
        - fully deployed cloud
     
     Process:
        - 
     
    8. update workflow
    
    9. tests (tempest, etc)
    
    TODO: SES
        - configure CLM (NOTE: new or existing deployment)
        - configure SES cluster
        - deploy SES (virtual)
        
    TODO: RHEL
    
    TODO: update input model on existing cloud (e.g. scale out an existing cluster or resource)
    
    TODO: scale setup