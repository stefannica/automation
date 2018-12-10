/**
 * The openstack-ardana-gerrit Jenkins Pipeline
 */

def ardana_lib = null

pipeline {
  // skip the default checkout, because we want to use a custom path
  options {
    skipDefaultCheckout()
    timestamps()
  }

  agent {
    node {
      label 'cloud-pipeline'
      customWorkspace "${JOB_NAME}-${BUILD_NUMBER}"
    }
  }

  stages {

    stage('Setup workspace') {
      steps {
        script {
          if (gerrit_patchset == '') {
            if (env.GERRIT_CHANGE_NUMBER == null || env.GERRIT_PATCHSET_NUMBER == null) {
              error("Empty 'gerrit_patchset' parameter value.")
            }
            env.gerrit_patchset = "${GERRIT_CHANGE_NUMBER}/${GERRIT_PATCHSET_NUMBER}"
          }
          currentBuild.displayName = "#${BUILD_NUMBER}: ${gerrit_change_ids}"

          sh('''
            IFS='/' read -r -a repo_arr <<< "$git_automation_repo"
            export git_automation_repo="${repo_arr[3]}"
            curl https://raw.githubusercontent.com/$git_automation_repo/automation/$git_automation_branch/scripts/jenkins/ardana/openstack-ardana.prep.sh | bash
          ''')

          ardana_lib = load "$WORKSPACE/automation-git/jenkins/ci.suse.de/pipelines/openstack-ardana.groovy"
          ardana_lib.load_extra_params_as_vars(extra_params)

          sh('''
            gerrit_change_items=(${gerrit_patchset//\\// })
            gerrit_change_number=${gerrit_change_items[0]}
            gerrit_patchset_number=${gerrit_change_items[1]}

            # abort other older running builds that target the same change patchset and integration test job
            ./automation-git/scripts/jenkins/jenkins-job-cancel \
              --older-than ${BUILD_NUMBER} \
              --with-param gerrit_patchset=${gerrit_patchset} \
              --with-param integration_test_job=${integration_test_job} \
              ${JOB_NAME} || :

            ./automation-git/scripts/jenkins/jenkins-job-cancel \
              --older-than ${BUILD_NUMBER} \
              --with-param GERRIT_CHANGE_NUMBER=${gerrit_change_number} \
              --with-param GERRIT_PATCHSET_NUMBER=${gerrit_patchset_number} \
              --with-param integration_test_job=${integration_test_job} \
              ${JOB_NAME} || :

            message="
Started build (${JOB_NAME}): ${BUILD_URL}
The following links can also be used to track the results:

- live console output: ${BUILD_URL}console
- live pipeline job view: ${RUN_DISPLAY_URL}
"
            if $voting ; then
              automation-git/scripts/jenkins/ardana/gerrit/gerrit_review.py \
                --vote 0 \
                --label 'Verified' \
                --message "$message" \
                ${gerrit_patchset}
            else
              automation-git/scripts/jenkins/ardana/gerrit/gerrit_review.py \
                --message "$message" \
                ${gerrit_patchset}
            fi
          ''')
        }
      }
    }

    stage('validate commit message') {
      steps {
        sh '''
          export LC_ALL=C.UTF-8
          export LANG=C.UTF-8

          if [[ -n $GERRIT_CHANGE_COMMIT_MESSAGE ]]; then
            echo $GERRIT_CHANGE_COMMIT_MESSAGE | base64 --decode | gitlint -C automation-git/scripts/jenkins/gitlint.ini
          else
            automation-git/scripts/jenkins/ardana/gerrit/gerrit_get_commit_msg.py ${gerrit_patchset} | gitlint -C automation-git/scripts/jenkins/gitlint.ini
          fi
        '''
      }
    }

    stage('integration test') {
      when {
        expression { integration_test_job != '' }
      }
      steps {
        script {
          // reserve a resource here for the openstack-ardana job, to avoid
          // keeping a cloud-ardana-ci worker busy while waiting for a
          // resource to become available.
          ardana_lib.run_with_reserved_env(reserve_env == 'true', ardana_env, ardana_env) {
            reserved_env ->
            ardana_lib.trigger_build(integration_test_job, [
              string(name: 'ardana_env', value: reserved_env),
              string(name: 'reserve_env', value: "false"),
              string(name: 'gerrit_change_ids', value: "$gerrit_patchset"),
              string(name: 'git_automation_repo', value: "$git_automation_repo"),
              string(name: 'git_automation_branch', value: "$git_automation_branch"),
              text(name: 'extra_params', value: extra_params)
            ])
          }
        }
      }
    }
  }
  post {
    always {
      script{
        env.BUILD_RESULT = currentBuild.currentResult
        sh('''
          automation-git/scripts/jenkins/jenkins-job-pipeline-report.py \
            --recursive \
            --filter 'Declarative: Post Actions' \
            --filter 'Setup workspace' > pipeline-report.txt || :

          if [[ $BUILD_RESULT == SUCCESS ]]; then
            vote=+2
            message="
Build succeeded (${JOB_NAME}): ${BUILD_URL}

"
          elif [[ $BUILD_RESULT == ABORTED ]]; then
            vote=
            message="
Build aborted (${JOB_NAME}): ${BUILD_URL}

"
          else
            vote=-2
            message="
Build failed (${JOB_NAME}): ${BUILD_URL}

"
          fi
          if $voting && [[ -n $vote ]] ; then
            automation-git/scripts/jenkins/ardana/gerrit/gerrit_review.py \
              --vote $vote \
              --label 'Verified' \
              --message "$message" \
              --message-file pipeline-report.txt \
              ${gerrit_patchset}
            if [[ $BUILD_RESULT == SUCCESS ]]; then
              automation-git/scripts/jenkins/ardana/gerrit/gerrit_merge.py \
                ${gerrit_patchset}
            fi
          else
            automation-git/scripts/jenkins/ardana/gerrit/gerrit_review.py \
              --message "$message" \
              --message-file pipeline-report.txt \
              ${gerrit_patchset}
          fi
        ''')
      }
    }
    cleanup {
      cleanWs()
    }
  }
}
