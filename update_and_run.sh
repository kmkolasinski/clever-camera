#!/usr/bin/env bash

SCRIPT_PATH="`dirname \"$0\"`"
cd $SCRIPT_PATH

source venv/bin/activate
git pull origin master
pip install -r requirements.txt
bash run.sh

