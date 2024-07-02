#!/usr/bin/env zsh

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.zshrc

pyenv activate 3.11.9/envs/deploy

cd /Users/hongju/Documents/aws-manager/tasks/cronjobs
 
python cloudtrail_log_pipeline.py
python quota_updater.py
python instance_police.py

echo "$(date) : 매일 5분마다 돌아가는 crontab 정상 작동" 