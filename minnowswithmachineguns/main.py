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

import minnows
from urlparse import urlparse

from optparse import OptionParser, OptionGroup


def require_login(options, parser):
    if not options.client_key:
        parser.error('To spin up new instances you need to specify a client key with -c')
    if not options.api_key:
        parser.error('To spin up new instances you need to specify an api key with -a')


def parse_options():
    """
    Handle the command line arguments for spinning up minnows
    """
    parser = OptionParser(usage="""
minnows COMMAND [options]

Minnows with Machine Guns

A utility for arming (creating) many minnows (digital ocean instances) to attack
(load test) targets (web applications).

commands:
  up            Start a batch of load testing servers.
  attack        Begin the attack on a specific url.
  down          Shutdown and deactivate the load testing servers.
  status        Get the status of the load testing servers. (for use after up)
  show_regions  Show the regions available with their associated ids
  show_sizes    Show the sizes available with their associated ids
    """)

    up_group = OptionGroup(parser, "up",
        """In order to spin up new servers you will need to specify at least the -k command, which is the name of the EC2 keypair to use for creating and connecting to the new servers. The minnows will expect to find a .pem file with this name in ~/.ssh/.""")

    # Required
    up_group.add_option('-c', '--client_key',  metavar="CLIENT_KEY",  nargs=1,
                        action='store', dest='client_key', type='string',
                        help="The client key for your account")
    up_group.add_option('-a', '--api_key',  metavar="API_KEY",  nargs=1,
                        action='store', dest='api_key', type='string',
                        help="The api key for your account")
    up_group.add_option('-s', '--servers', metavar="SERVERS", nargs=1,
                        action='store', dest='servers', type='int', default=1,
                        help="The number of servers to start (default: 1).")

    #TODO: add help here
    up_group.add_option('-r', '--region',  metavar="REGION",  nargs=1,
                        action='store', dest='region_id', type='string', default='1',
                        help="The region id to start the servers in (1 = NY, 2 = DENMARK, 3 = SF).")

    up_group.add_option('-t', '--type',  metavar="TYPE",  nargs=1,
                        action='store', dest='type', type='string', default='66',
                        help="The instance-type (size) to use for each server (default: 66 - smallest size).")

    up_group.add_option('-l', '--login',  metavar="LOGIN",  nargs=1,
                        action='store', dest='login', type='string', default='root',
                        help="The ssh username name to use to connect to the new servers (default: root).")

    up_group.add_option('-k', '--ssh_keys',  metavar="SSH_KEYS",  nargs=1,
                        action='store', dest='ssh_keys', type='string', default=None,
                        help="The ssh key id to connect with (added through digital ocean control panel) (default : all)")
    parser.add_option_group(up_group)



    attack_group = OptionGroup(parser, "attack",
            """Beginning an attack requires only that you specify the -u option with the URL you wish to target.""")

    # Required
    attack_group.add_option('-u', '--url', metavar="URL", nargs=1,
                        action='store', dest='url', type='string',
                        help="URL of the target to attack.")
    attack_group.add_option('-p', '--post-file',  metavar="POST_FILE",  nargs=1,
                        action='store', dest='post_file', type='string', default=False,
                        help="The POST file to deliver with the minnow's payload.")
    attack_group.add_option('-m', '--mime-type',  metavar="MIME_TYPE",  nargs=1,
                        action='store', dest='mime_type', type='string', default='text/plain',
                        help="The MIME type to send with the request.")
    attack_group.add_option('-n', '--number', metavar="NUMBER", nargs=1,
                        action='store', dest='number', type='int', default=1000,
                        help="The number of total connections to make to the target (default: 1000).")
    attack_group.add_option('-x', '--concurrent', metavar="CONCURRENT", nargs=1,
                        action='store', dest='concurrent', type='int', default=100,
                        help="The number of concurrent connections to make to the target (default: 100).")
    attack_group.add_option('-H', '--headers', metavar="HEADERS", nargs=1,
                        action='store', dest='headers', type='string', default='',
                        help="HTTP headers to send to the target to attack. Multiple headers should be separated by semi-colons, e.g header1:value1;header2:value2")
    attack_group.add_option('-e', '--csv', metavar="FILENAME", nargs=1,
                        action='store', dest='csv_filename', type='string', default='',
                        help="Store the distribution of results in a csv file for all completed minnows (default: '').")

    parser.add_option_group(attack_group)

    (options, args) = parser.parse_args()

    if len(args) <= 0:
        parser.error('Please enter a command.')

    command = args[0]

    if command == 'up':
        require_login(options, parser)
        minnows.up(options.servers, options.client_key, options.api_key, options.login, options.type, options.region_id, options.ssh_keys)
    elif command == 'attack':
        if not options.url:
            parser.error('To run an attack you need to specify a url with -u')

        parsed = urlparse(options.url)
        if not parsed.scheme:
            parsed = urlparse("http://" + options.url)

        if not parsed.path:
            parser.error('It appears your URL lacks a trailing slash, this will disorient the minnows. Please try again with a trailing slash.')

        additional_options = dict(
            headers=options.headers,
            post_file=options.post_file,
            mime_type=options.mime_type,
            csv_filename=options.csv_filename,
        )

        minnows.attack(options.url, options.number, options.concurrent, **additional_options)

    elif command == 'down':
        minnows.down()
    elif command == 'status':
        minnows.status()
    elif command == 'show_sizes':
        require_login(options, parser)
        minnows.show_sizes(options.client_key, options.api_key)
    elif command == 'show_regions':
        require_login(options, parser)
        minnows.show_regions(options.client_key, options.api_key)


def main():
    parse_options()
