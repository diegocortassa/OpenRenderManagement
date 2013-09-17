#!/usr/bin/env python
# -*- coding: utf8 -*-

"""
pul_query.py: Utilitaire d'interrogation de puli
Permet de lancer des requetes http au serveur pour recuperer certaines informations utiles.

Requetes: "query?attr=id&attr=user"

attr: permet de choisir les attributs à récupérer sur chaque tâche [id user prod name ...]
format: long/csv
constraint:

"""
__author__      = "Jérôme Samson"
__copyright__   = "Copyright 2013, Mikros Image"


# Imports from libs
from tornado import ioloop, escape
from tornado.httpclient import AsyncHTTPClient
from optparse import OptionParser
from optparse import IndentedHelpFormatter
from datetime import datetime

import simplejson as json
import sys
import time
import urllib

# Imports from local dir
from settings import Settings



_query = "query?"
_hostname = Settings.hostname
_port = Settings.port

VERBOSE = Settings.verbose
REQUEST_BEGIN_TIME = ''
REQUEST_END_TIME = ''

def handle_request(response):
    """
    Callback for handling the request result.
    We try to load the data as JSON and display it according to the arguments or default specification
    """

    if response.error:
        print "Error:", response.error
    else:
        REQUEST_END_TIME = time.time() - REQUEST_BEGIN_TIME

        if VERBOSE: print ""
        if VERBOSE: print "Getting response for request \""+_query+"\" in " + str(REQUEST_END_TIME)

        if VERBOSE: print "DEBUG - Response: " + str(response)

        if response.body == "":
            print ""
            print "No jobs in queue."
            print ""
            sys.exit()


        # Parsing json
        try:
            _data = json.loads ( response.body )
        except KeyError, e:
            print "Error unknown key : " + str(e)
            sys.exit()
        except Exception, e:
            print "Error loading json: " + str(e)
            sys.exit()


        # Display data according to given args
        if options.json:
            print json.dumps( _data, indent=4 )

        elif options.csv:

            # Print header
            header = ""
            if _data['tasks'] is not None:
                header += ";".join(_data['tasks'][0].keys())
                print header

            # Print rows with ";" separator and without field indicator (usually " or ')
            for row in _data['tasks']:
                line=""
                for val in row.values():
                    line += ";"+( str(val) )
                print line[1:]

        else:
            # Default display
            print ""
            print " ID     NAME          PROD    SHOT  IMG  OWNER   PRIO ST    %  SUBMITTED    START        END          RUN_TIME  "
            print "--------------------------------------------------------------------------------------------------------------"

            for row in _data['tasks']:
                line=""

                creationTime = datetime.fromtimestamp( row['creationTime'] )
                creationTimeStr = datetime.strftime( creationTime, Settings.date_format )

                # startTime = datetime.fromtimestamp( row['startTime'] )
                # endTime = datetime.fromtimestamp( row['endTime'] )
                
                startTimeStr='-'
                endTimeStr='-'
                runTimeStr = "-"

                if row['startTime'] is not None:
                    startTime= datetime.fromtimestamp( row['startTime'] )
                    startTimeStr = datetime.strftime( startTime, Settings.date_format )

                    if row['endTime'] is not None:
                        endTimeStr = datetime.strftime( datetime.fromtimestamp( row['endTime'] ), Settings.date_format )
                        runTimeStr = str(datetime.fromtimestamp(row['endTime']) - startTime)
                    else:
                        runTimeStr = str(datetime.now() - startTime)

                # elapsedTime = datetime.now() - creationTime
                # print "Elapsed time = ", elapsedTime
                percentCompletion = int(row['completion']) * 100.0

                prod = 'prod' in row.keys() and row['prod'][:6] or ''
                shot = 'shot' in row.keys() and row['shot'][:4]  or ''
                frames = 'frames' in row.keys() and row['shot']  or ''

                print "%6d  %12s  %6s  %-4s  %-3s  %-6s  %4d %2s  %3d  %11s  %11s  %11s  %s" \
                    % ( row['id'], row['name'][:12], prod, shot, "-", row['user'][:6], \
                        row['priority'], Settings.status_short_name[row['status']], percentCompletion, \
                        creationTimeStr, startTimeStr, endTimeStr, runTimeStr )

            print ""
            print "Summary: " + str(_data['summary']['count']) + " of " +str(_data['summary']['totalInDispatcher'])+ " tasks retrieved in "+ str(_data['summary']['requestTime']*1000)[:3] +" ms."
            print ""

    # Quit loop
    ioloop.IOLoop.instance().stop()


###########################################################################################################################

class PlainHelpFormatter(IndentedHelpFormatter): 
    '''
    Subclass of OptParse format handler, will allow to have a raw text formatting in usage and desc fields.
    '''
    def format_description(self, description):
        if description:
            return description + "\n"
        else:
            return ""

