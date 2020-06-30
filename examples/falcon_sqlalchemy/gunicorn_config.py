# coding=utf-8

import gunicorn

# set the 'server' response header
gunicorn.SERVER_SOFTWARE = 'demo-graphql-sqlalchemy-falcon'

# set the socket to bind on (use 0.0.0.0 for bare deploy)
# this can also be set programatically via the -b flag
bind = 'localhost:5432'

# set the maximum number of pending transactions before an error is returned
backlog = 8192

# set workers
workers = 1

# set threads (optimize for cores * 2-4?)
threads = 1

# set worker class ('sync' is good for normal workloads)
worker_class = 'sync'

# set maximum number of simultaneous client connections per worker process
worker_connections = 4096

# set lifetime of worker in requests before mandatory restart (prevent leaks)
max_requests = 40960

# add jitter to max_requests to avoid workers all stopping at the same time
max_requests_jitter = 7040

# set connection timeout for killing a worker (async jobs still communicate)
timeout = 30

# set time to finish services before restart when signal is received
graceful_timeout = 60

# set keepalive HTTP connection wait time for next request (in seconds)
keepalive = 200

# limit size (in bytes) of requests to guard against denial-of-service attacks
limit_request_line = 8192

# limit number of request header fields as an additional safeguard
limit_request_fields = 25

# Load application code before workers are forked (saves RAM & speeds up boot)
preload = True

# enable reload for automatic worker restarts on code changes during development
#reload = False

# enable spew for intense debugging in order to dump all executed code
#spew = True

# enable daemon to detach worked processes from terminal
#daemon = True

# set logging format and level ('debug', 'info', 'warning', 'error', 'critical')
errorlog = '-'
loglevel = 'debug'
accesslog = '-'
access_log_format = '%(t)s %(s)s "%(r)s" %(L)s %(b)s'
access_log_file = None

# set process name
proc_name = 'demo-graphql-sqlalchemy-falcon'
