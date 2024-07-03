#!/usr/bin/env zsh

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.zshrc

pyenv activate 3.11.9/envs/deploy

cd /Users/hongju/Documents/aws-manager/tasks/cronjobs

args=("$@")

for (( i=0; i<$#; i++)); do
  python ${args[$i-1]}
done

