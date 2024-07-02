#!/usr/bin/env zsh

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.zshrc

pyenv activate 3.11.9/envs/deploy

cd /Users/hongju/Documents/aws-manager/tasks/cronjobs
 
python instance_stopper.py

echo "$(date) : 인스턴스 일괄 종료 crontab 정상 작동 "