/**
 * The openstack-ardana-gerrit Jenkins Pipeline
 */

pipeline {
  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
  }

  agent {
    node {
      label 'cloud-trigger'
    }
  }

  stages {

    stage('validate commit message') {
      steps {
        cleanWs()
        script {
          currentBuild.displayName = "#${BUILD_NUMBER}: ${gerrit_change_ids}"
        }
        git branch: "${GERRIT_BRANCH}", url: 'git://git.suse.provo.cloud/${GERRIT_PROJECT}'
        //checkout changelog: true, poll: false, scm: [
        //  $class: 'GitSCM',
        //  branches: [[name: "${GERRIT_BRANCH}"]],
        //  doGenerateSubmoduleConfigurations: false,
        //  extensions: [],
        //  submoduleCfg: [],
        //  userRemoteConfigs: [[refspec: "${GERRIT_REFSPEC}",
        //                       url: "git://git.suse.provo.cloud/${GERRIT_PROJECT}"]]
        //]

        //branches: [[name: "$\{env.BRANCH_NAME}"]], doGenerateSubmoduleConfigurations: false, extensions:
        //[[$class: 'CloneOption', depth: 0, noTags: true, reference: '', shallow: +*true*+]],
        //submoduleCfg: [], userRemoteConfigs: [url: '[http://My]]
        echo 'TBD: trigger commit message validator job...'
      }
    }
  }
}