def process_args():
    '''
    Manages arguments parsing definition and help information
    '''

    usage = "usage: %prog [general options] [restriction list] [output option]"
    desc="""Displays information about the server render queue.
To restrict the display to jobs of interest, a list of zero or more restriction options may be supplied. Each restriction may be one of:
    - a user matches all jobs owned by the specified owner
    - (TODO) a job id matches the specified job
    - (TODO)a date matches all jobs created after the given date
    - a constraint expression which matches all jobs that satisfy the specified expressions: FILTER="VALUE"
        user=jsa
        status=1 (value is a number corresponding to the states: "Blocked", "Ready", "Running", "Done", "Error", "Cancel", "Pause")
        name="mon job"
        creationtime="2013-09-09 14:00:00" (It filters all jobs created AFTER the given date/time)
    
Output options will indicate if the command will output information as human readable format, or csv or raw json
If no output option is specified, the ouput will be a single line presenting the following information:
id, name, prod, shot, frames, owner, priority, status, creation date, start date, end date and runtime


Example 1. Retrieve all task for a specific user:

> pul_query jsa

 ID     NAME          PROD  SHOT  IMG  OWNER   PRIO ST    %  SUBMITTED    START        END          RUN_TIME  
--------------------------------------------------------------------------------------------------------------
 28834  TG-task-with  -     -     -    jsa        0  C    0  09/11 16:13            -            -  -
 28836  TG-task-with  -     -     -    jsa        0  C    0  09/11 18:00            -            -  -
 28838  TG-task-with  -     -     -    jsa        0  I    0  09/11 18:01            -            -  -
 28832  TG-task-with  -     -     -    jsa        0  C    0  09/11 16:05            -            -  -
 28833  TG-task-with  -     -     -    jsa        0  C    0  09/11 16:05            -            -  -

Summary: 5 of 8 tasks retrieved in 0.5 ms.


Example 2. Retrieve all tasks created after a given time for a specific user:

> pul_query jsa -C creationtime="2013-09-11 16:00:00"

 ID     NAME          PROD  SHOT  IMG  OWNER   PRIO ST    %  SUBMITTED    START        END          RUN_TIME  
--------------------------------------------------------------------------------------------------------------
 28836  TG-task-with  -     -     -    jsa        0  C    0  09/11 18:00            -            -  -
 28838  TG-task-with  -     -     -    jsa        0  I    0  09/11 18:01            -            -  -

Summary: 2 of 8 tasks retrieved in 0.7 ms.


Example 3. Retrieve all tasks with status "Ready" for a specific user and presenting it as json:

> pul_query jsa -C status=1 -j

{ "tasks": [
        { "status": 1, 
            "completion": 0.0, 
            "updateTime": null, 
            "name": "TG-task-with-ram_2", 
            "creationTime": 1378915289.0, 
            "priority": 0, 
            "user": "jsa", 
            "startTime": null, 
            "endTime": null, 
            "id": 28838
        }
    ], 
    "summary": { "count": 1, 
        "totalInDispatcher": 8, 
        "requestTime": 0.00060296058654785156, 
        "requestDate": "Thu Sep 12 11:14:48 2013"
    }
}
"""

    parser = OptionParser(usage=usage, description=desc, version="%prog 0.1", formatter=PlainHelpFormatter() )

    parser.add_option("-c", "--csv", action="store_true", dest="csv", help="Returns data formatted as raw CSV file [%default]", default=False)
    parser.add_option("-j", "--json", action="store_true", dest="json", help="Returns data formatted as JSON [%default]", default=False)
    
    parser.add_option("-C", "--constraint", action="append", type="string", help="Allow user to specify one or more filter constraints")
    parser.add_option("-a", "--attribute", action="append", type="string", help="Allow user to display specific attributes only (WARNING if defined, result will be presented as csv by default, it can be overriden by -j flag)")

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help="Verbose mode [%default]", default=False)

    parser.add_option("-s", "--server", action="store", dest="hostname", help="Specified a target host to send the request")
    parser.add_option("-p", "--port", action="store", dest="port", help="Specified a target port")

    options, args = parser.parse_args()

    return options, args



if __name__ == '__main__':


    options, args = process_args()
    VERBOSE = options.verbose
    
    if VERBOSE:
        print "Command options: %s" % options
        print "Command arguments: %s" % args


    #
    # Apply display rules
    #
    if options.attribute is not None:
        # Specifc attributes is desired by arguments, we must ensure that either json or csv is activated 
        # And if not, activate csv display.
        if not options.json and not options.csv:
            options.csv = True


    #
    # Creating corresponding query
    #

    # Applying restriction arguments
    for arg in args:
        if arg.isdigit():
            print "TODO: user can specify an id to retrieve information on a specific job"
            if VERBOSE: print "int as arg, consider an id"
        else:
            _query += "&constraint_user=%s" % arg


    # Applying display attributes
    if options.attribute is not None:
        for attr in options.attribute:
            _query += "&attr=%s" % attr


    # Applying constraints
    if options.constraint is not None:
        for currConst in options.constraint:
            constraint = currConst.split("=",1)
            if len(constraint) < 2:
                print "Error: constraint is not valid, it must have the following format: -C field=value"
                continue
            constField = str(constraint[0])
            constVal = str(constraint[1])
            _query += "&constraint_%s=%s" % (constField , urllib.quote(constVal))


    #
    # Set hotsname/port if given as arguments
    #
    if options.hostname is not None:
        _hostname = options.hostname

    if options.port is not None:
        _port = options.port

    if VERBOSE:
        print "Host: %s" % _hostname
        print "Port: %s" % _port
        print "Request: %s" % _query
        # print "http://%s:%s/%s" % ( _hostname, _port, _query )

    _request = "http://%s:%s/%s" % ( _hostname, _port, _query )

    http_client = AsyncHTTPClient()

    REQUEST_BEGIN_TIME = time.time()
    http_client.fetch( _request, handle_request )

    ioloop.IOLoop.instance().start()

    ################
    # Methode secondaire pour interroger le serveur: verifier si httplib est bloquant ou async
    #
    # from octopus.core.http import Request
    # import httplib
    # conn = httplib.HTTPConnection(Settings.hostname, Settings.port)

    # def onResponse(request, response):
    #     print "%s %s ==> %d %s" % (request.method, request.path, response.status, response.reason)
    #     print response.read()

    # def onError(request, error):
    #     print "%s %s ==> %s" % (request.method, request.path, error)

    # r = Request("GET", "/"+_query, {"Accept": "application/json"}, "")
    # r.call(conn, onResponse, onError)
