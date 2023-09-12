# Similar to subprocess, but with 100% detached processes

## Tested against Windows 10 / Python 3.10 / Anaconda and Ubuntu

### pip install detachedproc


The module defines a Python class named DetachedPopen that enable the execution and management 
of detached processes, primarily on Windows but with some compatibility for Unix-like systems as well.

Here's an overview of what the module does:

## Detached Process Execution: 

The main purpose of the module is to execute external processes in a detached manner, 
meaning the processes run independently of the Python script, 
and the script can continue its execution without waiting for the process to finish.

## Windows Compatibility: 

The module provides options for running processes with various Windows-specific features, 
such as specifying window styles ("Normal," "Hidden," "Minimized," "Maximized") 
and verbs (used in shell execution).

## Input and Output Handling: 

It allows you to specify the standard input of the process and capture its standard output and standard error. 
You can print or capture the output as needed. 
Additionally, it supports buffering for both standard output and standard error.

## Process Monitoring: 

The module uses the psutil library to monitor and manage processes. 
It can track child processes spawned by the executed command.

## Temporary File Management: 

Temporary files are created for various purposes (e.g., passing input, capturing output) 
during process execution. You have the option to delete these temporary files when they are no longer needed.

## Compatibility with subprocess: 

The module is designed with some compatibility with the subprocess.Popen class, 
allowing users familiar with the standard library subprocess module to transition to 
this more specialized functionality while maintaining a similar interface.

# Advantages:

## Detached Execution: 

This module is particularly useful when you need to run external commands or processes that might take a long time to complete, and you want your Python script to continue executing other tasks without waiting for the external process.

## Windows Integration: 

It offers features specifically tailored for Windows users, such as controlling window styles and verbs when executing processes.

## Input and Output Handling: 

It provides flexibility in handling process input and capturing output, which can be essential when dealing with command-line tools and automation.


