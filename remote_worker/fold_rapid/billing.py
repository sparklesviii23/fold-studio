"""Conservative resource reservations and elapsed-time estimates, never invoices."""
import math

def validate(p):
    names={'gpuSecondUSD','cpuCoreSecondUSD','memoryGiBSecondUSD','workerCPUs','workerMemoryGiB','startupSecondsPerStage','safetyUSD','storageAndControlUSD'}
    if not isinstance(p,dict) or set(p)!=names:raise ValueError('Provide every reviewed resource price, startup reserve and safety margin.')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in p.values()):raise ValueError('Invalid resource pricing.')
    if not p['gpuSecondUSD'] or not p['workerCPUs'] or not p['workerMemoryGiB'] or p['safetyUSD']<.25 or p['startupSecondsPerStage']<30:raise ValueError('Resource budget requires positive hardware and explicit safety reserves.')
    return p

def rate(p,engine):
    return (0 if engine=='rosetta' else p['gpuSecondUSD'])+p['workerCPUs']*p['cpuCoreSecondUSD']+p['workerMemoryGiB']*p['memoryGiBSecondUSD']

def coordinator_rate(p):return p['cpuCoreSecondUSD']+4*p['memoryGiBSecondUSD']

def base(value):
    p=validate(value['budget']['resourcePricing'])
    return value['budget']['seconds']*coordinator_rate(p)+p['safetyUSD']+p['storageAndControlUSD']

def reservation(value,engine):
    p=validate(value['budget']['resourcePricing'])
    return (value['stageBudgets'][engine]['seconds']+p['startupSecondsPerStage'])*rate(p,engine)

def quote(value,gpu_quote):
    if 'resourcePricing' not in value['budget']:return None
    total=base(value)+sum(r['maximumCalls']*reservation(value,r['engine']) for r in gpu_quote['stages'])
    return {'expectedResourceReservationUSD':total,'fixedCoordinatorStorageSafetyUSD':base(value),'allowanceUSD':value['budget']['maxEstimatedUSD'],'withinAllowance':total<=value['budget']['maxEstimatedUSD'],'providerReportedUSD':None,'method':'Reviewed requested/hard-limit CPU, memory and GPU rates; full stage runtimes, startup reserves, coordinator ceiling, storage/control and safety margin. Elapsed estimates are not provider billing.','pricing':value['budget']['resourcePricing']}

def live(value,stages,elapsed):
    p=validate(value['budget']['resourcePricing']);used=p['storageAndControlUSD']+p['safetyUSD']+elapsed*coordinator_rate(p)
    for stage in stages:used+=stage.get('observedRemoteSeconds',0)*rate(p,stage['engine'])
    return used
