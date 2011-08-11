'''
Created on Dec 6, 2010

@author: borja
'''

import threading
import paramiko, dg_paraproxy
import operator
import traceback
import select
import sys
import time
from boto.ec2.connection import EC2Connection,RegionInfo
from os import walk, environ
import socket    
from demogrid.common import log
import os
import signal
from Crypto.Random import atfork
import glob
from boto import connect_ec2
        
class ThreadAbortException(Exception):
    pass
        
class DemoGridThread (threading.Thread):
    def __init__ (self, multi, name, depends = None):
        threading.Thread.__init__(self)
        self.multi = multi
        self.name = name
        self.exception = None
        self.stack_trace = None
        self.status = -1
        self.depends = depends
        
    def check_continue(self):
        if self.multi.abort.is_set():
            raise ThreadAbortException()
        
    def run2(self):
        pass
        
    def run(self):
        try:
            self.run2()
            self.status = 0
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.exception = exc_value
            self.stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
            self.status = 1
            self.multi.thread_failure(self)
            
        if self.status == 0:
            self.multi.thread_success(self)

class MultiThread(object):
    def __init__(self):
        self.num_threads = 0
        self.done_threads = 0
        self.threads = {}
        self.lock = threading.Lock()
        self.all_done = threading.Event()
        self.abort = threading.Event()

    def add_thread(self, thread):
        self.threads[thread.name] = thread     
        self.num_threads += 1

    def run(self):
        self.done_threads = 0
        for t in [th for th in self.threads.values() if th.depends == None]:
            t.start()
        self.all_done.wait()
        
    def thread_success(self, thread):
        with self.lock:
            self.done_threads += 1
            log.debug("%s thread has finished successfully." % thread.name)
            log.debug("%i threads are done. Remaining: %s" % (self.done_threads, ",".join([t.name for t in self.threads.values() if t.status == -1])))
            for t in [th for th in self.threads.values() if th.depends == thread]:
                t.start()            
            if self.done_threads == self.num_threads:
                self.all_done.set()            

    def thread_failure(self, thread):
        with self.lock:
            if not isinstance(thread.exception, ThreadAbortException):
                log.debug("%s thread has failed: %s" % (thread.name, thread.exception))
                self.abort.set()
            else:
                log.debug("%s thread is being aborted." % thread.name)
                thread.status = 2
            self.done_threads += 1
            self.abort_dependents(thread)
            log.debug("%i threads are done. Remaining: %s" % (self.done_threads, ",".join([t.name for t in self.threads.values() if t.status == -1])))
            if self.done_threads == self.num_threads:
                self.all_done.set()           
                
    def abort_dependents(self, thread):
        dep = [th for th in self.threads.values() if th.depends == thread]
        for th in dep:
            log.debug("%s thread is being aborted because it depends on failed %s thread." % (th.name, thread.name))
            th.status = 3
            self.done_threads += 1
            self.abort_dependents(th)
        
    def all_success(self):
        return all([t.status == 0 for t in self.threads.values()])
        
    def get_exceptions(self):
        return dict([(t.name, (t.exception, t.stack_trace)) for t in self.threads.values() if t.status == 1]) 

# From http://code.activestate.com/recipes/496735-workaround-for-missed-sigint-in-multithreaded-prog/
# Modified so it will run a cleanup function
class SIGINTWatcher(object):
    """this class solves two problems with multithreaded
    programs in Python, (1) a signal might be delivered
    to any thread (which is just a malfeature) and (2) if
    the thread that gets the signal is waiting, the signal
    is ignored (which is a bug).

    The watcher is a concurrent process (not thread) that
    waits for a signal and the process that contains the
    threads.  See Appendix A of The Little Book of Semaphores.
    http://greenteapress.com/semaphores/

    I have only tested this on Linux.  I would expect it to
    work on the Macintosh and not work on Windows.
    """
    
    def __init__(self, cleanup_func):
        """ Creates a child thread, which returns.  The parent
            thread waits for a KeyboardInterrupt and then kills
            the child thread.
        """
        self.cleanup_func = cleanup_func
        self.child = os.fork()
        if self.child == 0:
            return
        else:
            self.watch()

    def watch(self):
        try:
            os.wait()
        except KeyboardInterrupt:
            self.cleanup_func()
            self.kill()
        sys.exit()

    def kill(self):
        try:
            os.kill(self.child, signal.SIGKILL)
        except OSError: pass
        

class SSHCommandFailureException(Exception):
    def __init__(self, ssh, command):
        self.ssh = ssh
        self.command = command
        
        
class SSH(object):
    def __init__(self, username, hostname, key_path, default_outf = sys.stdout, default_errf = sys.stderr, port=22):
        self.username = username
        self.hostname = hostname
        self.key_path = key_path
        self.default_outf = default_outf
        self.default_errf = default_errf
        self.port = port
        
    def open(self, timeout = 180):
        key = paramiko.RSAKey.from_private_key_file(self.key_path)
        connected = False
        remaining = timeout
        while not connected:
            try:
                if remaining < 0:
                    raise Exception("SSH timeout")
                else:
                    atfork()
                    self.client = paramiko.SSHClient()
                    self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    self.client.connect(self.hostname, self.port, self.username, pkey=key)
                    connected = True
            except Exception, e:
                if remaining - 2 < 0:
                    raise e
                else:
                    time.sleep(2)
                    remaining -= 2
            
