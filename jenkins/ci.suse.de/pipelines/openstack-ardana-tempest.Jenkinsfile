/**
 * The openstack-ardana-tempest Jenkins Pipeline
 *
 * This job runs tempest on a pre-deployed CLM cloud.
 */
pipeline {

  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
  }

  agent {
    node {
      label reuse_node ? reuse_node : "cloud-ardana-ci"
      customWorkspace clm_env ? "${JOB_NAME}-${clm_env}" : "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('setup workspace and environment') {
      steps {
        cleanWs()

        // If the job is set up to reuse an existing workspace, replace the
        // current workspace with a symlink to the reused one.
        // NOTE: even if we specify the reused workspace as the
        // customWorkspace variable value, Jenkins will refuse to reuse a
        // workspace that's already in use by one of the currently running
        // jobs and will just create a new one.
        sh '''
          if [ -n "${reuse_workspace}" ]; then
            rmdir "${WORKSPACE}"
            ln -s "${reuse_workspace}" "${WORKSPACE}"
          fi
        '''

        script {
          env.cloud_type = "virtual"
          if ( clm_env != '') {
            currentBuild.displayName = "#${BUILD_NUMBER} ${clm_env}"
            //currentBuild.description = ""
            if ( clm_env.startsWith("qe") || clm_env.startsWith("qa") ) {
              env.cloud_type = "physical"
            }
          }
          else {
            error("Empty 'clm_env' parameter value.")
          }
        }
      }
    }

    stage('clone automation repo') {
      when {
        expression { reuse_workspace == '' }
      }
      steps {
        dir("automation-git") {
          checkout scm
        }
      }
    }

    stage('setup ansible vars') {
      when {
        expression { cloud_type == 'virtual' && reuse_workspace == '' }
      }
      steps {
        script {
          // When running as a standalone job, we need a heat stack name to identify
          // the virtual environment and set up the ansible inventory.
          env.heat_stack_name="openstack-ardana-vcloud-$clm_env"
        }
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          sh './bin/setup_virt_vars.sh'
        }
      }
    }

    stage('run tempest') {
      steps {
        dir('automation-git/scripts/jenkins/ardana/ansible') {
          script {
            sh '''
              source /opt/ansible/bin/activate
              ansible-playbook -e qe_env=$clm_env \
                               -e rc_notify=$rc_notify \
                               -e tempest_run_filter=$tempest_run_filter \
                               run-ardana-tempest.yml
            '''
          }
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: '.artifacts/**', fingerprint: true
    }
  }
}