```python



import subprocess
from time import sleep
from detachedproc import DetachedPopen

p=DetachedPopen(
    args=[rf"ping.exe",'-n','10000', "8.8.8.8"],
    bufsize=-1,
    executable=None,
    stdin=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    preexec_fn=None,
    close_fds=True,
    shell=False,
    cwd=None,
    env=None,
    universal_newlines=None,
    startupinfo=None,
    creationflags=0,
    restore_signals=True,
    start_new_session=False,
    pass_fds=(),
    user=None,
    group=None,
    extra_groups=None,
    encoding=None,
    errors=None,
    text=None,
    umask=-1,
    pipesize=-1,
    window_style="Hidden",
    wait=False,
    verb=None,
    what_if=False,
    print_stdout=False,
    print_stderr=False,
    capture_stdout=True,
    capture_stderr=True,
    stdoutbuffer=None,
    stderrbuffer=None,
    psutil_timeout=15,
    delete_tempfiles=True,
)
while True:
    print(p.stdout.read())
    sleep(1)
	
	
	
	
A class for launching and managing detached processes.

This class provides a way to execute processes in the background, similar to the `subprocess.Popen` class.
It allows you to run processes with various options and provides methods for controlling and monitoring them.

Args:
	args (list or str): The command to be executed as a list of arguments or a single string to be parsed.
	bufsize (int): Not used; included for compatibility with `subprocess.Popen`.
	executable (str): Not used; included for compatibility with `subprocess.Popen`.
	stdin (str or None): Input to be provided to the process's standard input. Default is None.
	stdout (None or subprocess.PIPE): The standard output of the process. Default is None.
	stderr (None or subprocess.PIPE): The standard error of the process. Default is None.
	preexec_fn (callable or None): Not used; included for compatibility with `subprocess.Popen`.
	close_fds (bool): Not used; included for compatibility with `subprocess.Popen`.
	shell (bool): Not used; included for compatibility with `subprocess.Popen`.
	cwd (str or None): The working directory for the process. Default is None.
	env (dict or None): The environment variables to be used for the process. Default is None.
	universal_newlines (bool or None): Not used; included for compatibility with `subprocess.Popen`.
	startupinfo (subprocess.STARTUPINFO): Not used; included for compatibility with `subprocess.Popen`.
	creationflags (int): Not used; included for compatibility with `subprocess.Popen`.
	restore_signals (bool): Not used; included for compatibility with `subprocess.Popen`.
	start_new_session (bool): Not used; included for compatibility with `subprocess.Popen`.
	pass_fds (tuple): Not used; included for compatibility with `subprocess.Popen`.
	user (str or None): Not used; included for compatibility with `subprocess.Popen`.
	group (str or None): Not used; included for compatibility with `subprocess.Popen`.
	extra_groups (list or None): Not used; included for compatibility with `subprocess.Popen`.
	encoding (str or None): Not used; included for compatibility with `subprocess.Popen`.
	errors (str or None): Not used; included for compatibility with `subprocess.Popen`.
	text (bool or None): Not used; included for compatibility with `subprocess.Popen`.
	umask (int): Not used; included for compatibility with `subprocess.Popen`.
	pipesize (int): Not used; included for compatibility with `subprocess.Popen`.
	wait (bool): Whether to wait for the process to complete before returning. Default is False.
	verb (str or None): The verb to use when executing the process (Windows only). Default is None.
	what_if (bool): Whether to simulate the execution of the process without actually running it (Windows only).
		Default is False.
	window_style (str): The window style for the process (Windows only).
		Possible values: "Normal", "Hidden", "Minimized", "Maximized". Default is "Normal".
	print_stdout (bool): Whether to print the process's standard output. Default is True.
	print_stderr (bool): Whether to print the process's standard error. Default is True.
	capture_stdout (bool): Whether to capture the process's standard output. Default is True.
	capture_stderr (bool): Whether to capture the process's standard error. Default is True.
	stdoutbuffer (int or None): The maximum number of lines to buffer for standard output. Default is None.
	stderrbuffer (int or None): The maximum number of lines to buffer for standard error. Default is None.
	psutil_timeout (int): The maximum time to wait for process information using psutil. Default is 15 seconds.
	delete_tempfiles (bool): Whether to delete temporary files created during execution. Default is True.

Attributes:
	args (list or str): The command to be executed as a list of arguments or a single string to be parsed.
	bufsize (int): Not used; included for compatibility with `subprocess.Popen`.
	executable (str): Not used; included for compatibility with `subprocess.Popen`.
	stdin (str or None): Input to be provided to the process's standard input. Default is None.
	stdout (StdOutStdErr): An object for reading the process's standard output.
	stderr (StdOutStdErr): An object for reading the process's standard error.
	preexec_fn (callable or None): Not used; included for compatibility with `subprocess.Popen`.
	close_fds (bool): Not used; included for compatibility with `subprocess.Popen`.
	shell (bool): Not used; included for compatibility with `subprocess.Popen`.
	cwd (str or None): The working directory for the process. Default is None.
	env (dict or None): The environment variables to be used for the process. Default is None.
	universal_newlines (bool or None): Not used; included for compatibility with `subprocess.Popen`.
	startupinfo (subprocess.STARTUPINFO): Not used; included for compatibility with `subprocess.Popen`.
	creationflags (int): Not used; included for compatibility with `subprocess.Popen`.
	restore_signals (bool): Not used; included for compatibility with `subprocess.Popen`.
	start_new_session (bool): Not used; included for compatibility with `subprocess.Popen`.
	pass_fds (tuple): Not used; included for compatibility with `subprocess.Popen`.
	user (str or None): Not used; included for compatibility with `subprocess.Popen`.
	group (str or None): Not used; included for compatibility with `subprocess.Popen`.
	extra_groups (list or None): Not used; included for compatibility with `subprocess.Popen`.
	encoding (str or None): Not used; included for compatibility with `subprocess.Popen`.
	errors (str or None): Not used; included for compatibility with `subprocess.Popen`.
	text (bool or None): Not used; included for compatibility with `subprocess.Popen`.
	umask (int): Not used; included for compatibility with `subprocess.Popen`.
	pipesize (int): Not used; included for compatibility with `subprocess.Popen`.
	wait (bool): Whether to wait for the process to complete before returning. Default is False.
	verb (str or None): The verb to use when executing the process (Windows only). Default is None.
	what_if (bool): Whether to simulate the execution of the process without actually running it (Windows only).
		Default is False.
	window_style (str): The window style for the process (Windows only).
		Possible values: "Normal", "Hidden", "Minimized", "Maximized". Default is "Normal".
	print_stdout (bool): Whether to print the process's standard output. Default is True.
	print_stderr (bool): Whether to print the process's standard error. Default is True.
	capture_stdout (bool): Whether to capture the process's standard output. Default is True.
	capture_stderr (bool): Whether to capture the process's standard error. Default is True.
	stdoutbuffer (int or None): The maximum number of lines to buffer for standard output. Default is None (No limit).
	stderrbuffer (int or None): The maximum number of lines to buffer for standard error. Default is None (No limit).
	psutil_timeout (int): The maximum time to wait for process information using psutil. Default is 15 seconds.
	delete_tempfiles (bool): Whether to delete temporary files created during execution. Default is True.

Methods:
	terminate(): Terminate the process.
	kill(): Terminate the process.
	send_signal(): Terminate the process.

	To read standard output:

	stdout.read(): Read the process's standard output.
	stdout.readlines(): Read the process's standard output as a list of lines.
	stdout.readline(): Read a single line from the process's standard output.

	To read standard error:

	stderr.read(): Read the process's standard error.
	stderr.readlines(): Read the process's standard error as a list of lines.
	stderr.readline(): Read a single line from the process's standard error.


To use it on Ubuntu

# Update the list of packages
sudo apt-get update
# Install pre-requisite packages.
sudo apt-get install -y wget apt-transport-https software-properties-common
# Download the Microsoft repository GPG keys
wget -q "https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/packages-microsoft-prod.deb"
# Register the Microsoft repository GPG keys
sudo dpkg -i packages-microsoft-prod.deb
# Delete the the Microsoft repository GPG keys file
rm packages-microsoft-prod.deb
# Update the list of packages after we added packages.microsoft.com
sudo apt-get update
# Install PowerShell
sudo apt-get install -y powershell
# Start PowerShell
pwsh
# As superuser, register the Microsoft repository once. After registration, you can update PowerShell with 
sudo apt-get install powershell.
```