#             socket.error, e:
#                if e.errno == 111: # Connection refused
#                    time.sleep(2)
#                    remaining -= 2
#                else:
#                    time.sleep(2)
#                    remaining -= 2
#            except EOFError, e:
#                time.sleep(2)
#                remaining -= 2
#            except paramiko.SSHException, e:
#                if e.message in ("Error reading SSH protocol banner", "Authentication failed."):
#                    time.sleep(2)
#                    remaining -= 2
#                else:
#                    if remaining - 2 < 0:
#                        raise e
#            except:
#                if remaining - 2 < 0:
#                    raise e
        self.sftp = paramiko.SFTPClient.from_transport(self.client.get_transport())    
        
    def close(self):
        self.client.close()
        
    def run(self, command, outf=None, errf=None, exception_on_error = True, expectnooutput=False):
        channel = self.client.get_transport().open_session()
        
        log.debug("%s - Running %s" % (self.hostname,command))
        
        if expectnooutput:
            outf = None
            errf = None
        else:
            if outf != None:
                outf = open(outf, "w")
            else:
                outf = self.default_outf
        
            if errf != None:
                errf = open(errf, "w")
            else:
                errf = self.default_errf
            
        try:
            channel.exec_command(command)
    
            if outf != None or errf != None:
                while True:
                    rl, wl, xl = select.select([channel],[],[])
                    if len(rl) > 0:
                        # Must be stdout
                        x = channel.recv(1)
                        if not x: break
                        outf.write(x)
                        outf.flush()
                
                if outf != sys.stdout:
                    outf.close()
                    
                if errf != sys.stderr:
                    outf.close()
            
            log.debug("%s - Waiting for exit status: %s" % (self.hostname,command))
            rc = channel.recv_exit_status()
            log.debug("%s - Ran %s" % (self.hostname,command))
            channel.close()
        except Exception, e:
            raise # Replace by something more meaningful
         
        if exception_on_error and rc != 0:
            raise SSHCommandFailureException(self, command)
        else:
            return rc
    

        
        
    def scp(self, fromf, tof):
        # Create directory if it does not exist
        try:
            self.sftp.stat(os.path.dirname(tof))
        except IOError, e:
            pdirs = get_parent_directories(tof)
            for d in pdirs:
                try:
                    self.sftp.stat(d)
                except IOError, e:
                    self.sftp.mkdir(d)        
        try:
            self.sftp.put(fromf, tof)
        except Exception, e:
            traceback.print_exc()
            try:
                self.close()
            except:
                pass
        log.debug("scp %s -> %s:%s" % (fromf, self.hostname, tof))
        
    def scp_dir(self, fromdir, todir):
        for root, dirs, files in walk(fromdir):
            todir_full = todir + "/" + root[len(fromdir):]
            try:
                self.sftp.stat(todir_full)
            except IOError, e:
                self.sftp.mkdir(todir_full)
            for f in files:
                fromfile = root + "/" + f
                tofile = todir_full + "/" + f
                self.sftp.put(fromfile, tofile)
                log.debug("scp %s -> %s:%s" % (fromfile, self.hostname, tofile))

    
def create_ec2_connection(hostname = None, path = None, port = None):
    if hostname == None:
        # We're using EC2.
        # Check for AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY,
        # and use EC2Connection. boto will fill in all the values
        if not (environ.has_key("AWS_ACCESS_KEY_ID") and environ.has_key("AWS_SECRET_ACCESS_KEY")):
            return None
        else:
            return EC2Connection()
    else:
        # We're using an EC2-ish cloud.
        # Check for EC2_ACCESS_KEY and EC2_SECRET_KEY (these are used by Eucalyptus;
        # we will probably have to tweak this further to support other systems)
        if not (environ.has_key("EC2_ACCESS_KEY") and environ.has_key("EC2_SECRET_KEY")):
            return None
        else:
            print "Setting region"
            region = RegionInfo(name="eucalyptus", endpoint=hostname)
            return connect_ec2(aws_access_key_id=environ["EC2_ACCESS_KEY"],
                        aws_secret_access_key=environ["EC2_SECRET_KEY"],
                        is_secure=False,
                        region=region,
                        port=port,
                        path=path)            
    
def parse_extra_files_files(f, generated_dir):
    l = []
    extra_f = open(f)
    for line in extra_f:
        srcglob, dst = line.split()
        srcglob = srcglob.replace("@", generated_dir)
        srcs = glob.glob(os.path.expanduser(srcglob))
        srcs = [s for s in srcs if os.path.isfile(s)]
        dst_isdir = (os.path.basename(dst) == "")
        for src in srcs:
            full_dst = dst
            if dst_isdir:
                full_dst += os.path.basename(src)
            l.append( (src, full_dst) )
    return l
    
    
def get_parent_directories(filepath):
    dir = os.path.dirname(filepath)
    dirs = [dir]
    while dir != "/":
        dir = os.path.dirname(dir)
        dirs.append(dir)
    dirs.reverse()
    return dirs

# From http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)


