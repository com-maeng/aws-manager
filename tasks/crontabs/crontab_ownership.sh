#!/bin/bash

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.bashrc

pyenv activate 3.11.9/envs/deploy

cd /home/hongju/aws-manager/tasks/cronjobs

python instance_owner_info_pipeline.py
 
echo "onwership_info shell 정상 작동 $(date)" >> cronjob_log.txt 
~                                                                            