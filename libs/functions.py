
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path
import shutil
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
import random
import string

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
        v1 = client.CoreV1Api()        
        pods = v1.list_namespaced_pod(namespace)        
        pod_list = [pod.metadata.name for pod in pods.items if pod.status.phase == "Running"]
        return pod_list

    except ApiException as e:
        print(f"Exception when calling CoreV1Api->list_namespaced_pod: {e}")
        return []

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

def get_containers(namespace, pod_name):    
    kubeconfig_path = os.getenv('KUBECONFIG')
    if not kubeconfig_path:
        raise EnvironmentError("KUBECONFIG environment variable is not set")
    try:
        config.load_kube_config(config_file=kubeconfig_path)
    except ConfigException as e:
        print(f"Failed to load kubeconfig: {e}")
        return []

    try:
        v1 = client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        container_names = [container.name for container in pod.spec.containers]
        return container_names

    except ApiException as e:
        print(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")
        return []

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

def get_node_ip(namespace, pod_name):
    # Retrieve the kubeconfig path from the environment variable
    kubeconfig_path = os.getenv('KUBECONFIG')
    if not kubeconfig_path:
        raise EnvironmentError("KUBECONFIG environment variable is not set")

    try:
        # Load the kubeconfig file
        config.load_kube_config(config_file=kubeconfig_path)
    except ConfigException as e:
        print(f"Failed to load kubeconfig: {e}")
        return None

    try:
        # Create an instance of the API class
        v1 = client.CoreV1Api()

        # Get the specified pod in the specified namespace
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        # Get the name of the node where the pod is running
        node_name = pod.spec.node_name

        # Get the details of the node
        node = v1.read_node(name=node_name)

        # Extract the node IP from the node details
        for address in node.status.addresses:
            if address.type == "InternalIP":
                return address.address

        return None

    except ApiException as e:
        print(f"Exception when calling CoreV1Api->read_namespaced_pod or read_node: {e}")
        return None

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def get_node_ips():

    kubeconfig_path = os.getenv('KUBECONFIG')
    if not kubeconfig_path:
        raise EnvironmentError("KUBECONFIG environment variable is not set")
    try:
        config.load_kube_config(config_file=kubeconfig_path)
    except ConfigException as e:
        print(f"Failed to load kubeconfig: {e}")
        return {}

    try:        
        v1 = client.CoreV1Api()
        nodes = v1.list_node()
        node_info = {}
        for node in nodes.items:
            node_name = node.metadata.name
            node_ip = None
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    node_ip = address.address
                    break
            if node_ip:
                node_info[node_name] = node_ip

        return node_info

    except ApiException as e:
        print(f"Exception when calling CoreV1Api->list_node: {e}")
        return {}

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {}


def get_node_name(namespace, pod_name):    
    kubeconfig_path = os.getenv('KUBECONFIG')
    if not kubeconfig_path:
        raise EnvironmentError("KUBECONFIG environment variable is not set")

    try:        
        config.load_kube_config(config_file=kubeconfig_path)
    except ConfigException as e:
        print(f"Failed to load kubeconfig: {e}")
        return None

    try:        
        v1 = client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)        
        node_name = pod.spec.node_name
        return node_name

    except ApiException as e:
        print(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")
        return None

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

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
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    command=f"ssh -o StrictHostKeyChecking=no debian@{worker_node_ip} 'sudo nohup nice timeout { timeout } nsenter --target {container_pid} --net -- {tcpdump_command}' -w /tmp/{timestamp}-{random_string}-{magic_str}-{pod_name}-{container}.pcap >/dev/null 2>&1&"            
    print(f"Executing {command}...")
    subprocess.run(command, shell=True, capture_output=True, text=True)            