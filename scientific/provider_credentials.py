"""Provider secrets in macOS Keychain, never project files, argv or reports."""
import ctypes as c
import sys

SERVICE=b'org.foldstudio.scientific-providers'
ACCOUNTS={'boltz-api-key','modal-token-id','modal-token-secret'}


def libraries():
    if sys.platform!='darwin':raise ValueError('Configure credentials through the official provider environment on this platform.')
    sec=c.CDLL('/System/Library/Frameworks/Security.framework/Security');cf=c.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    sec.SecKeychainFindGenericPassword.argtypes=[c.c_void_p,c.c_uint32,c.c_char_p,c.c_uint32,c.c_char_p,c.POINTER(c.c_uint32),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p)]
    sec.SecKeychainAddGenericPassword.argtypes=[c.c_void_p,c.c_uint32,c.c_char_p,c.c_uint32,c.c_char_p,c.c_uint32,c.c_void_p,c.POINTER(c.c_void_p)]
    sec.SecKeychainItemModifyAttributesAndData.argtypes=[c.c_void_p,c.c_void_p,c.c_uint32,c.c_void_p]
    sec.SecKeychainItemDelete.argtypes=[c.c_void_p];sec.SecKeychainItemFreeContent.argtypes=[c.c_void_p,c.c_void_p];cf.CFRelease.argtypes=[c.c_void_p]
    return sec,cf


def access(account,value=None,remove=False):
    if account not in ACCOUNTS:raise ValueError('Unknown provider credential slot.')
    sec,cf=libraries();name=account.encode();length=c.c_uint32();data=c.c_void_p();item=c.c_void_p()
    status=sec.SecKeychainFindGenericPassword(None,len(SERVICE),SERVICE,len(name),name,c.byref(length),c.byref(data),c.byref(item))
    try:
        if status not in (0,-25300):raise ValueError('Keychain credential access was denied or unavailable (status '+str(status)+').')
        if value is None and not remove:return c.string_at(data,length.value).decode() if status==0 else None
        if remove:
            if status==0 and sec.SecKeychainItemDelete(item)!=0:raise ValueError('Could not remove provider credential.')
            return None
        if not isinstance(value,str) or not 1<=len(value)<=4096 or any(ch.isspace() for ch in value):raise ValueError('Provider credential must be a nonempty token without whitespace.')
        raw=value.encode()
        code=sec.SecKeychainItemModifyAttributesAndData(item,None,len(raw),raw) if status==0 else sec.SecKeychainAddGenericPassword(None,len(SERVICE),SERVICE,len(name),name,len(raw),raw,None)
        if code:raise ValueError('Could not save provider credential (status '+str(code)+').')
        return True
    finally:
        if data:sec.SecKeychainItemFreeContent(None,data)
        if item:cf.CFRelease(item)


def environment():
    result={}
    for key,account in [('BOLTZ_API_KEY','boltz-api-key'),('MODAL_TOKEN_ID','modal-token-id'),('MODAL_TOKEN_SECRET','modal-token-secret')]:
        value=access(account)
        if value:result[key]=value
    return result
