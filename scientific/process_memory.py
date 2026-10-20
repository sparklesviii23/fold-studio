"""macOS task footprint, including compressed allocations, from the public libproc API.

Layout matches rusage_info_v0 in the macOS SDK's sys/resource.h. Resident size
alone is insufficient for a unified-memory workload under compression.
"""
import ctypes,os,sys

class RusageInfoV0(ctypes.Structure):
 _fields_=[('ri_uuid',ctypes.c_uint8*16)]+[(name,ctypes.c_uint64) for name in (
  'ri_user_time','ri_system_time','ri_pkg_idle_wkups','ri_interrupt_wkups',
  'ri_pageins','ri_wired_size','ri_resident_size','ri_phys_footprint',
  'ri_proc_start_abstime','ri_proc_exit_abstime')]

def process_memory(pid):
 if sys.platform!='darwin':raise OSError('The footprint governor requires the macOS libproc API.')
 if type(pid) is not int or pid<=0:raise ValueError('A positive process identity is required.')
 library=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
 query=library.proc_pid_rusage;query.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];query.restype=ctypes.c_int
 reading=RusageInfoV0()
 if query(pid,0,ctypes.byref(reading))!=0:
  error=ctypes.get_errno();raise OSError(error,os.strerror(error))
 return {'residentBytes':int(reading.ri_resident_size),'physicalFootprintBytes':int(reading.ri_phys_footprint),'processStartAbstime':int(reading.ri_proc_start_abstime)}

def exceeds_footprint_budget(reading,budget_bytes):
 return max(reading['residentBytes'],reading['physicalFootprintBytes'])>budget_bytes
