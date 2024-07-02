#!/usr/bin/env zsh

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.zshrc

pyenv activate 3.11.9/envs/deploy

cd /home/hongju/aws-manager/tasks/cronjobs
 
python instance_stopper.py

echo "인스턴스 6시에 종료  shell 정상 작동 $(date)" >> cronjob_log.txt 