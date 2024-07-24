#!/bin/bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
KUBECONFIG=/home/eduardoefb/scripts/ansible/k8s-proxmox/files/kubeconfig python app.py
