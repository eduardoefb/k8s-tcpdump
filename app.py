from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import subprocess
import os
import json
from libs.functions import *
from pathlib import Path
import webbrowser

# Set the custom KUBECONFIG path
KUBECONFIG_PATH = '/home/eduardoefb/scripts/ansible/k8s-proxmox/files/kubeconfig'
os.environ['KUBECONFIG'] = KUBECONFIG_PATH

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace 'your_secret_key' with a strong key

node_ip_mapping = {}

@app.route('/')
def index():
    namespaces = get_namespaces()
    return render_template('index.html', namespaces=namespaces)

@app.route('/get_pods', methods=['POST'])
def get_pods_route():
    namespace = request.form.get('namespace')
    session['selected_namespace'] = namespace  # Store the selected namespace in the session
    pods = get_pods(namespace)
    return jsonify(pods)

@app.route('/select_pods', methods=['POST'])
def select_pods():
    selected_pods = request.form.getlist('pods')
    namespace = session.get('selected_namespace')
    pod_node_mapping = {}
    pod_container_mapping = {}

    for item in selected_pods:
        pod_name, node_name = item.split(':')
        pod_node_mapping[pod_name] = node_name
        containers = get_containers(namespace, pod_name)
        pod_container_mapping[pod_name] = containers

    node_ip_mapping = get_node_ips()
    print(f'Node IP Mapping: {node_ip_mapping}')
    print(f'Selected pods: {pod_node_mapping}')
    print(f'Pod-Container mapping: {pod_container_mapping}')

    clear_tcpdump(node_ip_mapping)

    for pod in selected_pods:
        pod_name = pod.split(":")[0]
        worker_node_ip = node_ip_mapping[str(pod.split(":")[1])]
        for container in pod_container_mapping[str(pod_name)]:
            container_tcpdump(worker_node_ip, container, pod_name, user="debian")
            
    return '', 204

@app.route('/stop_tcpdump', methods=['POST'])
def stop_tcpdump_route():
    stop_tcpdump()    
    return '', 204

@app.route('/pcap_files/<path:filename>')
def download_file(filename):
    return send_from_directory('pcap_files', filename)

@app.route('/pcap_files')
def list_files():
    files = os.listdir('pcap_files')
    return render_template('list_files.html', files=files)

@app.route('/reuse_namespace', methods=['GET'])
def reuse_namespace():
    selected_namespace = session.get('selected_namespace')
    if selected_namespace:
        # Do something with the selected namespace
        print(f'Reusing selected namespace: {selected_namespace}')
        # Add your logic here
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
