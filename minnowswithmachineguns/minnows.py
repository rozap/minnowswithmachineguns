#!/bin/env python

"""
The MIT License

Copyright (c) 2010 The Chicago Tribune & Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from multiprocessing import Pool
import os
import json
import re
import socket
import time
import urllib2
import csv
import math
import random
from dop.client import Client
import paramiko

STATE_FILENAME = os.path.expanduser('~/.minnows')

# Utilities

def _read_server_list():
    if not os.path.isfile(STATE_FILENAME):
        return None, None, None, []
    with open(STATE_FILENAME, 'r') as f:
        server_state = json.loads(f.read())
        return server_state['client_key'], server_state['api_key'], server_state['login'], server_state['droplets']

def _write_server_list(client_key, api_key, login, droplets):
    with open(STATE_FILENAME, 'w') as f:
        d = {
            'client_key' : client_key, 
            'api_key' : api_key,
            'login' : login,
            'droplets' : [d.id for d in droplets]
        }
        f.write(json.dumps(d))

def _delete_server_list():
    os.remove(STATE_FILENAME)



# Methods

def up(count, client_key, api_key, login, size = 66, region_id = 1, ssh_keys = None):
    """
    Startup the load testing server.
    """
    count = int(count)
    client = Client(client_key, api_key)
    print 'Attempting to call up %i minnows.' % count

    if not ssh_keys:
        ssh_keys = [str(k.id) for k in client.all_ssh_keys()]

    droplet_ids = []
    droplets = []

    #25489 is ubuntu 12.04 
    for i in range(0, count):
        droplet = client.create_droplet('minnow-%s' % i, size, 25489, region_id, ssh_keys)
        droplet_ids.append(droplet.id)

    print "Started droplets with ids: %s" % ','.join([str(i) for i in droplet_ids])
    print "Waiting for minnows to wake up..."

    for drop_id in droplet_ids:
        droplet = client.show_droplet(drop_id)
        while (not droplet.status == 'active') or droplet.ip_address == -1:
            print '.'
            time.sleep(4)
            droplet = client.show_droplet(drop_id)
        droplets.append(droplet)
        print "Droplet id %s is ready" % drop_id

    print "The school of minnows has been assembled."
    _write_server_list(client_key, api_key, login, droplets)
    print "Arming the minnows with Apache Bench..."
    #TODO: Can't ssh into the servers for a bit...is there a better way to do this rather than
    #sleeping for an arbitrary amount of time?
    time.sleep(20)

    
    params = []
    for droplet in droplets:
        params.append({
            'droplet_id': droplet.id,
            'ip_address': droplet.ip_address,
            'login': login,
        })
    # Spin up processes for connecting to EC2 instances
    pool = Pool(len(params))
    pool.map(_install_apache_utils, params)
    return

def status():
    """
    Report the status of the load testing servers.
    """
    client_key, api_key, login, droplet_ids = _read_server_list()
    client = Client(client_key, api_key)

    if len(droplet_ids) == 0:
        print 'No minnows have been mobilized.'
        return
    print "Getting status of minnows"
    for drop_id in droplet_ids:
        droplet = client.show_droplet(drop_id)
        print 'minnow %s: %s @ %s' % (droplet.id, droplet.status, droplet.ip_address)
        

def down():
    """
    Shutdown the load testing server.
    """
    client_key, api_key, login, droplet_ids = _read_server_list()

    if not droplet_ids:
        print 'No minnows have been mobilized.'
        return

    print 'Connecting to the ocean.'
    client = Client(client_key, api_key)

    for droplet_id in droplet_ids:
        res = client.destroy_droplet(droplet_id)
        print "Destroyed %s" % res

    _delete_server_list()


def _install_apache_utils(params):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            params['ip_address'],
            username=params['login'])
        stdin, stdout, stderr = client.exec_command('apt-get install apache2-utils -y')
        stdout.read()
        print "Armed minnow %s with Apache Bench" % params['droplet_id']
    except socket.error, e:
        return e

def _attack(params):
    """
    Test the target URL with requests.

    Intended for use with multiprocessing.
    """
    print 'minnow %i is joining the school.' % params['i']

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            params['ip_address'],
            username=params['login'])

        print 'minnow %i is firing her machine gun. Bang bang!' % params['i']

        options = ''
        if params['headers'] is not '':
            for h in params['headers'].split(';'):
                options += ' -H "%s"' % h

        stdin, stdout, stderr = client.exec_command('tempfile -s .csv')
        params['csv_filename'] = stdout.read().strip()
        if params['csv_filename']:
            options += ' -e %(csv_filename)s' % params
        else:
            print 'minnow %i lost sight of the target (connection timed out creating csv_filename).' % params['i']
            return None
            
        if params['post_file']:
            os.system("scp -q -o 'StrictHostKeyChecking=no' %s %s@%s:/tmp/honeycomb" % (params['post_file'], params['login'], params['ip_address']))
            options += ' -k -T "%(mime_type)s; charset=UTF-8" -p /tmp/honeycomb' % params

        params['options'] = options
        benchmark_command = 'ab -r -n %(num_requests)s -c %(concurrent_requests)s -C "sessionid=NotARealSessionID" %(options)s "%(url)s"' % params
        stdin, stdout, stderr = client.exec_command(benchmark_command)

        response = {}

        ab_results = stdout.read()
        ms_per_request_search = re.search('Time\ per\ request:\s+([0-9.]+)\ \[ms\]\ \(mean\)', ab_results)

        if not ms_per_request_search:
            print 'minnow %i lost sight of the target (connection timed out running ab).' % params['i']
            return None

        requests_per_second_search = re.search('Requests\ per\ second:\s+([0-9.]+)\ \[#\/sec\]\ \(mean\)', ab_results)
        failed_requests = re.search('Failed\ requests:\s+([0-9.]+)', ab_results)
        complete_requests_search = re.search('Complete\ requests:\s+([0-9]+)', ab_results)

        response['ms_per_request'] = float(ms_per_request_search.group(1))
        response['requests_per_second'] = float(requests_per_second_search.group(1))
        response['failed_requests'] = float(failed_requests.group(1))
        response['complete_requests'] = float(complete_requests_search.group(1))

        stdin, stdout, stderr = client.exec_command('cat %(csv_filename)s' % params)
        response['request_time_cdf'] = []
        for row in csv.DictReader(stdout):
            row["Time in ms"] = float(row["Time in ms"])
            response['request_time_cdf'].append(row)
        if not response['request_time_cdf']:
            print 'minnow %i lost sight of the target (connection timed out reading csv).' % params['i']
            return None

        print 'minnow %i is out of ammo.' % params['i']

        client.close()

        return response
    except socket.error, e:
        return e

def _print_results(results, params, csv_filename):
    """
    Print summarized load-testing results.
    """
    timeout_minnows = [r for r in results if r is None]
    exception_minnows = [r for r in results if type(r) == socket.error]
    complete_minnows = [r for r in results if r is not None and type(r) != socket.error]

    timeout_minnows_params = [p for r,p in zip(results, params) if r is None]
    exception_minnows_params = [p for r,p in zip(results, params) if type(r) == socket.error]
    complete_minnows_params = [p for r,p in zip(results, params) if r is not None and type(r) != socket.error]

    num_timeout_minnows = len(timeout_minnows)
    num_exception_minnows = len(exception_minnows)
    num_complete_minnows = len(complete_minnows)

    if exception_minnows:
        print '     %i of your minnows didn\'t make it to the action. They might be taking a little longer than normal to find their machine guns, or may have been terminated without using "minnows down".' % num_exception_minnows

    if timeout_minnows:
        print '     Target timed out without fully responding to %i minnows.' % num_timeout_minnows

    if num_complete_minnows == 0:
        print '     No minnows completed the mission. Apparently your minnows are peace-loving hippies.'
        return

    complete_results = [r['complete_requests'] for r in complete_minnows]
    total_complete_requests = sum(complete_results)
    print '     Complete requests:\t\t%i' % total_complete_requests

    complete_results = [r['failed_requests'] for r in complete_minnows]
    total_failed_requests = sum(complete_results)
    print '     Failed requests:\t\t%i' % total_failed_requests

    complete_results = [r['requests_per_second'] for r in complete_minnows]
    mean_requests = sum(complete_results)
    print '     Requests per second:\t%f [#/sec]' % mean_requests

    complete_results = [r['ms_per_request'] for r in complete_minnows]
    mean_response = sum(complete_results) / num_complete_minnows
    print '     Time per request:\t\t%f [ms] (mean of minnows)' % mean_response

    # Recalculate the global cdf based on the csv files collected from
    # ab. Can do this by sampling the request_time_cdfs for each of
    # the completed minnows in proportion to the number of
    # complete_requests they have
    n_final_sample = 100
    sample_size = 100*n_final_sample
    n_per_minnow = [int(r['complete_requests']/total_complete_requests*sample_size)
                 for r in complete_minnows]
    sample_response_times = []
    for n, r in zip(n_per_minnow, complete_minnows):
        cdf = r['request_time_cdf']
        for i in range(n):
            j = int(random.random()*len(cdf))
            sample_response_times.append(cdf[j]["Time in ms"])
    sample_response_times.sort()
    request_time_cdf = sample_response_times[0:sample_size:sample_size/n_final_sample]

    print '     50%% responses faster than:\t%f [ms]' % request_time_cdf[49]
    print '     90%% responses faster than:\t%f [ms]' % request_time_cdf[89]

    if mean_response < 500:
        print 'Mission Assessment: Target crushed minnow offensive.'
    elif mean_response < 1000:
        print 'Mission Assessment: Target successfully fended off the school.'
    elif mean_response < 1500:
        print 'Mission Assessment: Target wounded, but operational.'
    elif mean_response < 2000:
        print 'Mission Assessment: Target severely compromised.'
    else:
        print 'Mission Assessment: school annihilated target.'

    if csv_filename:
        with open(csv_filename, 'w') as stream:
            writer = csv.writer(stream)
            header = ["% faster than", "all minnows [ms]"]
            for p in complete_minnows_params:
                header.append("minnow %(droplet_id)s [ms]" % p)
            writer.writerow(header)
            for i in range(100):
                row = [i, request_time_cdf[i]]
                for r in results:
                    row.append(r['request_time_cdf'][i]["Time in ms"])
                writer.writerow(row)
    
def attack(url, n, c, **options):
    """
    Test the root url of this site.
    """
    client_key, api_key, login, droplet_ids = _read_server_list()
    client = Client(client_key, api_key)

    if not login or not client_key or not api_key:
        print "You need to create the minnows first with the up command"
        return
    if not droplet_ids or len(droplet_ids) == 0:
        print 'No minnows are ready to attack.'
        return

    headers = options.get('headers', '')
    csv_filename = options.get("csv_filename", '')

    if csv_filename:
        try:
            stream = open(csv_filename, 'w')
        except IOError, e:
            raise IOError("Specified csv_filename='%s' is not writable. Check permissions or specify a different filename and try again." % csv_filename)
    


    print 'Assembling minnows.'
    droplets = []
    for droplet_id in droplet_ids:
        droplets.append(client.show_droplet(droplet_id))

    droplet_count = len(droplets)

    if n < droplet_count * 2:
        print 'minnows: error: the total number of requests must be at least %d (2x num. instances)' % (droplet_count * 2)
        return
    if c < droplet_count:
        print 'minnows: error: the number of concurrent requests must be at least %d (num. instances)' % droplet_count
        return
    if n < c:
        print 'minnows: error: the number of concurrent requests (%d) must be at most the same as number of requests (%d)' % (c, n)
        return

    requests_per_instance = int(float(n) / droplet_count)
    connections_per_instance = int(float(c) / droplet_count)

    print 'Each of %i minnows will fire %s rounds, %s at a time.' % (droplet_count, requests_per_instance, connections_per_instance)

    params = []
    for i, droplet in enumerate(droplets):
        params.append({
            'i': i,
            'droplet_id': droplet.id,
            'ip_address': droplet.ip_address,
            'url': url,
            'concurrent_requests': connections_per_instance,
            'num_requests': requests_per_instance,
            'login': login,
            'headers': headers,
            'post_file': options.get('post_file'),
            'mime_type': options.get('mime_type', ''),
        })

    print 'Hitting URL so it will be cached for the attack.'

    # Ping url so it will be cached for testing
    dict_headers = {}
    if headers is not '':
        dict_headers = headers = dict(h.split(':') for h in headers.split(';'))
    request = urllib2.Request(url, headers=dict_headers)
    urllib2.urlopen(request).read()

    print 'Organizing the school.'

    # Spin up processes for connecting to EC2 instances
    pool = Pool(len(params))

    results = pool.map(_attack, params)

    print 'Offensive complete.'

    _print_results(results, params, csv_filename)

    print 'The school is awaiting new orders.'



def show_sizes(client_key, api_key):
    print "Fetching Sizes..."
    client = Client(client_key, api_key)
    sizes = client.sizes()
    for s in sizes:
        print "Size id: %s has %s of memory" % (s.id, s.name[:-1])

def show_regions(client_key, api_key):
    print "Fetching Regions..."
    client = Client(client_key, api_key)
    regions = client.regions()
    for r in regions:
        print "Region id: %s is located in %s" % (r.id, r.name[:-1])

