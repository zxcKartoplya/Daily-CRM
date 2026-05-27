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
        lock(resource: 'daily-compose-deploy')
        timeout(time: 30, unit: 'MINUTES')
    }
 
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
 
        stage('Test') {
            steps {
                sh """
                    docker build --target tester \
                      -t ${IMAGE_NAME}:test-${BUILD_NUMBER} \
                      .
                    docker run --rm ${IMAGE_NAME}:test-${BUILD_NUMBER}
                """
            }
            post {
                always {
                    sh "docker rmi ${IMAGE_NAME}:test-${BUILD_NUMBER} || true"
                }
            }
        }
 
        stage('Build') {
            steps {
                sh """
                    docker build --target runtime \
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
            post {
                failure {
                    sh """
                        docker rmi ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} || true
                        docker rmi ${REGISTRY}/${IMAGE_NAME}:latest || true
                    """
                }
            }
        }
 
        stage('Deploy') {
            when { branch 'main' }
            steps {
                sh """
                    cd ${DEPLOY_DIR}
                    
                    sed -i 's|^BACKEND_IMAGE=.*|BACKEND_IMAGE=${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}|' .env
 
                    docker compose up -d --no-deps --force-recreate backend
 
                    docker compose ps backend
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
 
