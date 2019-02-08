/**
 * The openstack-ardana Jenkins pipeline library
 */

def ansible_playbook(playbook, params='') {
  sh("""
    cd $WORKSPACE
    source automation-git/scripts/jenkins/ardana/jenkins-helper.sh
    ansible_playbook """+playbook+""".yml -e @input.yml """+params
  )
}

def trigger_build(job_name, parameters, propagate=true, wait=true) {
  def slaveJob = build job: job_name, parameters: parameters, propagate: propagate, wait: wait
  if (wait && !propagate) {
    def jobResult = slaveJob.getResult()
    def jobUrl = slaveJob.buildVariables.blue_ocean_buildurl
    def jobMsg = "Build ${jobUrl} completed with: ${jobResult}"
    echo jobMsg
    if (jobResult != 'SUCCESS') {
      error(jobMsg)
    }
  }
  return slaveJob
}

def get_deployer_ip() {
  env.DEPLOYER_IP = sh (
    returnStdout: true,
    script: '''
      grep -oP "^${ardana_env}\\s+ansible_host=\\K[0-9\\.]+" \\
        $WORKSPACE/automation-git/scripts/jenkins/ardana/ansible/inventory
    '''
  ).trim()
  currentBuild.displayName = "#${BUILD_NUMBER}: ${ardana_env} (${DEPLOYER_IP})"
  echo """
******************************************************************************
** The deployer for the '${ardana_env}' environment is reachable at:
**
**        ssh root@${DEPLOYER_IP}
**
******************************************************************************
  """
}

def generate_tempest_stages(tempest_filter_list) {
  if (tempest_filter_list != '') {
    for (filter in tempest_filter_list.split(',')) {
      catchError {
        stage("Tempest: "+filter) {
          ansible_playbook('run-tempest', "-e tempest_run_filter=$filter")
        }
      }
      archiveArtifacts artifacts: ".artifacts/**/ansible.log, .artifacts/**/*${filter}*", allowEmptyArchive: true
      junit testResults: ".artifacts/testr_results_region1_${filter}.xml", allowEmptyResults: true
    }
  }
}

def generate_qa_tests_stages(qa_test_list) {
  if (qa_test_list != '') {
    for (test in qa_test_list.split(',')) {
      catchError {
        stage("QA test: "+test) {
          ansible_playbook('run-ardana-qe-tests', "-e test_name=$test")
        }
      }
      archiveArtifacts artifacts: ".artifacts/**/${test}*", allowEmptyArchive: true
      junit testResults: ".artifacts/${test}.xml", allowEmptyResults: true
    }
  }
}


// Implements a simple closure that executes the supplied function (body) with
// or without reserving a Lockable Resource identified by the 'resource_label'
// label value, depending on the 'reserve' boolean value.
//
// The reserved resource will be made available to the supplied function body
// via the 'reserved_env' variable. For convenience, the function also accepts a
// 'default_resource' parameter that will be used as a default value for 'reserved_env'
// if a resource does not actually need to be reserved. This enables the supplied
// function body to use the 'reserved_env' variable without needing to check if a
// resource has been reserved.
//
// The function also implements a sleep-retry mechanism as a workaround for JENKINS-52638.
//
def run_with_reserved_env(reserve, resource_label, default_resource, body) {

  if (reserve) {
    lock(resource: null, label: resource_label, variable: 'reserved_env', quantity: 1) {
      if (env.reserved_env && reserved_env != null) {
        echo "Reserved resource: " + reserved_env
        body()
      } else  {
        error("Jenkins bug (JENKINS-52638): couldn't reserve a resource with label " + resource_label)
      }
    }
  } else {
    env.reserved_env = default_resource != null ? default_resource: resource_label
    echo "Using resource without a reservation: " + reserved_env
    body()
  }
}

return this
