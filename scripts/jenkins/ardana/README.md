# Ardana automated CI/CD

Principles:

* modularized approach
  * a job is split into constituent atomic operations, parallelized and pipelined
  * allows individual operations to be reused, replayed or triggered manually
* parallelization - run in parallel everything that can be run in parallel:
  * operations of the same job
  * concurrent jobs
* fastfail
  * abort parallel operations if any single one fails and if that failure decides the global status
  * abort on outside trigger (e.g. the job has been canceled or superseded by a subsequent code change update)
  * some operations cannot be interrupted (e.g. creating the heat stack)and must run to completion, then the cleanup 
  operation needs to be run
* cleanup
  * clean everything for superseded/cancelled jobs
  * keep a backlog of saved job results, cleaned periodically or when a new job starts/ends

## Jenkins pipeline implementation strategy

* move as much as possible into the Jenkinsfile definition and out of the JJB file:
  * setting the agent node
  * setting the workspace
  * setting the job name
  * post build triggers
  * downstream job triggers (part of the pipeline now)
  * NOT the parameters, because:
    1. if the parameters are configured in the Jenkinsfile, they will overwrite those in the JJB
    after the first run
    2. the automated job that resyncs the Jenkins jobs in the automation repository with those configured
    in ci.suse.de will overwrite the parameters in the Jenkinsfile
* most stages should be implemented as ansible playbook calls
* use downstream jobs for tasks that can be externalized and executed on their own
  * these jobs will have a subset of the parameters that the main pipeline job accepts
* upstream/downstream execution strategy:
  * the downstream job has the option of reusing the workspace and agent node that is used
  by the upstream job. This is enforced:
    1. to avoid duplicating work between upstream/downstream (e.g. checking out the automation
    repository contents from version control)
    2. to enable sharing large amounts of data between jobs (e.g. generated input models) that would otherwise have
    to be transferred using other means (e.g. artifacts)
    3. to enable sharing the runtime environment (e.g. ansible inventory and variables) between multiple stages,
    which helps to keep the stage implementation closer to the form in which they are executed directly
    from a development environment
  * pass information back to the upstream job by setting them as environment variables in the
  downstream job and using the `.buildVariables` build job object attribute in the upstream job
  (NOTE: this is only possible if the downstream job is also a pipeline job)
* passing information from one stage to the next:
  * use ansible variables (host/group vars, extra vars) as much as possible
  * use build environment variables (which can only be set by using `env.<variable-name>` in a pipeline script block)
* use the lockable resources mechanism to throttle parallel builds and
implement a virtual resource management and scheduling
* use fast-fail for parallel stages where applicable to abort all the individual stages
comprising a parallel block when a single one fails
* the `clm_env` parameter determines a unique Jenkins workspace name, which is required to replay stages
* the `when` pipeline verb is used to conditionally skip stages (instead of checking conditions
inside the stage steps, which would show the stage as being always executed, regardless of result)


## Automation modules

### Gerrit change test package builder

Builds test packages corresponding to a list of gerrit.suse.provo.cloud reviews.

Input:

* list of gerrit change IDs
* IBS baseline project

Output:

* IBS test project/repository
NOTE: should be easily accessible from the engcloud in Provo

Process (pipeline):

1.a. extend list of gerrit changes to cover Depends-On relationships
1.b. create staging IBS project
2. for every target package, in parallel:
2.a. add package to staging IBS project
2.b. update source to include change
3. wait for build to finish

Implementation:

* gerrit/build_test_package.py
TODO: split existing module stages, convert it into an ansible module

Notes:

