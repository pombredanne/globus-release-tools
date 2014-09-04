"""
Version comparison routines to deal with software version numbers, such as
1.2.1, or 1.2rc3, based on https://gist.github.com/kjk/458188tc

"""

def __v2fhelper(v, suff, version, weight):
    parts = v.split(suff)
    if 2 != len(parts):
        return v
    version[4] = weight
    version[5] = parts[1] if parts[1] else 0
    return parts[0]
 
def version2float(v):
    """
    Convert a Mozilla-style version string into a floating-point number
    1.2.3.4, 1.2a5, 2.3.4b1pre, 3.0rc2, etc
    """
    version = [
        0, 0, 0, 0, # 4-part numerical revision
        4, # Alpha, beta, RC or (default) final
        0, # Alpha, beta, or RC version revision
        1  # Pre or (default) final
    ]
    parts = v.split("pre")
    if 2 == len(parts):
        version[6] = 0
        v = parts[0]
 
    if ".beta" in v:
        v = __v2fhelper(v, ".beta", version, 2)
    elif "beta" in v:
        v = __v2fhelper(v, "beta", version, 2)
    else:
        v = __v2fhelper(v, "a",  version, 1)
        v = __v2fhelper(v, "b",  version, 2)
    v = __v2fhelper(v, "rc", version, 3)
 
    parts = v.split(".")[:4]
    for (p, i) in zip(parts, range(len(parts))):
        version[i] = p
    ver = float(version[0])
    ver += float(version[1]) / 100.
    ver += float(version[2]) / 10000.
    ver += float(version[3]) / 1000000.
    ver += float(version[4]) / 100000000.
    ver += float(version[5]) / 10000000000.
    ver += float(version[6]) / 1000000000000.
    return ver
 
 
def ProgramVersionGreater(ver1, ver2):
    """
    Return True if ver1 > ver2 using semantics of comparing version
    numbers
    """
    v1f = version2float(ver1)
    v2f = version2float(ver2)
    return v1f > v2f

def ReleaseGreater(ver1, ver2):
    """
    Return True if ver1 > ver2 using semantics of comparing release strings
    (numeric until the first non-number)
    """
    if ver1 is None or ver2 is None:
        return
    accum1 = ""
    rest1 = ""
    for r in range(len(ver1)):
        dig = ver1[r]
        if dig.isdigit() or dig == '.':
            accum1 += dig
        else:
            rest1 = ver1[r:]
            break
    accum2 = ""
    rest2 = ""
    for r in range(len(ver2)):
        dig = ver2[r]
        if dig.isdigit() or dig == '.':
            accum2 += dig
        else:
            rest2 = ver2[r:]
            break

    if accum1[-1] == '.':
        accum1 = accum1[:-1]
    if accum2[-1] == '.':
        accum2 = accum2[:-1]
    a1f = version2float(accum1)
    a2f = version2float(accum2)

    if a1f > a2f:
        return True
    elif a2f > a1f:
        return False
    else:
        return rest1 > rest2