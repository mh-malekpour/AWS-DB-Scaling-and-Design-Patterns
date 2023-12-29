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
    if instance['Name'] == 'manager':
        instance_ids.append(instance['InstanceID'])

commands = [
    # phase 1
    "sudo mkdir -p /opt/mysqlcluster/home",
    "cd /opt/mysqlcluster/home && sudo wget http://dev.mysql.com/get/Downloads/MySQL-Cluster-7.2/mysql-cluster-gpl-7.2.1-linux2.6-x86_64.tar.gz",
    "cd /opt/mysqlcluster/home && sudo tar xvf mysql-cluster-gpl-7.2.1-linux2.6-x86_64.tar.gz",
    "cd /opt/mysqlcluster/home && sudo ln -s mysql-cluster-gpl-7.2.1-linux2.6-x86_64 mysqlc",
    "echo 'export MYSQLC_HOME=/opt/mysqlcluster/home/mysqlc' | sudo tee /etc/profile.d/mysqlc.sh && echo 'export PATH=$MYSQLC_HOME/bin:$PATH' | sudo tee -a /etc/profile.d/mysqlc.sh && source /etc/profile.d/mysqlc.sh",
    "sudo apt-get update && sudo apt-get -y install libncurses5",
    # phase2
    "sudo mkdir -p /opt/mysqlcluster/deploy",
    "sudo mkdir conf",
    "sudo mkdir mysqld_data",
    "sudo mkdir ndb_data",
    """
    cd conf && sudo cat <<EOF > my.cnf
    [mysqld]
    ndbcluster
    datadir=/opt/mysqlcluster/deploy/mysqld_data
    basedir=/opt/mysqlcluster/home/mysqlc
    port=3306
    EOF
    """,
    """
    cd conf && sudo cat <<EOF > config.ini
    [ndb_mgmd]
    hostname=ip-10-0-1-225.ec2.internal
    datadir=/opt/mysqlcluster/deploy/ndb_data
    nodeid=1
    
    [ndbd default]
    noofreplicas=3
    datadir=/opt/mysqlcluster/deploy/ndb_data
    
    [ndbd]
    hostname=ip-10-0-1-254.ec2.internal
    nodeid=2
    
    [ndbd]
    hostname=ip-10-0-1-126.ec2.internal
    nodeid=3
    
    [ndbd]
    hostname=ip-10-0-1-6.ec2.internal
    nodeid=4
    
    [mysqld]
    nodeid=50
    """,
    # phase 3
    "cd /opt/mysqlcluster/home/mysqlc && sudo scripts/mysql_install_db --no-defaults --datadir=/opt/mysqlcluster/deploy/mysqld_data",
    "sudo /opt/mysqlcluster/home/mysqlc/bin/ndb_mgmd -f /opt/mysqlcluster/deploy/conf/config.ini --initial --configdir=/opt/mysqlcluster/deploy/conf/",
    'mysqld --defaults-file="/opt/mysqlcluster/deploy/conf/my.cnf" --user=root &'
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