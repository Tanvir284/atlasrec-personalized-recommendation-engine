"""Observed process RSS samples; includes native libraries, excludes child processes."""
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread


def rss():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[("cb",wintypes.DWORD),("faults",wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ("peak","working","quota_peak_paged","quota_paged","quota_peak_nonpaged","quota_nonpaged","pagefile","peak_pagefile","private")]
        counters=Counters()
        counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        handle=kernel.GetCurrentProcess()
        api=ctypes.windll.psapi.GetProcessMemoryInfo
        api.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD]
        if not api(handle,ctypes.byref(counters),counters.cb):
            raise OSError("Process memory measurement unavailable")
        return counters.working/1024**2
    fields=Path("/proc/self/statm").read_text().split()
    return int(fields[1])*os.sysconf("SC_PAGE_SIZE")/1024**2

@contextmanager
def observed_memory():
    stop=Event()
    result={"rss_peak_observed_mb":None,"rss_measurement":"unavailable"}
    thread=None
    try:
        result["rss_peak_observed_mb"]=rss()
        result["rss_measurement"]="process RSS sampled every 100 ms; includes loaded libraries; excludes child processes"
        def sample():
            while not stop.wait(0.1):
                try:
                    result["rss_peak_observed_mb"]=max(result["rss_peak_observed_mb"],rss())
                except OSError:
                    break
        thread=Thread(target=sample,daemon=True)
        thread.start()
    except OSError:
        pass
    try:
        yield result
    finally:
        stop.set()
        if thread:
            thread.join(timeout=1)
