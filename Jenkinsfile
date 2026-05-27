pipeline {
    agent any

    environment {
        IMAGE_NAME = 'daily-backend'
        REGISTRY   = 'localhost:5000'
        DEPLOY_DIR = '/opt/daily'
    }

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Build') {
            steps {
                sh """
                    docker build \
                      -t ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \
                      -t ${REGISTRY}/${IMAGE_NAME}:latest \
                      .
                """
            }
        }

        stage('Push') {
            steps {
                sh """
                    docker push ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}
                    docker push ${REGISTRY}/${IMAGE_NAME}:latest
                """
            }
        }

        stage('Deploy') {
            when { branch 'main' }
            steps {
                sh """
                    cd ${DEPLOY_DIR} && \
                    BACKEND_IMAGE=${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \
                    docker compose up -d --no-deps --force-recreate backend
                """
            }
        }
    }

    post {
        success { echo "✅ Backend #${BUILD_NUMBER} deployed" }
        failure { echo "❌ Build #${BUILD_NUMBER} failed" }
        always  { sh 'docker image prune -f --filter "until=72h" || true' }
    }
}
