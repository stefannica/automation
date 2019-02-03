/**
 * The openstack-ardana-update Jenkins Pipeline
 *
 * This job updates a pre-deployed CLM cloud.
 */

def ardana_lib = null

pipeline {

  options {
    // skip the default checkout, because we want to use a custom path
    skipDefaultCheckout()
    timestamps()
  }

  agent {
    node {
      label "cloud-ardana-ci"
      customWorkspace "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('Setup workspace') {
      steps {
        script {
          // Set this variable to be used by upstream builds
          env.blue_ocean_buildurl = env.RUN_DISPLAY_URL
          if (ardana_env == '') {
            error("Empty 'ardana_env' parameter value.")
          }
          currentBuild.displayName = "#${BUILD_NUMBER}: ${ardana_env}"
          // Use a shared workspace folder for all jobs running on the same
          // target 'ardana_env' cloud environment
          env.SHARED_WORKSPACE = sh (
            returnStdout: true,
            script: 'echo "$(dirname $WORKSPACE)/shared/${ardana_env}"'
          ).trim()
          sh('''
            rm -rf $SHARED_WORKSPACE
            mkdir -p $SHARED_WORKSPACE

            cd $SHARED_WORKSPACE
            git clone $git_automation_repo --branch $git_automation_branch automation-git
            source automation-git/scripts/jenkins/ardana/jenkins-helper.sh
            ansible_playbook load-job-params.yml
            ansible_playbook setup-ssh-access.yml -e @input.yml
          ''')
          // archiveArtifacts and junit don't support absolute paths, so we have to to this instead
          sh "ln -s ${SHARED_WORKSPACE}/.artifacts ${WORKSPACE}"

          ardana_lib = load "$SHARED_WORKSPACE/automation-git/jenkins/ci.suse.de/pipelines/openstack-ardana.groovy"
          ardana_lib.get_deployer_ip()
        }
      }
    }

    stage('Update ardana') {
      steps {
        script {
          ardana_lib.ansible_playbook('ardana-update', "-e cloudsource=$update_to_cloudsource")
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: ".artifacts/**/*", allowEmptyArchive: true
    }
    cleanup {
      cleanWs()
    }
  }
}
