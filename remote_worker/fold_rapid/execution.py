"""Remote execution admission; request metadata cannot select a Mac fallback."""
import os
import platform
import socket
from .contracts import fields


def policy(value):
    fields(value,('mode','provider','localFallback'))
    if value['mode']!='cloud' or value['provider'] not in ('modal','vast') or value['localFallback'] is not False:raise ValueError('Cloud campaigns require an explicit remote provider and prohibit local fallback.')
    return dict(value)


def require_cloud(value):
    value=policy(value)
    if platform.system()!='Linux':raise ValueError('Cloud scientific campaigns must execute on a Linux cloud worker; execution on this Mac is prohibited.')
    provider=os.environ.get('FOLD_COMPUTE_PROVIDER')
    if value['provider']=='vast' and os.environ.get('SSH_CONNECTION'):provider=provider or 'vast'
    if provider!=value['provider']:raise ValueError('Execution provider differs from the campaign policy; no local or alternate-provider fallback.')
    return {'mode':'cloud','provider':provider,'hostname':socket.gethostname(),'platform':platform.platform(),'controllerLocation':'remote','localFallback':False}
