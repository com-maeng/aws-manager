#!/bin/bash

# Update codebase
git pull origin

# Remove old gunicorn processes
pids=$(ps aux | grep gunicorn | grep -v grep | awk '{print $2}')

for pid in $pids
do
    sudo kill -9 $pid
    echo "Killed PID: $pid"
done

# Set deployment environments
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

pyenv activate deploy
pip install -r requirements.txt

# Deploy the service
nohup gunicorn --workers 2 --bind 127.0.0.1:4202 app:app >> deploy.log 2>&1 &
