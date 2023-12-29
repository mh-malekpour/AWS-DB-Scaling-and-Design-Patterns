import boto3
import json
import time


# Initialize the SSM client
ssm_client = boto3.client('ssm')

# Specify the instance IDs
with open('instance_details.json', 'r') as file:
    instance_details = json.load(file)

instance_ids = []
for instance in instance_details:
    if "worker" in instance['Name']:
        instance_ids.append(instance['InstanceID'])

# Function to read a script file
def read_script(file_path):
    with open(file_path, 'r') as f:
        return f.read()

commands = [
    # phase 1
    "sudo mkdir -p /opt/mysqlcluster/home",
    "cd /opt/mysqlcluster/home && sudo wget http://dev.mysql.com/get/Downloads/MySQL-Cluster-7.2/mysql-cluster-gpl-7.2.1-linux2.6-x86_64.tar.gz",
    "cd /opt/mysqlcluster/home && sudo tar xvf mysql-cluster-gpl-7.2.1-linux2.6-x86_64.tar.gz",
    "cd /opt/mysqlcluster/home && sudo ln -s mysql-cluster-gpl-7.2.1-linux2.6-x86_64 mysqlc",
    "echo 'export MYSQLC_HOME=/opt/mysqlcluster/home/mysqlc' | sudo tee /etc/profile.d/mysqlc.sh && echo 'export PATH=$MYSQLC_HOME/bin:$PATH' | sudo tee -a /etc/profile.d/mysqlc.sh && source /etc/profile.d/mysqlc.sh",
    "sudo apt-get update && sudo apt-get -y install libncurses5",
    # phase 2
    "sudo mkdir -p /opt/mysqlcluster/deploy/ndb_data && sudo chmod -R 777 /opt && ndbd -c ip-10-0-1-225.ec2.internal:1186"
]

def send_command(instance_ids, command):
    response = ssm_client.send_command(
        InstanceIds=instance_ids,
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': [command]},
    )
    return response['Command']['CommandId']

def check_command_status(command_id, instance_id):
    for _ in range(10):  # Try up to 10 times with a delay in between
        try:
            response = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            if response['Status'] != 'InProgress':
                return response
        except ssm_client.exceptions.InvocationDoesNotExist:
            print(f"Waiting for command {command_id} to be registered in SSM...")
        time.sleep(10)  # Wait for 10 seconds before checking again

    return {"Status": "Failed", "StatusDetails": "Invocation does not exist or check exceeded retries"}


# Flag to track if any command fails
any_command_failed = False

# Execute each command and check its status
for command in commands:
    if any_command_failed:
        break  # Stop executing further commands if one has already failed

    command_id = send_command(instance_ids, command)
    if 'docker-compose up' in command:
        print("running docker-compose up on instances")
        break

    for instance_id in instance_ids:
        status = check_command_status(command_id, instance_id)
        print(f"Status for instance {instance_id} on command '{command}': {status['Status']}, {status['StatusDetails']}")
        if status['Status'] != 'Success':
            print(f"Command execution failed on instance {instance_id} for command '{command}'")
            any_command_failed = True
            break  # Stop executing further commands on this instance