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
    if instance['Name'] == 'stand-alone':
        instance_ids.append(instance['InstanceID'])

commands = [
    # Install docker
    'sudo apt-get update',
    'sudo apt-get install -y mysql-server',
    """sudo mysql_secure_installation <<EOF
    n
    y
    y
    y
    n
    EOF""",
    'wget https://downloads.mysql.com/docs/sakila-db.tar.gz',
    'tar -xzf sakila-db.tar.gz',
    'sudo mysql < sakila-db/sakila-schema.sql',
    'sudo mysql < sakila-db/sakila-data.sql',
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
    for instance_id in instance_ids:
        status = check_command_status(command_id, instance_id)
        print(f"Status for instance {instance_id} on command '{command}': {status['Status']}, {status['StatusDetails']}")
        if status['Status'] != 'Success':
            print(f"Command execution failed on instance {instance_id} for command '{command}'")
            any_command_failed = True
            break  # Stop executing further commands on this instance