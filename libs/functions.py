
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path
import shutil
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

def stop_tcpdump():
    magic_str = get_magic_str()
    local_pcap_dir = Path("pcap_files")
    if local_pcap_dir.exists() and local_pcap_dir.is_dir():
        shutil.rmtree(local_pcap_dir)    
    local_pcap_dir.mkdir(exist_ok=True)

    node_ip_mapping = get_node_ips()

    # Stop tcpdump
    for node_ip in node_ip_mapping.values():
        command = f"ssh -o StrictHostKeyChecking=no debian@{node_ip} 'sudo pkill -f {magic_str}'"
        subprocess.run(command, shell=True, capture_output=True, text=True)

    # Download pcap files
    for node_ip in node_ip_mapping.values():
        command = f"ssh -o StrictHostKeyChecking=no debian@{node_ip} 'ls /tmp/*{magic_str}*.pcap'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        files = result.stdout.split()
        for file in files:
            if file.endswith('.pcap'):
                scp_command = f"scp -o StrictHostKeyChecking=no debian@{node_ip}:{file} {local_pcap_dir}/"
                print(f"Executing {command}...")
                subprocess.run(scp_command, shell=True, capture_output=True, text=True)                
                rm_command = f"ssh -o StrictHostKeyChecking=no debian@{node_ip} 'sudo rm {file}'"
                print(f"Executing {command}...")
                subprocess.run(rm_command, shell=True, capture_output=True, text=True)
    
    now = datetime.now()
    timestamp = now.strftime('%y%m%d%H%M%S')

    command = f"mergecap pcap_files/*{magic_str}*.pcap -w pcap_files/{timestamp}-{magic_str}-all.pcap"
    print(f"Executing {command}...")
    subprocess.run(command, shell=True, capture_output=True, text=True)
    print("Tcpdump stopped and pcap files downloaded.")


def get_namespaces():
    # Retrieve the kubeconfig path from the environment variable
    kubeconfig_path = os.getenv('KUBECONFIG')
    if not kubeconfig_path:
        raise EnvironmentError("KUBECONFIG environment variable is not set")

    try:
        # Load the kubeconfig file
        config.load_kube_config(config_file=kubeconfig_path)
    except ConfigException as e:
        print(f"Failed to load kubeconfig: {e}")
        return []

    try:
        # Create an instance of the API class
        v1 = client.CoreV1Api()

        # List all namespaces
        namespaces = v1.list_namespace()

        # Extract the names of the namespaces and return as a list
        namespace_list = [ns.metadata.name for ns in namespaces.items]
        
        return namespace_list

    except ApiException as e:
        print(f"Exception when calling CoreV1Api->list_namespace: {e}")
        return []

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []


def get_pods(namespace):
    result = subprocess.run(['kubectl', 'get', 'pods', '-n', namespace, '-o', 'json'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        pods_json = result.stdout
        pods = []
        for item in json.loads(pods_json)['items']:
            pod_name = item['metadata']['name']
            node_name = item['spec']['nodeName']
            pods.append({pod_name: node_name})
        return pods
    else:
        return []        

def get_containers(namespace, pod_name):
    result = subprocess.run(['kubectl', 'get', 'pod', pod_name, '-n', namespace, '-o', 'json'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        pod_json = json.loads(result.stdout)
        containers = [container['name'] for container in pod_json['spec']['containers']]
        return containers
    else:
        return []        

def get_node_ips():
    result = subprocess.run(['kubectl', 'get', 'nodes', '-o', 'json'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        nodes_json = json.loads(result.stdout)
        node_ips = {}
        for item in nodes_json['items']:
            node_name = item['metadata']['name']
            for address in item['status']['addresses']:
                if address['type'] == 'InternalIP':
                    node_ips[node_name] = address['address']
                    break
        return node_ips
    else:
        return {}    

def get_magic_str():
    return "7eca88064c63dcc9"

def clear_tcpdump(node_ip_mapping):
    magic_str = get_magic_str()
    for i in node_ip_mapping:
        worker_node_ip = node_ip_mapping[i]
        command = f"ssh -o StrictHostKeyChecking=no debian@{worker_node_ip} 'sudo pkill -f {magic_str}' "
        subprocess.run(command, shell=True, capture_output=True, text=True) 
        command = f"ssh -o StrictHostKeyChecking=no debian@{worker_node_ip} 'sudo rm /tmp/*{magic_str}*.pcap' "
        subprocess.run(command, shell=True, capture_output=True, text=True) 
    return 0

def container_tcpdump(worker_node_ip, container, pod_name, user="debian"):
    now = datetime.now()
    timestamp = now.strftime('%y%m%d%H%M%S')
    magic_str = get_magic_str()
    timeout=300
    tcpdump_command = "tcpdump -ni any -s 0"

    command = f"ssh -o StrictHostKeyChecking=no debian@{worker_node_ip} 'sudo crictl ps' 2>/dev/null | awk '/ {container} .* {pod_name}/ {{print $1}}'"
    print(f"Executing {command}...")
    container_id = str(subprocess.run(command, shell=True, capture_output=True, text=True).stdout).strip()
    command = f"ssh -o StrictHostKeyChecking=no debian@{worker_node_ip} 'sudo crictl inspect {container_id}'"
    print(f"Executing {command}...")
    container_output = subprocess.run(command, shell=True, capture_output=True, text=True)
    container_pid = json.loads(container_output.stdout)["info"]["pid"]
    command=f"ssh -o StrictHostKeyChecking=no debian@{worker_node_ip} 'sudo nohup nice timeout { timeout } nsenter --target {container_pid} --net -- {tcpdump_command}' -w /tmp/{timestamp}-{magic_str}-{pod_name}-{container}.pcap >/dev/null 2>&1&"            
    print(f"Executing {command}...")
    subprocess.run(command, shell=True, capture_output=True, text=True)            