* changes associated with packages without source services (e.g. python packages)
* cleanup -> keep a configurable number of projects, corresponding to the global number of stored job results
* fastfail -> stop immediately (i.e. if one package build fails, don't wait for others) and cleanup

### Gerrit test IBS project cleanup

Cleans up old IBS test projects left over from the previous module.

Input:

* (optional) IBS test project/repository
* (optional) number of projects to keep

Process (job):

* cleans up the supplied IBS project or all IBS projects exceeding the supplied number


### Create virtual environment (heat stack)

This job can be triggered manually to create an input model and a complete virtual environment based on 
a set of input parameters describing an input model

Input:

* scenario (existing)
* scenario parameters (new):
  * network template
  * service template
  * ...
* scenario parameters
  * controller count
  * sles computes
  * rhel computes
* (optional) input model repository/branch
* input model path (in repository or workspace) 
* input model name
* (stack name ?)
* cloud configuration name

Output:

* heat stack name
* updated ansible inventory
* generated/updated input model
* ansible hostname for the CLM

Process (pipeline):

1. (optional) clone input model repo
2. (optional) run input model generator
2. run heat generator / update input model
3.a.i. check/wait until resources are available
3.a.ii. create heat stack
3.b. update input model (with info from heat generator + extracted from the heat stack)
4. other operations needed to prepare the virtual environment and bring it and the test harness to the same state
as the hardware environment, such as:
4.a. generate ansible inventory

Notes:

* to avoid overloading the infrastructure with too many API calls, concurrency should be disabled for step 3.
* in the context of a limited resource pool, it might be required to put this job on hold until resources are freed
by some of the running jobs. This could be implemented by 
  * polling (step 3.a.i.), or
  * running another job, which implements 3.a. separately (i.e. schedules virtual resources) and has concurrency 
  disabled, or
  * using the lockable resources plugin, e.g.:
    * define a number of resources having the same label equal to the number of available "slots" in a resource pool
    * use the `lock` pipeline step, with a label and `quantity: 1`
    NOTE: the `lock` step needs to include all the tasks that use the resource, which extend beyond this job


### Virtual environment (heat stack) cleanup

### Generate input model

### Build CLM for hardware environment

Input:

* (optional) input model repository/branch
* target H/W setup label

Process

Implementation:
* rebuild VM
* (optional) clone input model

* QA repo: rebuild-deployer-vm.yml

### Bootstrap/Update CLM

Prepare a node to be used as CLM by setting up the necessary media and software channels. This step only includes steps
that are common to all cloud setup scenarios using the same media/repositories. It doesn't include installing packages
or setting up an input model, which would mean specializing the CLM to be used only with a particular scenario. 

This job shouldn't touch any of the other nodes in the cloud, in order to enable it being run separately, to create
a CLM baseline that can be reused in many a cloud setup.

This same step can be called repeatedly, e.g. to update the CLM media/repositories required in testing update scenarios.

Input:

* target CLM hostname
* media+repositories

Process (pipeline)
1. setup SSH keys, write motd, grow root partition on virtual setups
2. rsync media, nfs-mount and install remote repositories
3. setup needed RHEL repositories
4. (H/W cobbler only) copy medias to their location

Implementation:
* QA repo: boostrap-deployer-vm.yml
* automation repo: repositories.yml, init.yml

NOTEs:
* the RHEL bits should be set up even if the input model doesn't specify a RHEL compute node, to enable adding a
RHEL compute node at a later time
* a CLM node bootstrapped in this manner can be snapshotted and then cloned for other cloud testing scenarios using
the same media/repositories
* nodes in a virtual environment should be bootstrapped too, by installing OS updates after the repos have been set up.
This step becomes obvious when automating testing the maintenance update workflow, which also install updates
that are missing from the base image instead of only installing those targeted by the test. There are several ways of doing this:
  * update each node before deploying the cloud (time consuming, duplicated effort), or
  * use a single seed node (e.g. the node that will become the deployer), then create a snapshot and use that for all
  other nodes (still time consuming), or
  * keep a list of prebuilt images, corresponding to latest baselines and select the one needed, or
  * define a separate job that creates these snapshots for a well known list of baselines. All other CI jobs will depend
  on this job. For example, such a job could periodically be run to update the JEOS SLES12 SP3 image used by all SLES
  virtual nodes to install the maintenance updates that have been published since the last run. A similar job could
  be set to do the same thing for the latest maintenance updates pending testing.
The same is valid with regards to the RHEL base image and also to the ISOs used by cobbler.
  
### Initialize cloud

Prepare the cloud nodes for the initial cloud deployment

Input:

* target CLM hostname
* input model path

Process (pipeline)
1. setup SSH keys, grow root partition on virtual setups on non-deployer nodes
2. install Ardana (install pattern, run ardana-init)
3. 
4. (H/W cobbler only) copy medias to their location


Implementation:
* QA repo: boostrap-deployer-vm.yml
* automation repo: repositories.yml, init.yml


## Automation pipelines

## Requirements

1. the job that is integrated with Gerrit (i.e. triggered by gerrit changes and reporting results back to gerrit) also 
has to be parameterized in a way that allows it to be manually (re)triggered for the same gerrit change with different
parameters
2. ability to trigger custom jobs from gerrit, based on parameters extracted from the comment (e.g. a `check std-split`
gerrit comment should trigger a job that uses the `std-split` input model instead of the default `std-min` input model).
The job may or may not be able to vote on the gerrit review
3. pushing a new patchset must abort existing jobs running for the old patchset(s). This needs to be done for all jobs
triggered by the main job, but allow the tasks to run that perform proper cleanup of resources (e.g. delete the heat 
stacks). This can be done by multi-jobs and running the cleanup jobs as a post-build trigger configured for a "build aborted"
text in the log
4. if one of the voting jobs from the set of jobs running on the same gerrit change fails (or is aborted?), then all the
other jobs must be aborted as well (NOTE: but allow the cleanup post-build triggers to run). This can be accomplished via
the Gerrit Trigger option:'Other jobs on which this job depends', which links two or more gerrit-triggered jobs together
and reports their results together, or just use a pipeline.
5. a "core" job used in common by all triggers (gerrit, manual/QA/MU workflow, IBS gating, submitrequest, other staging projects)
6. the "core" job consists of stages, some of which can also be manually (re)triggered with different parameters
7. log artifacts collected by top-level jobs and presented back to the triggering processes (submitrequest/gerrit/manual/etc.)
8. rebuild from stage should work for pipeline jobs (NOTE: this requires the workspace to be the same)

## Proposal

* parameterized ansible top-level playbooks/roles or scripts for various modules, e.g.:
  * gerrit change package builder
  * input model generator
  * heat generator
  * virtual setup builder
  * CLM bootstrapper
  * cloud deployer
  * test runner(s)
  * heat resource pool manager (currently an embedded bash script in one of the jobs)
* operation jobs: parameterized jobs associated with modules or sets of modules that can be (re)triggered manually, e.g.:
  * virtual setup configuration builder (input model generator and/or heat generator)
  * virtual setup manager (create/cleanup/resource pool management)
  * gerrit change package builder
  * CLM bootstrapper
  * test runner
  * 
* workflow jobs: multi-purpose, parameterized pipeline jobs that implement a workflow consisting of chaining together 
several operation jobs. They either call operation jobs (preferable), or their scripts directly, e.g.:
  * openstack-ardana (generate, deploy and test a setup)
 
* trigger jobs templates: top-level, parameterized job templates which are connected to the SCM system (gerrit/IBS gating/sumbitrequest)
or are triggered periodically (IBS other) and are wrapped around one of the workflow or operation jobs, e.g.:
  * gerrit CI job
  * gerrit commit title checker
  * IBS gating job
  * trackupstream job ?
These jobs are also able to use tokens parsed from the gerrit comments (or submitrequests ?) as parameter values


* top-level job: incarnations of the trigger job templates, for various purposes, e.g.:
  * voting gerrit CI job with std-min input model for cloud9 and SLES only computes
  * IBS gating job with std-min input model for cloud9 and RHEL computes


## Limitations


### Gerrit CI

Stages:

1.a run: gerrit test package builder
(lock on virtual build resource)
1.b run: create virtual environment

### Ardana submitrequest CI

## IBS validation pipeline

Sources generating changes:

* SLES updates
* HA updates
* trackupstream
  * crowbar
  * ardana
  * common
* OBS
  * openstack packages
  * other...
  
Strategy:

* identify and maintain a sane baseline for each individual change generating source, in the form of a temporary IBS 
project and/or a package repository that can be used as input in CI/CD jobs
NOTE: these should be easily accessible from the engcloud Provo
* changes coming in from one of these sources are collected in batches, and every batch is tested incrementally along 
a pipeline, through one or several "merge points"
* allow manual override/continuation 
* achievable through the staging projects IBS feature
* incoming individual changes (gerrit, IBS D:C:8 submit request) are tested against the set of sane baselines plus the staging
version (baseline+pending changes) of the package group to which the change belongs

Example:



### Ardana Gerrit CI IBS validation pipeline  

* gerrit patchset is published
* one or more test job(s) are started (in parallel)
  * packages are built in a test project branched from the Ardana staging project
  * Depends-On changes are included
  * the repositories configured for the test setups are: the Ardana staging project+the test project+all other sane baselines
* if the builds pass
  * wait for the Depends-On changes to be merged (they must be merged in order, otherwise the staging build will be invalidated)
  NOTE: should the tests be rerun when done waiting to cover latest changes ? (all Depends-On changes cannot be merged at the
  same time because their individual states might prevent that - i.e. if some are not workflowed)
  * change is merged (check for conflicts)
  * the trackupstream build is triggered (on-demand, or periodically) to pick up the change and update the staging package

The changes merged in the staging project might not be guaranteed to work together. There are corner cases:
* two independent changes A and B from the same repository both pass gerrit CI while tested against the staging
project, but they are incompatible with each-other (without explicit merge conflicts) and will not pass the
same test if tested together. This will block subsequent test runs for the gerrit or IBS submitrequest CI
* it takes time for new changes to propagate from the point where they are merged into the Git repository to the point 
where they are published in the IBS repository/media where they can be consumed the test environments. This means that
there is no guarantee that the set of gerrit patches under test are actually tested against the latest version of the
sources available in all other Git repositories. Some changesets may still be in one of the intermediary states:
  * trackupstream hasn't run yet (package hasn't yet been updated with the latest source)
  * package with latest source hasn't built yet, so the latest version is not yet available in the repository
The missing changesets can create the following type of situations:
  * change under test Depends-On a merged change, which is missing
  * change under test has a hidden dependency on the latest version of another repository, which is missing
Solution:
  * always rebuild the latest version of packages corresponding to all repositories in the test project
* it takes time between validating a new change and merging it, which means that other changes can slip through
NOTE: this is a know issue that is mediated by running subsequent integration and validation steps

NOTEs: 
* the only guarantee that we can make is that merging a single change will not invalidate the staging build, if the
staging build is still in the state it was in when the change was tested
* testing new changes against the sane baseline instead of the staging project, would help identify hidden dependencies
between changes (even those that have been merged yet) and force the developer to mark these as explicit dependencies
in the gerrit patch. This is also something that, when translated into explicit IBS package dependencies, can be used 
during maintenance updates selection, because this kind of hidden dependency takes a lot of time to debug.

