#!/usr/bin/env zsh

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.zshrc

pyenv activate 3.11.9/envs/deploy

cd /Users/hongju/Documents/aws-manager/tasks/cronjobs

python console_access_manager.py
 
echo "$(date) : 접근 권한 부여 및 회수 crontab 정상 작동 " 