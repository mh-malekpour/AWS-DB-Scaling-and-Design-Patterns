import random
import pymysql.cursors
from flask import Flask, request, jsonify
from flask_api import status
from pythonping import ping
from pymysql import ProgrammingError, Connection
from flask_api.exceptions import ParseError

# Database Nodes
manager_node = "ip-10-0-1-225.ec2.internal"
data_nodes = ["ip-10-0-1-254.ec2.internal", "ip-10-0-1-126.ec2.internal", "ip-10-0-1-6.ec2.internal"]

# Initialize Flask App
app = Flask(__name__)

def parse_request(req):
    """
    Parses the incoming request and validates its structure.

    :param req: The incoming Flask request object
    :return: Parsed data as a dictionary
    """
    if req.is_json:
        data = req.get_json()
        if 'SQL' in data and 'Mode' in data and data['Mode'] in ['Direct', 'Random', 'Fastest']:
            return data
    raise ParseError

def execute_query(mode, sql, query_type):
    """
    Executes the provided SQL query based on the selected mode.

    :param mode: Mode of operation ('Direct', 'Random', 'Fastest')
    :param sql: SQL query string
    :param query_type: Type of query ('Read', 'Write')
    :return: Query result or error message
    """
    target_node = manager_node if mode == 'Direct' or query_type == 'Write' else select_data_node(mode)
    try:
        with establish_connection(target_node) as connection:
            return process_query(connection, sql, query_type)
    except Exception as e:
        return jsonify({'error': str(e)}), status.HTTP_500_INTERNAL_SERVER_ERROR

def establish_connection(node):
    """
    Establishes a database connection to the specified node.

    :param node: IP address of the database node
    :return: Database connection object
    """
    return pymysql.connect(
            host=node,
            user='root',
            password='7221974',
            database='sakila',
            cursorclass=pymysql.cursors.DictCursor
    )

def process_query(connection, sql, query_type):
    """
    Processes the SQL query using the given connection.

    :param connection: Database connection object
    :param sql: SQL query string
    :param query_type: Type of query ('Read', 'Write')
    :return: Query result
    """
    with connection.cursor() as cursor:
        try:
            affected_rows = cursor.execute(sql)
            return cursor.fetchall() if query_type == 'Read' else f'Affected rows: {affected_rows}'
        except ProgrammingError as e:
            return jsonify(e.args), status.HTTP_400_BAD_REQUEST

def select_data_node(mode):
    """
    Selects a data node based on the specified mode.

    :param mode: Mode of operation ('Random', 'Fastest')
    :return: Selected data node IP address
    """
    return random.choice(data_nodes) if mode == 'Random' else find_fastest_node()

def find_fastest_node():
    """
    Finds the data node with the fastest response time.

    :return: IP address of the fastest data node
    """
    fastest_node = min(data_nodes, key=lambda node: ping(node).rtt_avg_ms)
    return fastest_node

@app.route('/', methods=['GET'])
def health_check():
    """ Confirms that the proxy server is operational. """
    return "Proxy server is operational.", status.HTTP_200_OK

@app.route('/read', methods=['GET'])
def handle_read():
    """ Handles read requests. """
    try:
        data = parse_request(request)
        return execute_query(data['Mode'], data['SQL'], 'Read')
    except ParseError as e:
        return e.detail, e.status_code

@app.route('/write', methods=['POST', 'PUT', 'DELETE'])
def handle_write():
    """ Handles write requests, always using the 'Direct' mode. """
    try:
        data = parse_request(request)
        return execute_query('Direct', data['SQL'], 'Write')
    except ParseError as e:
        return e.detail, e.status_code

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
