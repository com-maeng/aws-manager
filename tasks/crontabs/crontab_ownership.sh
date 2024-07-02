#!/usr/bin/env zsh

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.zshrc

pyenv activate 3.11.9/envs/deploy

cd /Users/hongju/Documents/aws-manager/tasks/cronjobs

python instance_owner_info_pipeline.py
 
echo "$(date) : onwership_info crontab 정상 작동" 
                                                                        