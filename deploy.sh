export GOOGLE_CLOUD_PROJECT="qwiklabs-gcp-01-03d4dd387ba7"
export GOOGLE_CLOUD_LOCATION="us-central1" # Example location
export AGENT_PATH="./image_agent" 
export SERVICE_NAME="home-recommendation-agent-service"

/home/student_00_8400921b9866/agent_test/.venv/bin/python ./.venv/bin/adk deploy cloud_run \
--project=$GOOGLE_CLOUD_PROJECT \
--region=$GOOGLE_CLOUD_LOCATION \
--service_name=$SERVICE_NAME \
--with_ui \
$AGENT_PATH