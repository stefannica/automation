/**
 * The openstack-ardana-image-update Jenkins Pipeline
 * This job automates updating the base SLES image used by virtual cloud nodes.
 */

pipeline {
  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
    timestamps()
  }

  agent {
    node {
      label 'cloud-ardana-ci'
      customWorkspace "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {

    stage('Setup workspace') {
      steps {
        script {
          currentBuild.displayName = "#${BUILD_NUMBER}: ${sles_image}"
        }
      }
    }

    stage('upload new image version') {
      steps {
        sh '''
          env
        '''
      }
    }

    stage('integration test') {
      steps {
        script {
          def slaveJob = build job: openstack_ardana_job, parameters: [
              string(name: 'ardana_env', value: "cloud-ardana-gerrit-slot"),
              string(name: 'git_automation_repo', value: "$git_automation_repo"),
              string(name: 'git_automation_branch', value: "$git_automation_branch"),
              text(name: 'extra_params', value: "sles_image=${sles_image}-update")
          ], propagate: true, wait: true
        }
      }
    }
  }
  post {
    success {
      sh '''
          openstack --os-cloud $os_cloud image set \
              --name ${sles_image}-$(date +%Y%m%d) \
              --deactivate \
              ${sles_image}

          openstack --os-cloud $os_cloud image set \
              --name ${sles_image} \
              ${sles_image}-update
      '''
    }
    cleanup {
      cleanWs()
    }
  }
}
