import re
import shlex
from collections import deque
import kthread_sleep
import psutil
import asyncio
import sys
import traceback
from time import sleep
import kthread
from time import time, perf_counter
import tempfile
import shutil
import subprocess
import os
from shortpath83 import convert_path_in_string
from touchtouch import touch
from typing import Union, Literal

try:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    creationflags = subprocess.CREATE_NO_WINDOW
    invisibledict = {
        "startupinfo": startupinfo,
        "creationflags": creationflags,
        "start_new_session": True,
    }
except Exception:
    invisibledict = {}
from what_os import check_os

myos = check_os()
if myos == "windows":
    taskkillpath = shutil.which("taskkill.exe")


def get_tmpfile(suffix=".bat"):
    tfp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    filename = tfp.name
    filename = os.path.normpath(filename)
    tfp.close()
    touch(filename)
    return filename


class ProcDescriptor:
    def __get__(self, instance, owner):
        return (
            None
            if not instance.__dict__[f"_{self.name}"]
            else instance.__dict__[f"_{self.name}"][0]
        )

    def __set__(self, instance, value):
        instance.__dict__[self.name] = []

    def __delete__(self, instance):
        instance.__dict__[self.name] = []

    def __set_name__(self, owner, name):
        self.name = name


class DetachedProcess:
    process = ProcDescriptor()

    def __init__(
        self,
        cmd: list,
        wait: bool = False,
        use_new_environment: bool = False,
        stdin: Union[str, None] = None,
        verb: Union[str, None] = None,
        what_if: bool = False,
        working_directory: Union[str, None] = None,
        window_style=Literal["Normal", "Hidden", "Minimized", "Maximized"],
        print_stdout: bool = True,
        print_stderr: bool = True,
        capture_stdout: bool = True,
        capture_stderr: bool = True,
        stdoutbuffer: Union[int, None] = None,
        stderrbuffer: Union[int, None] = None,
        psutil_timeout: int = 15,
        delete_tempfiles: bool = True,
        stderr_stdout_readmode="rb",
        args_to_83=True,
    ):
        self.window_style = window_style
        self.wait = wait
        self.use_new_environment = use_new_environment
        self.stdin = stdin
        self.verb = verb
        self.what_if = what_if
        if myos == "windows":
            self.psexe = shutil.which("powershell.exe")
        else:
            self.psexe = shutil.which("pwsh")
        self.tmpfile = None
        self.tmpfilestdout = None
        self.tmpfilestderr = None
        self.tmpfilestdin = None
        self.working_directory = working_directory
        self._process = []
        self.process = None
        self.allchildren = []
        self.cmd = cmd
        self.cmd_to_execute = None
        self.psutil_timeout = psutil_timeout
        self.psutil_iter = None
        self._stoptriggerstdout = [
            False,
        ]
        self._stoptriggerstderr = [
            False,
        ]
        if not stdoutbuffer:
            self.stdoutbuffer = []
        else:
            self.stdoutbuffer = deque([], stdoutbuffer)

        if not stderrbuffer:
            self.stderrbuffer = []
        else:
            self.stderrbuffer = deque([], stderrbuffer)
        self.capture_stdout = capture_stdout
        self.capture_stderr = capture_stderr
        self._tstdout = None
        self._tstderr = None
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr
        self._oldprocs = set()
        self._newprocs = set()
        self._newstartedprocs = set()
        self.wholecommandline = None
        self._adjustedcmd = []
        self.delete_tempfiles = delete_tempfiles
        self.is_alive = True
        self._isrunning_thread = None
        self.stderr_stdout_readmode = stderr_stdout_readmode
        self._subprocesspopen = []
        self.args_to_83 = args_to_83
        self.run()

    def __str__(self):
        return str(self.process).split("(", maxsplit=1)[1].strip(")")

    def _stdout_fu(self, line):
        if self.capture_stdout:
            self.stdoutbuffer.append(line)
        if self.print_stdout:
            sys.stdout.write(f"{line}\n")

    def _stderr_fu(self, line):
        if self.capture_stderr:
            self.stderrbuffer.append(line)
        if self.print_stderr:
            sys.stderr.write(f"{line}\n")

    def get_parent_children_proc(
        self,
    ):
        c2 = set([re.sub(r"\W+", "", x).lower() for x in self._adjustedcmd])
        found = False
        timeoutfinal = time() + self.psutil_timeout
        while not found and time() < timeoutfinal:
            try:
                for p in psutil.process_iter():
                    try:
                        self._newprocs.add(
                            (p.pid, p.name(), tuple(p.cmdline()), p.cwd())
                        )
                    except Exception:
                        continue

                for q in self._newprocs - self._oldprocs:
                    self._newstartedprocs.add(q)

                for e in self._newstartedprocs:
                    c1 = set([re.sub(r"\W+", "", x).lower() for x in e[2]])
                    if len(c1) == len(c2) == len(c1 & c2):
                        self._process.append(psutil.Process(e[0]))
                        self.allchildren.extend(self._process[-1].children())
                        found = True
                        break
            except Exception as fe:
                pass

    def _is_running(self):
        while not self.process:
            kthread_sleep.sleep(0.1)
        self.is_alive = self.process.is_running()
        kthread_sleep.sleep(2)
        while is_alive := self.process.is_running():
            self.is_alive = is_alive
            kthread_sleep.sleep(1)
        self.kill(taskkill=False)
        self.is_alive = False

    def run(self):
        if self.stdin:
            self.tmpfilestdin = get_tmpfile(suffix=".txt")
            with open(self.tmpfilestdin, "w", encoding="utf-8") as f:
                f.write(self.stdin)
            stdinadd = f" -RedirectStandardInput {self.tmpfilestdin} "
        else:
            stdinadd = ""

        if myos == "windows":
            self.tmpfile = get_tmpfile(suffix=".bat")
        else:
            self.tmpfile = get_tmpfile(suffix=".sh")
        self.tmpfilestdout = get_tmpfile(suffix=".txt")
        self.tmpfilestderr = get_tmpfile(suffix=".txt")

        UseNewEnvironment = (
            " -UseNewEnvironment $true " if self.use_new_environment else ""
        )
        Wait = " -Wait " if self.wait else ""
        Verb = "" if not self.verb else f" -Verb {self.verb} "
        WhatIf = " -WhatIf " if self.what_if else ""
        WindowStyle = self.window_style if self.window_style else "Normal"

        if "/" not in self.cmd[0] and "\\" not in self.cmd[0]:
            self.cmd[0] = shutil.which(self.cmd[0])
        FilePath = convert_path_in_string(self.cmd[0])
        self._adjustedcmd.append(FilePath)
        WorkingDirectory = (
            os.path.dirname(FilePath)
            if not self.working_directory
            else convert_path_in_string(self.working_directory)
        )

        ArgumentList = []
        try:
            if myos == "windows":
                _ArgumentList = [
                    f"""{x.replace('"', f'{os.sep}{os.sep}"')}""" for x in self.cmd[1:]
                ]
                for a in _ArgumentList:
                    if self.args_to_83:
                        cva = convert_path_in_string(a)
                        ArgumentList.append(cva)
                    else:
                        ArgumentList.append(a)
            else:
                ArgumentList = [
                    f"""{f'{x}'.replace('"', f'`"')}""" for x in self.cmd[1:]
                ]
        except Exception as fe:
            pass
        self._adjustedcmd.extend(ArgumentList)
        if ArgumentList:
            if myos == "windows":
                ArgumentList = f""" -ArgumentList \\"{' '.join(ArgumentList)}\\" """
            else:
                ArgumentList = f""" -ArgumentList \\"{' '.join(ArgumentList)}\\" """

        else:
            ArgumentList = ""

        if myos == "windows":
            self.wholecommandline = f"""{self.psexe} -ExecutionPolicy RemoteSigned Start-Process -FilePath {FilePath}{WhatIf}{Verb}{UseNewEnvironment}{Wait}{stdinadd}{ArgumentList}-RedirectStandardOutput {self.tmpfilestdout} -RedirectStandardError {self.tmpfilestderr} -WorkingDirectory {WorkingDirectory} -WindowStyle {WindowStyle}"""
            self.cmd_to_execute = self.wholecommandline
        else:
            self.wholecommandline = f'''{self.psexe} -ExecutionPolicy RemoteSigned -Command \"Start-Process -FilePath {FilePath} {WhatIf}{Verb}{UseNewEnvironment}{Wait}{stdinadd}{ArgumentList} -RedirectStandardOutput {self.tmpfilestdout} -RedirectStandardError {self.tmpfilestderr} -WorkingDirectory {WorkingDirectory}\"'''

            with open(self.tmpfile, "w") as script_file:
                script_file.write(self.wholecommandline)
                self.cmd_to_execute = self.wholecommandline
            os.chmod(
                self.tmpfile,
                0o777,
            )

        _stoptriggerstdout = [
            False,
        ]
        _stoptriggerstderr = [
            False,
        ]

        self._oldprocs = set()
        for p in psutil.process_iter():
            try:
                self._oldprocs.add((p.pid, p.name(), tuple(p.cmdline()), p.cwd()))
            except Exception:
                continue

        self.psutil_iter = kthread.KThread(
            target=self.get_parent_children_proc,
            name=str(perf_counter()),
        )
        self._tstdout = read_async(
            file=self.tmpfilestdout,
            asthread=True,
            mode=self.stderr_stdout_readmode,
            action=lambda line: self._stdout_fu(line),
            stoptrigger=self._stoptriggerstdout,
        )
        self._tstderr = read_async(
            file=self.tmpfilestderr,
            asthread=True,
            mode=self.stderr_stdout_readmode,
            action=lambda line: self._stderr_fu(line),
            stoptrigger=self._stoptriggerstderr,
        )
        if myos == "windows":
            self._subprocesspopen.append(
                subprocess.Popen(
                    self.cmd_to_execute,
                    cwd=self.working_directory,
                    env=os.environ.copy(),
                    shell=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    **invisibledict,
                )
            )

        else:
            self._subprocesspopen.append(
                subprocess.Popen(
                    ["nohup", self.tmpfile],
                    shell=False,
                    start_new_session=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            )

        self.psutil_iter.start()

        while (
            not self.allchildren
            and not self.process
            and not self.stdoutbuffer
            and not self.stderrbuffer
        ):
            kthread_sleep.sleep(0.1)
        if myos == "windows":
            self._subprocesspopen[-1].kill()
        self._isrunning_thread = kthread.KThread(
            target=self._is_running,
            name=str(perf_counter()),
        )
        self._isrunning_thread.start()

    def kill(self, taskkill=True):
        self._stoptriggerstdout.append(True)
        self._stoptriggerstderr.append(True)

        try:
            self._tstdout.kill()
        except Exception:
            pass
        try:
            self._tstderr.kill()
        except Exception:
            pass
        if taskkill:
            if myos == "windows":
                try:
                    subprocess.run(
                        f"{taskkillpath} /F /T /PID {self.process.pid}", **invisibledict
                    )
                except Exception:
                    pass
            try:
                self._subprocesspopen[0].kill()
            except Exception:
                pass
            try:
                self._isrunning_thread.kill()
            except Exception:
                pass
        if self.delete_tempfiles:
            for file in [
                self.tmpfile,
                self.tmpfilestdout,
                self.tmpfilestderr,
                self.tmpfilestdin,
            ]:
                try:
                    os.remove(file)
                except Exception as fe:
                    pass
        self.is_alive = False


class StdOutStdErr:
    def __init__(self, obj, std, bytesorstring="r", read_async=True):
        self.read_async = read_async
        self.obj = obj
        if std == "stdout":
            self._std = self.obj._running_proc.stdoutbuffer
        else:
            self._std = self.obj._running_proc.stderrbuffer
        self.bytesorstring = bytesorstring

    def read(self, *args, **kwargs):
        if self.read_async:
            tmpout = []
            if self._std:
                tmpout = [self._std.pop(0) for _ in range(len(self._std) - 1)]
            r = "".tmpout if self.bytesorstring == "r" else b"".join(tmpout)
            return r
        else:
            tmpout = self._std.copy()
            self._std.clear()
            r = "".tmpout if self.bytesorstring == "r" else b"".join(tmpout)
            return r

    def readlines(self, *args, **kwargs):
        if self.read_async:
            if self._std:
                tmpout = [self._std.pop(0) for _ in range(len(self._std) - 1)]
            else:
                tmpout = []
            return tmpout
        else:
            tmpout = self._std.copy()
            self._std.clear()

            return tmpout

    def readline(self, *args, **kwargs):
        try:
            r = self._std.pop(0)
        except Exception:
            r = "" if self.bytesorstring == "r" else b""
        return r

    def __getattr__(self, item):
        return None


def _start_as_tread(file, mode, action, stoptrigger, encoding, errors):
    t = kthread.KThread(
        target=_read_file_async,
        kwargs={
            "file": file,
            "mode": mode,
            "action": action,
            "stoptrigger": stoptrigger,
            "encoding": encoding,
            "errors": errors,
        },
    )
    t.daemon = True
    t.start()
    return t


def pfehler():
    etype, value, tb = sys.exc_info()
    traceback.print_exception(etype, value, tb)


def _read_file_async(
    file,
    mode="r",
    action=lambda line: sys.stderr.write((str(line) + "\n")),
    stoptrigger: list | tuple = (False,),
    encoding: str = "utf-8",
    errors: str = "backslashreplace",
):
    while not os.path.exists(file):
        sleep(0.005)

    async def start_reading():
        async def rline(_file):
            _file.seek(0, 2)
            while not stoptrigger[-1]:
                line = _file.readline()
                if not line:
                    # await asyncio.sleep(0.01)
                    continue
                yield line

        if "b" in mode:
            with open(file, mode) as f:
                reader_generator = rline(f)

                while not stoptrigger[-1]:
                    line = await anext(reader_generator)
                    action(line)
        else:
            with open(file, mode, encoding=encoding, errors=errors) as f:
                reader_generator = rline(f)

                while not stoptrigger[-1]:
                    line = await anext(reader_generator)
                    action(line)

    try:
        return asyncio.run(start_reading())
    except Exception:
        pfehler()


def read_async(
    file: str,
    asthread: bool = True,
    mode: str = "r",
    action=lambda line: sys.stderr.write((str(line) + "\n")),
    stoptrigger: list | tuple = (False,),
    encoding: str = "utf-8",
    errors: str = "backslashreplace",
):
    """
    Read a file asynchronously and process its content.

    Args:
        file (str): The path to the file to be read.
        asthread (bool, optional): If True, the function will start as a thread. Default is True.
        mode (str, optional): The mode in which the file is opened. Default is 'r' (read mode).
        action (function, optional): A function to be applied to each line of the file. Default is to write the line to stderr.
        stoptrigger (list | tuple, optional): A list or tuple (preferably a list) that triggers the function to stop reading when its last element is True. Default is [False].
        encoding (str, optional): The character encoding of the file. Default is 'utf-8'.
        errors (str, optional): How to handle encoding errors. Default is 'backslashreplace'.

    Returns:
        kthread.KThread or None: If as_thread is True, it returns a KThread object. Otherwise, it returns None.

    The advantage of this function is that it allows for real-time processing of the file while it is being written by another process.
    This is particularly useful in scenarios where the file is continuously updated, and the updates need to be processed immediately, such as in log monitoring or real-time data analysis.

    Example usage:
        from threading import Timer
        from time import time
        newfile = f'c:\\testfilex{str(time()).replace(".","_")}.txt'
        stoptrigger = [False,]
        t = read_async(
            file=newfile,
            as_thread=True,
            mode="r",
            action=lambda line: sys.stderr.write((str(line) + "\n")),
            stoptrigger=stoptrigger,
        )
        Timer(5, lambda: stoptrigger.append(True)).start() # Stops after 5 seconds and doesn't print anymore, but os.system goes on.
        os.system("ping 8.8.8.8 -n 10 > " + newfile + "")
    """
    if not asthread:
        return _read_file_async(
            file,
            mode=mode,
            action=action,
            stoptrigger=stoptrigger,
            encoding=encoding,
            errors=errors,
        )
    else:
        return _start_as_tread(file, mode, action, stoptrigger, encoding, errors)


class DetachedProcessNoSyncRead(DetachedProcess):
    def run(self):
        if self.stdin:
            self.tmpfilestdin = get_tmpfile(suffix=".txt")
            with open(self.tmpfilestdin, "w", encoding="utf-8") as f:
                f.write(self.stdin)
            stdinadd = f" -RedirectStandardInput {self.tmpfilestdin} "
        else:
            stdinadd = ""

        if myos == "windows":
            self.tmpfile = get_tmpfile(suffix=".bat")
        else:
            self.tmpfile = get_tmpfile(suffix=".sh")
        self.tmpfilestdout = get_tmpfile(suffix=".txt")
        self.tmpfilestderr = get_tmpfile(suffix=".txt")

        UseNewEnvironment = (
            " -UseNewEnvironment $true " if self.use_new_environment else ""
        )
        Wait = " -Wait " if self.wait else ""
        Verb = "" if not self.verb else f" -Verb {self.verb} "
        WhatIf = " -WhatIf " if self.what_if else ""
        WindowStyle = self.window_style if self.window_style else "Normal"

        if "/" not in self.cmd[0] and "\\" not in self.cmd[0]:
            self.cmd[0] = shutil.which(self.cmd[0])
        FilePath = convert_path_in_string(self.cmd[0])
        self._adjustedcmd.append(FilePath)
        WorkingDirectory = (
            os.path.dirname(FilePath)
            if not self.working_directory
            else convert_path_in_string(self.working_directory)
        )

        ArgumentList = []
        try:
            if myos == "windows":
                _ArgumentList = [
                    f"""{x.replace('"', f'{os.sep}{os.sep}"')}""" for x in self.cmd[1:]
                ]
                for a in _ArgumentList:
                    if self.args_to_83:
                        cva = convert_path_in_string(a)
                        ArgumentList.append(cva)
                    else:
                        ArgumentList.append(a)
            else:
                ArgumentList = [
                    f"""{f'{x}'.replace('"', f'`"')}""" for x in self.cmd[1:]
                ]
        except Exception as fe:
            pass
        self._adjustedcmd.extend(ArgumentList)
        if ArgumentList:
            if myos == "windows":
                ArgumentList = f""" -ArgumentList \\"{' '.join(ArgumentList)}\\" """
            else:
                ArgumentList = f""" -ArgumentList \\"{' '.join(ArgumentList)}\\" """

        else:
            ArgumentList = ""

        if myos == "windows":
            self.wholecommandline = f"""{self.psexe} -ExecutionPolicy RemoteSigned Start-Process -FilePath {FilePath}{WhatIf}{Verb}{UseNewEnvironment}{Wait}{stdinadd}{ArgumentList}-RedirectStandardOutput {self.tmpfilestdout} -RedirectStandardError {self.tmpfilestderr} -WorkingDirectory {WorkingDirectory} -WindowStyle {WindowStyle}"""
            self.cmd_to_execute = self.wholecommandline
        else:
            self.wholecommandline = f'''{self.psexe} -ExecutionPolicy RemoteSigned -Command \"Start-Process -FilePath {FilePath} {WhatIf}{Verb}{UseNewEnvironment}{Wait}{stdinadd}{ArgumentList} -RedirectStandardOutput {self.tmpfilestdout} -RedirectStandardError {self.tmpfilestderr} -WorkingDirectory {WorkingDirectory}\"'''

            with open(self.tmpfile, "w") as script_file:
                script_file.write(self.wholecommandline)
                self.cmd_to_execute = self.wholecommandline
            os.chmod(
                self.tmpfile,
                0o777,
            )

        _stoptriggerstdout = [
            False,
        ]
        _stoptriggerstderr = [
            False,
        ]

        self._oldprocs = set()
        if myos == "windows":
            self._subprocesspopen.append(
                subprocess.run(
                    self.cmd_to_execute,
                    cwd=self.working_directory,
                    env=os.environ.copy(),
                    shell=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    **invisibledict,
                )
            )

        else:
            self._subprocesspopen.append(
                subprocess.run(
                    ["nohup", self.tmpfile],
                    shell=False,
                    start_new_session=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            )
        # sleep(1)
        while True:
            try:
                os.rename(self.tmpfilestdout, self.tmpfilestdout)
                os.rename(self.tmpfilestderr, self.tmpfilestderr)
                with open(self.tmpfilestdout, "rb") as f:
                    self.stdoutbuffer = f.readlines()
                with open(self.tmpfilestderr, "rb") as f:
                    self.stderrbuffer = f.readlines()
                break
            except Exception as e:
                kthread_sleep.sleep(0.1)


class DetachedPopen:
    def __init__(
        self,
        args,
        bufsize=-1,
        executable=None,
        stdin=None,
        stdout=None,
        stderr=None,
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
        *,
        user=None,
        group=None,
        extra_groups=None,
        encoding=None,
        errors=None,
        text=None,
        umask=-1,
        pipesize=-1,
        wait=False,
        verb=None,
        what_if=False,
        window_style="Normal",
        print_stdout=True,
        print_stderr=True,
        capture_stdout=True,
        capture_stderr=True,
        stdoutbuffer=None,
        stderrbuffer=None,
        psutil_timeout=15,
        delete_tempfiles=True,
        read_stdout_stderr_async=False,
        args_to_83=True,
        **kwargs,
    ):
        r"""
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
            read_stdout_stderr_async (bool): Whether to read stdout/stderr during execution (True means slower execution).
                                             Default is False
            args_to_83 (bool): Whether to convert arguments to 8.3 format (Windows only) - The main executable will
                               always be converted to 8.3 format, this is only for the arguments afterwards (args[1:]).
                               Default is True.


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


        """
        self.args = args if isinstance(args, list) else shlex.split(args)
        self.bufsize = bufsize
        self.executable = executable
        self.stdin = stdin
        self.preexec_fn = preexec_fn
        self.close_fds = close_fds
        self.shell = shell
        self.cwd = cwd
        self.env = env
        self.universal_newlines = universal_newlines
        self.startupinfo = startupinfo
        self.creationflags = creationflags
        self.restore_signals = restore_signals
        self.start_new_session = start_new_session
        self.pass_fds = pass_fds
        self.user = user
        self.group = group
        self.extra_groups = extra_groups
        self.encoding = encoding
        self.errors = errors
        self.text = text
        self.umask = umask
        self.pipesize = pipesize

        self.args = args  # w
        self.stdin = stdin if isinstance(stdin, str) else None  # w
        if stdout == subprocess.PIPE:
            kwargs["capture_stdout"] = True
            kwargs["print_stdout"] = False
        else:
            kwargs["capture_stdout"] = False
            kwargs["print_stdout"] = True
        if stderr == subprocess.PIPE:
            kwargs["capture_stderr"] = True
            kwargs["print_stderr"] = False

        else:
            kwargs["capture_stderr"] = False
            kwargs["print_stderr"] = True
        bytes_or_string = "rb" if not self.encoding else "r"
        self.cwd = cwd  # w
        self.env = env  # w
        self.startupinfo = startupinfo  # w
        self.wait = wait
        self.verb = verb
        self.what_if = what_if
        self.window_style = window_style
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr
        self.capture_stdout = capture_stdout
        self.capture_stderr = capture_stderr
        self.stdoutbuffer = stdoutbuffer
        self.stderrbuffer = stderrbuffer
        self.psutil_timeout = psutil_timeout
        self.delete_tempfiles = delete_tempfiles
        self.read_stdout_stderr_async = read_stdout_stderr_async
        self.args_to_83 = args_to_83
        self.class_to_execute = (
            DetachedProcessNoSyncRead
            if not self.read_stdout_stderr_async
            else DetachedProcess
        )
        self._running_proc = self.class_to_execute(
            cmd=self.args,
            wait=self.wait,
            use_new_environment=False,
            stdin=self.stdin,
            verb=self.verb,
            what_if=self.what_if,
            working_directory=self.cwd,
            window_style=self.window_style,
            print_stdout=self.print_stdout,
            print_stderr=self.print_stderr,
            capture_stdout=self.capture_stdout,
            capture_stderr=self.capture_stderr,
            stdoutbuffer=self.stdoutbuffer,
            stderrbuffer=self.stderrbuffer,
            psutil_timeout=self.psutil_timeout,
            delete_tempfiles=self.delete_tempfiles,
            stderr_stdout_readmode=bytes_or_string,
            args_to_83=self.args_to_83,
        )
        self.stdout = StdOutStdErr(
            self,
            "stdout",
            bytesorstring=bytes_or_string,
            read_async=self.read_stdout_stderr_async,
        )
        self.stderr = StdOutStdErr(
            self,
            "stderr",
            bytesorstring=bytes_or_string,
            read_async=self.read_stdout_stderr_async,
        )
        self.terminate = self._running_proc.kill
        self.kill = self._running_proc.kill
        self.send_signal = self._running_proc.kill
        self.wait = lambda *arg, **kwargs: None
        self.poll = lambda *arg, **kwargs: None
        self.communicate = lambda *arg, **kwargs: None
        if not self.read_stdout_stderr_async:
            if delete_tempfiles:
                self.kill(taskkill=False)

    def __getattr__(self, item):
        return None
