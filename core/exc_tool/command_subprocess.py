import subprocess
import threading
import time
from typing import Optional, Union, List, Callable, Awaitable
import asyncio
from core.data.models.infrastructure.executions import CommandResult, AsyncCommandResult


def run_command(
    command: Union[str, List[str]],
    timeout: Optional[float] = None,
    shell: bool = False,
    text: bool = True,
) -> CommandResult:
    start = time.time()
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            timeout=timeout,
            shell=shell,
            check=False,
        )
        end = time.time()
        return CommandResult(
            command=command,
            return_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            start_time=start,
            end_time=end,
            duration=end - start,
            error=None,
        )
    except Exception as exc:
        end = time.time()
        return CommandResult(
            command=command,
            return_code=None,
            stdout="",
            stderr="",
            start_time=start,
            end_time=end,
            duration=end - start,
            error=str(exc),
        )


def run_command_stream(
    command: Union[str, List[str]],
    *,
    stdout_callback: Optional[Callable[[str], None]] = None,
    stderr_callback: Optional[Callable[[str], None]] = None,
    timeout: Optional[float] = None,
    shell: bool = False,
    text: bool = True,
    bufsize: int = 1,  # line buffered when text=True
) -> CommandResult:
    """
    Run command but stream stdout/stderr lines to callbacks in real time.
    Callbacks receive each line (without stripping newline unless you want).
    Returns CommandResult with full accumulated stdout/stderr.
    """
    start = time.time()
    # accumulators
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            bufsize=bufsize,
            shell=shell,
            universal_newlines=text,
        )
    except Exception as exc:
        end = time.time()
        return CommandResult(
            command=command,
            return_code=None,
            stdout="",
            stderr="",
            start_time=start,
            end_time=end,
            duration=end - start,
            error=str(exc),
        )

    # reader threads for stdout and stderr
    def _reader(stream, acc, cb, name):
        try:
            # iter read until EOF
            for line in iter(stream.readline, ""):
                acc.append(line)
                if cb:
                    try:
                        cb(line)
                    except Exception:
                        # swallow callback exceptions to not break the reader
                        pass
            stream.close()
        except Exception:
            # If stream read fails, just exit thread
            pass

    t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_lines, stdout_callback, "stdout"), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_lines, stderr_callback, "stderr"), daemon=True)

    t_out.start()
    t_err.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # kill the process and collect what we have
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait()  # ensure reaping
        end = time.time()
        # attempt to join reader threads (they should terminate when streams closed)
        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)
        return CommandResult(
            command=command,
            return_code=proc.returncode,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
            start_time=start,
            end_time=end,
            duration=end - start,
            error=f"TimeoutExpired: {str(exc)}",
        )
    except Exception as exc:
        # unexpected error waiting on process
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait()
        end = time.time()
        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)
        return CommandResult(
            command=command,
            return_code=proc.returncode if proc else None,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
            start_time=start,
            end_time=end,
            duration=end - start,
            error=str(exc),
        )

    # Normal termination
    end = time.time()
    # ensure readers finished
    t_out.join(timeout=1.0)
    t_err.join(timeout=1.0)

    return CommandResult(
        command=command,
        return_code=proc.returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        start_time=start,
        end_time=end,
        duration=end - start,
        error=None,
    )


# -------------------------
# Async runner with streaming callbacks
# -------------------------
async def run_command_async(
    command: Union[str, List[str]],
    *,
    stdout_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    stderr_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    timeout: Optional[float] = None,
    shell: bool = False,
    text: bool = True,
) -> AsyncCommandResult:
    """
    Async command runner. Callbacks may be async functions (coroutines).
    Returns AsyncCommandResult with accumulated stdout/stderr.
    """
    start = time.time()
    stdout_buf: List[str] = []
    stderr_buf: List[str] = []

    # Prepare args for create_subprocess_exec/create_subprocess_shell
    try:
        if isinstance(command, str):
            # if user passed a string and shell=True, use shell
            if shell:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                # treat string as single program name -> use shell for string; otherwise recommend list
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        else:
            # list of args
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
    except Exception as exc:
        end = time.time()
        return AsyncCommandResult(
            command=command,
            return_code=None,
            stdout="",
            stderr="",
            start_time=start,
            end_time=end,
            duration=end - start,
            error=str(exc),
        )

    async def _read_stream(stream: asyncio.StreamReader, buf: List[str], cb: Optional[Callable[[str], Awaitable[None]]]):
        try:
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                # decode if necessary
                try:
                    line = line_bytes.decode() if isinstance(line_bytes, (bytes, bytearray)) else str(line_bytes)
                except Exception:
                    line = repr(line_bytes)
                buf.append(line)
                if cb:
                    try:
                        maybe = cb(line)
                        if asyncio.iscoroutine(maybe):
                            await maybe
                    except Exception:
                        # swallow callback exceptions
                        pass
        except Exception:
            pass

    # create tasks to consume streams
    tasks = []
    if proc.stdout is not None:
        tasks.append(asyncio.create_task(_read_stream(proc.stdout, stdout_buf, stdout_callback)))
    if proc.stderr is not None:
        tasks.append(asyncio.create_task(_read_stream(proc.stderr, stderr_buf, stderr_callback)))

    try:
        # await process completion with optional timeout
        if timeout is not None:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        else:
            await proc.wait()
    except asyncio.TimeoutError as exc:
        try:
            proc.kill()
        except Exception:
            pass
        await proc.wait()
        # let readers drain
        await asyncio.gather(*tasks, return_exceptions=True)
        end = time.time()
        return AsyncCommandResult(
            command=command,
            return_code=proc.returncode,
            stdout="".join(stdout_buf),
            stderr="".join(stderr_buf),
            start_time=start,
            end_time=end,
            duration=end - start,
            error=f"TimeoutExpired: {str(exc)}",
        )
    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        await proc.wait()
        await asyncio.gather(*tasks, return_exceptions=True)
        end = time.time()
        return AsyncCommandResult(
            command=command,
            return_code=proc.returncode,
            stdout="".join(stdout_buf),
            stderr="".join(stderr_buf),
            start_time=start,
            end_time=end,
            duration=end - start,
            error=str(exc),
        )

    # successful exit: wait for readers to finish
    await asyncio.gather(*tasks, return_exceptions=True)
    end = time.time()
    return AsyncCommandResult(
        command=command,
        return_code=proc.returncode,
        stdout="".join(stdout_buf),
        stderr="".join(stderr_buf),
        start_time=start,
        end_time=end,
        duration=end - start,
        error=None,
    )
