/**
 * The openstack-ardana-virtual Jenkins Pipeline
 *
 * This jobs creates an ECP virtual environment that can be used to deploy
 * an Ardana input model which is either predefined or generated based on
 * the input parameters.
 */
pipeline {

  options {
    // skip the default checkout, because we want to use a custom path
    skipDefaultCheckout()
    timestamps()
  }

  agent {
    node {
      label reuse_node ? reuse_node : "cloud-ardana-ci"
      customWorkspace "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {
    stage('Setup workspace') {
      steps {
        script {
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
          if (reuse_node == '') {
            sh('''
              rm -rf $SHARED_WORKSPACE
              mkdir -p $SHARED_WORKSPACE

              # archiveArtifacts and junit don't support absolute paths, so we have to to this instead
              ln -s ${SHARED_WORKSPACE}/.artifacts ${WORKSPACE}

              cd $SHARED_WORKSPACE
              git clone $git_automation_repo --branch $git_automation_branch automation-git
              source automation-git/scripts/jenkins/ardana/jenkins-helper.sh
              ansible_playbook load-job-params.yml
            ''')
          }
        }
      }
    }

    stage('Prepare input model') {
      parallel {
        stage('Generate input model') {
          when {
            expression { scenario_name != '' }
          }
          steps {
            sh 'sleep 1'
          }
        }
        stage('Clone input model') {
          when {
            expression { scenario_name == '' }
          }
          steps {
            echo env.RUN_DISPLAY_URL
            script {
              env.build_url = env.RUN_DISPLAY_URL
              //env.RUN_DISPLAY_URL = env.RUN_DISPLAY_URL
            }
            sh 'sleep 1'
          }
        }
      }
    }

    stage('Generate heat template') {
      steps {
        sh 'sleep 1'
      }
    }

    stage('Create heat stack') {
      steps {
        sh 'sleep 1'
      }
    }

    stage('Setup SSH access') {
      steps {
        sh 'sleep 1'
      }
    }
  }
}
